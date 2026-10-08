"""Thread-safe runtime snapshots and a local one-click diagnostic bundle."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import platform
import re
import sys
import tempfile
import threading
from collections.abc import Callable, Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from .about import APP_NAME
from .config import paths
from .config.preferences import _release_version
from .runtime_logging import RUNTIME_LOG

log = logging.getLogger("fhds.diagnostics")

_LOG_BYTE_LIMIT = 2 * 1024 * 1024
_CONTROLLER_ID_KEYS = frozenset(
    {
        "controller_identity",
        "controller_lock_serial",
        "controller_serial",
        "device_instance_id",
        "identity",
        "instance_id",
        "serial",
        "serial_number",
    }
)
_DEVICE_PATH_KEYS = frozenset({"controller_path", "device_path", "hid_path"})
_QUOTED_OR_BARE_VALUE = (
    r"(?:b?'[^'\r\n]*'|b?\"[^\"\r\n]*\"|[^\s,;\)\]]+)"
)
_LABELED_CONTROLLER_ID_RE = re.compile(
    r"(?P<label>\b(?:controller_identity|controller_lock_serial|"
    r"controller_serial|device_instance_id|identity|instance_id|serial|"
    r"serial_number)\b\s*(?:=|:)\s*)"
    rf"(?P<value>{_QUOTED_OR_BARE_VALUE})",
    re.IGNORECASE,
)
_LABELED_DEVICE_PATH_RE = re.compile(
    r"(?P<label>\b(?:controller_path|device_path|hid_path)\b\s*(?:=|:)\s*)"
    rf"(?P<value>{_QUOTED_OR_BARE_VALUE})",
    re.IGNORECASE,
)
_HID_INTERFACE_PATH_RE = re.compile(
    r"\\{2,4}\?\\{1,2}(?:hid|usb|bthenum|bthledevice)"
    r"#[a-z0-9_&#{}().:+%\-]+",
    re.IGNORECASE,
)
_DEVICE_INSTANCE_ID_RE = re.compile(
    r"(?<![a-z0-9_])(?:hid|usb|bthenum|bthledevice)\\{1,2}"
    r"[^\\\s'\",;:()\[\]]+(?:\\{1,2}[^\\\s'\",;:()\[\]]+)+",
    re.IGNORECASE,
)
_LINUX_HID_PATH_RE = re.compile(
    r"(?<![\w/])/dev/(?:hidraw\d+|input/event\d+)\b",
    re.IGNORECASE,
)
_MAC_ADDRESS_RE = re.compile(
    r"(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])",
    re.IGNORECASE,
)
_NON_IDENTIFIERS = frozenset(
    {"", "false", "none", "not-set", "null", "true", "unavailable", "unknown"}
)


def _identity_fingerprint(value: object) -> str:
    raw = str(value).strip()
    if not raw:
        return ""
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()
    return f"sha256:{digest[:12]}"


def _unquote_log_value(value: str) -> str:
    if len(value) >= 3 and value[0] in {"b", "B"} and value[1] in {"'", '"'}:
        if value[-1] == value[1]:
            return value[2:-1]
    if len(value) >= 2 and value[0] in {"'", '"'} and value[-1] == value[0]:
        return value[1:-1]
    return value


def _fingerprint_marker(kind: str, value: str) -> str:
    return f"<{kind} {_identity_fingerprint(value)}>"


def _replace_labeled_value(match: re.Match[str], *, kind: str) -> str:
    value = _unquote_log_value(match.group("value")).strip()
    if value.casefold() in _NON_IDENTIFIERS:
        return match.group(0)
    return f'{match.group("label")}{_fingerprint_marker(kind, value)}'


def _sanitize_log_line(line: str) -> str:
    line = _LABELED_DEVICE_PATH_RE.sub(
        lambda match: _replace_labeled_value(match, kind="device-path"),
        line,
    )
    line = _LABELED_CONTROLLER_ID_RE.sub(
        lambda match: _replace_labeled_value(match, kind="controller-id"),
        line,
    )
    line = _HID_INTERFACE_PATH_RE.sub(
        lambda match: _fingerprint_marker("device-path", match.group(0)),
        line,
    )
    line = _DEVICE_INSTANCE_ID_RE.sub(
        lambda match: _fingerprint_marker("controller-id", match.group(0)),
        line,
    )
    line = _LINUX_HID_PATH_RE.sub(
        lambda match: _fingerprint_marker("device-path", match.group(0)),
        line,
    )
    return _MAC_ADDRESS_RE.sub(
        lambda match: _fingerprint_marker("controller-id", match.group(0)),
        line,
    )


def _sanitize_log_text(text: str) -> str:
    return "".join(_sanitize_log_line(line) for line in text.splitlines(keepends=True))


def _sanitize_log_payload(payload: bytes) -> bytes:
    text = payload.decode("utf-8-sig", errors="replace")
    return _sanitize_log_text(text).encode("utf-8")


def _complete_log_tail(payload: bytes, *, starts_mid_line: bool) -> bytes:
    if starts_mid_line:
        _, separator, payload = payload.partition(b"\n")
        if not separator:
            return b""
    # The active logger can be writing its last record during the snapshot.
    end = payload.rfind(b"\n")
    return payload[:end + 1] if end >= 0 else b""


def _read_log_tail(path: Path) -> bytes:
    with path.open("rb") as stream:
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        start = max(0, size - _LOG_BYTE_LIMIT)
        if start:
            stream.seek(start - 1)
            starts_mid_line = stream.read(1) != b"\n"
        else:
            stream.seek(0)
            starts_mid_line = False
        payload = stream.read(min(size, _LOG_BYTE_LIMIT))
    payload = _complete_log_tail(payload, starts_mid_line=starts_mid_line)
    sanitized = _sanitize_log_payload(payload)
    # Replacement characters and fingerprints can expand the encoded output.
    # Apply the same record boundary to keep the exported copy bounded too.
    if len(sanitized) > _LOG_BYTE_LIMIT:
        start = len(sanitized) - _LOG_BYTE_LIMIT
        sanitized = _complete_log_tail(
            sanitized[start:],
            starts_mid_line=sanitized[start - 1:start] != b"\n",
        )
    return sanitized


def _json_value(value, *, key: str = ""):
    normalized_key = key.casefold()
    if normalized_key in _CONTROLLER_ID_KEYS:
        return _identity_fingerprint(value)
    if normalized_key in _DEVICE_PATH_KEYS:
        return _identity_fingerprint(value)
    if normalized_key == "last_input_at":
        # A process-local monotonic timestamp is not useful outside the run.
        return None
    if isinstance(value, str):
        return _sanitize_log_text(value)
    if value is None or isinstance(value, (int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Enum):
        return _json_value(value.value, key=key)
    if isinstance(value, Path):
        return value.name
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _json_value(getattr(value, field.name), key=field.name)
            for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(item_key): _json_value(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    return str(value)


def _safe_call(target, method: str):
    if target is None:
        return None
    callback = getattr(target, method, None)
    if not callable(callback):
        return None
    try:
        return callback()
    except Exception as exc:
        return {"snapshot_error": str(exc) or type(exc).__name__}


class DiagnosticsCollector:
    """Collect live component snapshots without taking ownership of them."""

    def __init__(
        self,
        settings,
        *,
        controller_provider: Callable[[], object | None],
        listener_provider: Callable[[], object | None],
        xinput_service=None,
        usb_audio=None,
        haptics_lab=None,
        error_provider: Callable[[], Mapping[str, object]] | None = None,
        runtime_mode: str = "gui",
    ):
        self._settings = settings
        self._controller_provider = controller_provider
        self._listener_provider = listener_provider
        self._xinput_service = xinput_service
        self._usb_audio = usb_audio
        self._haptics_lab = haptics_lab
        self._error_provider = error_provider
        self._runtime_mode = str(runtime_mode)
        self._lock = threading.Lock()
        self._haptic_routing_snapshot = None

    def publish_haptics(self, snapshot) -> None:
        with self._lock:
            self._haptic_routing_snapshot = snapshot

    def snapshot(self) -> dict:
        controller = self._controller_provider()
        listener = self._listener_provider()
        with self._lock:
            haptic_routing = self._haptic_routing_snapshot
        errors = {}
        if self._error_provider is not None:
            try:
                errors = dict(self._error_provider())
            except Exception as exc:
                errors = {"provider": str(exc) or type(exc).__name__}

        xinput = _safe_call(self._xinput_service, "snapshot")
        hidhide = _safe_call(self._xinput_service, "hidhide_snapshot")
        controller_state = _safe_call(controller, "snapshot")
        if controller_state is None and controller is not None:
            controller_state = {
                "connected": bool(getattr(controller, "connected", False)),
                "backend": type(controller).__name__,
            }
        payload = {
            "schema_version": 1,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "application": {
                "name": APP_NAME,
                "release": _release_version() or "unknown",
                "runtime_mode": self._runtime_mode,
                "frozen": bool(getattr(sys, "frozen", False)),
            },
            "system": {
                "platform": platform.platform(),
                "python": platform.python_version(),
                "architecture": platform.machine(),
                "executable_name": Path(sys.executable).name,
            },
            "settings": {
                "language": getattr(self._settings, "language", ""),
                "use_dsx": bool(getattr(self._settings, "use_dsx", False)),
                "forza_platform": getattr(
                    self._settings,
                    "preferred_forza_platform",
                    "",
                ),
                "hidhide_enabled": bool(
                    getattr(self._settings, "enable_hidhide", False)
                ),
                "trigger_feedback_enabled": bool(
                    getattr(self._settings, "enable_trigger_feedback", False)
                ),
                "body_haptics_enabled": bool(
                    getattr(self._settings, "enable_body_haptics", False)
                ),
                "auto_reconnect_enabled": bool(
                    getattr(self._settings, "enable_reconnect", False)
                ),
                "udp_host": getattr(self._settings, "udp_host", ""),
                "udp_port": getattr(self._settings, "udp_port", None),
                "udp_timeout_s": getattr(self._settings, "udp_timeout", None),
            },
            "controller": controller_state,
            "controller_diagnostics": _safe_call(
                controller,
                "diagnostics_snapshot",
            ),
            "telemetry": _safe_call(listener, "snapshot"),
            "xinput": xinput,
            "hidhide": hidhide,
            "usb_audio": _safe_call(self._usb_audio, "diagnostics_snapshot"),
            "haptic_routing": haptic_routing,
            "haptics_lab": _safe_call(self._haptics_lab, "snapshot"),
            "runtime_errors": errors,
            "privacy": {
                "controller_identity": "sha256 fingerprint only",
                "preferences_included": False,
                "profiles_included": False,
            },
        }
        return _json_value(payload)

    @staticmethod
    def _flush_logs() -> None:
        for handler in logging.getLogger().handlers:
            try:
                handler.flush()
            except Exception:
                pass

    @staticmethod
    def _log_files() -> tuple[Path, ...]:
        candidates = (
            RUNTIME_LOG,
            RUNTIME_LOG.with_name(f"{RUNTIME_LOG.name}.1"),
            RUNTIME_LOG.with_name(f"{RUNTIME_LOG.name}.2"),
            paths.DATA / "crash.log",
        )
        return tuple(path for path in candidates if path.is_file())

    def _log_payloads(self) -> tuple[tuple[str, bytes], ...]:
        payloads = []
        for path in self._log_files():
            try:
                payloads.append(
                    (path.name, _read_log_tail(path))
                )
            except OSError as exc:
                # Rotation can rename a log between discovery and reading.
                # The runtime snapshot is still useful, so omit only that file.
                log.debug("Diagnostic log snapshot skipped for %s: %s", path, exc)
        return tuple(payloads)

    def export(self, destination_dir: Path | None = None) -> Path:
        """Write one local ZIP and return its final path."""
        self._flush_logs()
        destination = Path(destination_dir) if destination_dir is not None else paths.DATA / "diagnostics"
        destination.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        final_path = destination / f"FHDS-diagnostics-{stamp}.zip"
        suffix = 1
        while True:
            try:
                # Reserve the final name across threads and processes, including
                # portable FAT/exFAT destinations which do not support hard links.
                with final_path.open("xb"):
                    pass
                break
            except FileExistsError:
                final_path = destination / f"FHDS-diagnostics-{stamp}-{suffix}.zip"
                suffix += 1
        temporary = None
        readme = (
            "FH-DualSense-Enhanced diagnostic bundle\n\n"
            "This bundle contains a point-in-time runtime snapshot and bounded log files.\n"
            "Each log contains at most 2 MiB of recent complete records; oversized or "
            "unfinished records are omitted.\n"
            "It does not contain user preferences or profiles. Controller identifiers and "
            "HID device paths are replaced with short SHA-256 fingerprints.\n"
            "Logs can still contain other local paths or error text, so review the ZIP before "
            "sharing it.\n"
        )
        try:
            log_payloads = self._log_payloads()
            payload = self.snapshot()
            payload["bundle_files"] = [f"logs/{name}" for name, _data in log_payloads]
            with tempfile.NamedTemporaryFile(
                mode="w+b",
                prefix=f".{final_path.name}.",
                suffix=".tmp",
                dir=destination,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                with ZipFile(stream, "w", compression=ZIP_DEFLATED) as archive:
                    archive.writestr(
                        "diagnostics.json",
                        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
                    )
                    archive.writestr("README.txt", readme)
                    for name, data in log_payloads:
                        archive.writestr(f"logs/{name}", data)
            os.replace(temporary, final_path)
        except Exception:
            for path in (temporary, final_path):
                if path is not None:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass
            raise
        log.info("Diagnostic bundle written: %s", final_path)
        return final_path
