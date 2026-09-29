"""HidHide isolation for the Windows Xbox App bridge.

HidHide 1.7+ supports FHDS-owned process-lifetime device entries. The official
1.5 driver requires persistent device rules. FHDS journals its own additions
and removes them on normal exit or the next launch after an interrupted exit.
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import shutil
import sys
import threading
import uuid
from contextlib import AbstractContextManager
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol

from ..config import paths


log = logging.getLogger("fhds.hidhide")

_CONTROL_DEVICE = r"\\.\HidHide"
_IO_CONTROL_DEVICE_TYPE = 32769
_METHOD_BUFFERED = 0
_FILE_READ_DATA = 1
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_SHARE_DELETE = 0x00000004
_OPEN_EXISTING = 3
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_VOLUME_NAME_NT = 0x00000002
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_OWNERSHIP_SCHEMA = 1
_DUALSENSE_HARDWARE_ID = re.compile(
    r"(?:^VID_054C&PID_(?:0CE6|0DF2)|_VID&0002054C_PID&(?:0CE6|0DF2))(?=&|$)",
    re.IGNORECASE,
)


def _ctl_code(function: int) -> int:
    return (
        (_IO_CONTROL_DEVICE_TYPE << 16)
        | (_FILE_READ_DATA << 14)
        | (int(function) << 2)
        | _METHOD_BUFFERED
    )


IOCTL_GET_WHITELIST = _ctl_code(2048)
IOCTL_SET_WHITELIST = _ctl_code(2049)
IOCTL_GET_BLACKLIST = _ctl_code(2050)
IOCTL_SET_BLACKLIST = _ctl_code(2051)
IOCTL_GET_ACTIVE = _ctl_code(2052)
IOCTL_SET_ACTIVE = _ctl_code(2053)
IOCTL_GET_WLINVERSE = _ctl_code(2054)
IOCTL_ADD_SESSION_BLACKLIST = _ctl_code(2056)
IOCTL_CLR_SESSION_BLACKLIST = _ctl_code(2057)


class HidHidePhase(str, Enum):
    DISABLED = "disabled"
    READY = "ready"
    ACTIVE = "active"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class HidHideSnapshot:
    phase: HidHidePhase = HidHidePhase.DISABLED
    hidden_device_count: int = 0
    last_error: str = ""
    game_restart_recommended: bool = False
    manual_configuration: bool = False
    automatic_configuration: bool = False


class HidHideError(RuntimeError):
    pass


class HidHideUnavailableError(HidHideError):
    pass


class HidHideSafetyError(HidHideError):
    pass


class HidHideApi(Protocol):
    def get_whitelist(self) -> tuple[str, ...]: ...

    def set_whitelist(self, entries: tuple[str, ...]) -> None: ...

    def get_blacklist(self) -> tuple[str, ...]: ...

    def set_blacklist(self, entries: tuple[str, ...]) -> None: ...

    def get_active(self) -> bool: ...

    def set_active(self, active: bool) -> None: ...

    def get_inverse(self) -> bool: ...

    def add_session_blacklist(self, entries: tuple[str, ...]) -> None: ...

    def clear_session_blacklist(self) -> None: ...


ApiFactory = Callable[[], AbstractContextManager[HidHideApi]]


def _encode_multi_sz(entries: tuple[str, ...]) -> bytes:
    values: list[str] = []
    for entry in entries:
        value = str(entry)
        if not value or "\0" in value:
            raise ValueError("HidHide MULTI_SZ entries must be non-empty and contain no NUL")
        values.append(value)
    # HidHide's persistent list API mirrors its own StringListToMultiString:
    # an empty collection is one terminating WCHAR, while non-empty lists end
    # with the item terminator plus the list terminator. Session additions are
    # always non-empty and therefore satisfy 1.7's stricter double-NUL check.
    text = "\0".join(values) + ("\0\0" if values else "\0")
    return text.encode("utf-16-le")


def _decode_multi_sz(payload: bytes) -> tuple[str, ...]:
    if payload == b"\0\0":
        return ()
    if len(payload) < 4 or len(payload) % 2:
        raise HidHideError("HidHide returned an invalid MULTI_SZ byte length")
    try:
        text = payload.decode("utf-16-le")
    except UnicodeDecodeError as exc:
        raise HidHideError("HidHide returned invalid UTF-16 data") from exc
    if not text.endswith("\0\0"):
        raise HidHideError("HidHide returned an unterminated MULTI_SZ")
    # HidHide 1.5 reports a buffer larger than the actual collection. Its
    # unwritten suffix is zero-filled, so find the first list terminator while
    # still rejecting any nonzero data after it.
    end = text.find("\0\0")
    if end < 0 or text[end:].strip("\0"):
        raise HidHideError("HidHide returned data after the MULTI_SZ terminator")
    values = text[:end].split("\0") if end else []
    if any(not value for value in values):
        raise HidHideError("HidHide returned an invalid empty MULTI_SZ entry")
    return tuple(values)


class _WindowsDriverSession(AbstractContextManager["_WindowsDriverSession"]):
    def __init__(self):
        if sys.platform != "win32":
            raise HidHideUnavailableError("HidHide is available only on Windows")
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_apis()
        self._handle: int | None = None

    def _configure_apis(self) -> None:
        kernel32 = self._kernel32
        kernel32.CreateFileW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.DeviceIoControl.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p,
        )
        kernel32.DeviceIoControl.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL

    def __enter__(self) -> "_WindowsDriverSession":
        handle = self._kernel32.CreateFileW(
            _CONTROL_DEVICE,
            0x80000000,  # GENERIC_READ
            _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
            None,
            _OPEN_EXISTING,
            _FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if handle in (None, _INVALID_HANDLE_VALUE):
            error = ctypes.WinError(ctypes.get_last_error())
            if getattr(error, "winerror", None) in {5, 32}:
                raise HidHideUnavailableError(
                    "HidHide control device is busy or access was denied; "
                    "close the Configuration Client and FHDS will retry"
                ) from error
            raise HidHideUnavailableError(
                "HidHide is not installed or its control device is unavailable"
            ) from error
        self._handle = int(handle)
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        handle, self._handle = self._handle, None
        if handle is not None:
            self._kernel32.CloseHandle(handle)

    def _ioctl(
        self,
        code: int,
        *,
        input_bytes: bytes | None = None,
        output_size: int = 0,
    ) -> tuple[bytes, int]:
        if self._handle is None:
            raise HidHideError("HidHide control device is not open")
        input_buffer = (
            None if input_bytes is None else ctypes.create_string_buffer(input_bytes)
        )
        output_buffer = (
            None if output_size <= 0 else ctypes.create_string_buffer(output_size)
        )
        returned = wintypes.DWORD()
        ok = self._kernel32.DeviceIoControl(
            self._handle,
            code,
            None if input_buffer is None else ctypes.cast(input_buffer, ctypes.c_void_p),
            0 if input_bytes is None else len(input_bytes),
            None if output_buffer is None else ctypes.cast(output_buffer, ctypes.c_void_p),
            max(0, int(output_size)),
            ctypes.byref(returned),
            None,
        )
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        if output_buffer is None:
            return b"", int(returned.value)
        if returned.value > output_size:
            raise HidHideError("HidHide returned more bytes than the supplied buffer")
        return output_buffer.raw[: returned.value], int(returned.value)

    def _get_multi_sz(self, code: int) -> tuple[str, ...]:
        _unused, required = self._ioctl(code)
        if required < 2 or required % 2:
            raise HidHideError("HidHide returned an invalid MULTI_SZ size")
        payload, returned = self._ioctl(code, output_size=required)
        if returned != required:
            raise HidHideError("HidHide changed a list while it was being read")
        return _decode_multi_sz(payload)

    def _set_multi_sz(self, code: int, entries: tuple[str, ...]) -> None:
        self._ioctl(code, input_bytes=_encode_multi_sz(entries))

    def _get_boolean(self, code: int) -> bool:
        payload, returned = self._ioctl(code, output_size=1)
        if returned != 1:
            raise HidHideError("HidHide returned an invalid BOOLEAN size")
        return payload != b"\0"

    def _set_boolean(self, code: int, value: bool) -> None:
        self._ioctl(code, input_bytes=b"\1" if value else b"\0")

    def get_whitelist(self) -> tuple[str, ...]:
        return self._get_multi_sz(IOCTL_GET_WHITELIST)

    def set_whitelist(self, entries: tuple[str, ...]) -> None:
        self._set_multi_sz(IOCTL_SET_WHITELIST, entries)

    def get_blacklist(self) -> tuple[str, ...]:
        return self._get_multi_sz(IOCTL_GET_BLACKLIST)

    def set_blacklist(self, entries: tuple[str, ...]) -> None:
        self._set_multi_sz(IOCTL_SET_BLACKLIST, entries)

    def get_active(self) -> bool:
        return self._get_boolean(IOCTL_GET_ACTIVE)

    def set_active(self, active: bool) -> None:
        self._set_boolean(IOCTL_SET_ACTIVE, active)

    def get_inverse(self) -> bool:
        return self._get_boolean(IOCTL_GET_WLINVERSE)

    def add_session_blacklist(self, entries: tuple[str, ...]) -> None:
        self._set_multi_sz(IOCTL_ADD_SESSION_BLACKLIST, entries)

    def clear_session_blacklist(self) -> None:
        self._ioctl(IOCTL_CLR_SESSION_BLACKLIST)


def _open_driver() -> _WindowsDriverSession:
    return _WindowsDriverSession()


def application_full_image_name(path: Path) -> str:
    """Resolve a Win32 executable to the NT path HidHide compares in-kernel."""
    if sys.platform != "win32":
        raise HidHideUnavailableError("HidHide is available only on Windows")
    resolved = Path(path).resolve(strict=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.GetFinalPathNameByHandleW.argtypes = (
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    )
    kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.CreateFileW(
        str(resolved),
        0,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
        None,
        _OPEN_EXISTING,
        _FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle in (None, _INVALID_HANDLE_VALUE):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        required = int(kernel32.GetFinalPathNameByHandleW(handle, None, 0, _VOLUME_NAME_NT))
        if required <= 0:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_unicode_buffer(required + 1)
        written = int(
            kernel32.GetFinalPathNameByHandleW(
                handle,
                buffer,
                len(buffer),
                _VOLUME_NAME_NT,
            )
        )
        if written <= 0 or written >= len(buffer):
            raise ctypes.WinError(ctypes.get_last_error())
        result = buffer.value
    finally:
        kernel32.CloseHandle(handle)
    if not result.casefold().startswith("\\device\\".casefold()):
        raise HidHideError("Windows did not return an NT device path for this executable")
    return result


def device_instance_id_from_hid_path(path: bytes | str) -> str:
    """Convert a hidapi interface path into its SetupAPI device instance ID."""
    if isinstance(path, bytes):
        try:
            value = path.decode("utf-8")
        except UnicodeDecodeError:
            value = path.decode("mbcs")
    else:
        value = str(path)
    value = value.strip().rstrip("\0")
    if value.startswith("\\\\?\\"):
        value = value[4:]
    elif value.startswith("\\?\\"):
        value = value[3:]
    components = value.split("#")
    if len(components) < 4 or not components[-1].startswith("{"):
        raise ValueError("not a Windows HID interface path")
    instance_id = "\\".join(components[:-1]).strip("\\")
    if not instance_id.casefold().startswith("hid\\") or instance_id.count("\\") < 2:
        raise ValueError("not a HID device instance path")
    return instance_id.upper()


def _standalone_supported() -> bool:
    return sys.platform == "win32" and bool(getattr(sys, "frozen", False))


def _canonical(entries: tuple[str, ...] | list[str]) -> frozenset[str]:
    return frozenset(str(entry).casefold() for entry in entries)


def _is_dualsense_device_rule(instance_id: str) -> bool:
    parts = instance_id.split("\\")
    return bool(
        len(parts) >= 3
        and parts[0].upper() in {"HID", "BTHENUM"}
        and _DUALSENSE_HARDWARE_ID.search(parts[1])
    )


def _load_owned_whitelist(path: Path) -> tuple[str, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ()
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Ignoring invalid HidHide ownership journal %s: %s", path, exc)
        return ()
    values = payload.get("whitelist_paths") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != _OWNERSHIP_SCHEMA
        or not isinstance(values, list)
    ):
        log.warning("Ignoring incompatible HidHide ownership journal %s", path)
        return ()
    if not all(isinstance(value, str) and value and "\0" not in value for value in values):
        log.warning("Ignoring malformed HidHide ownership journal %s", path)
        return ()
    return tuple(values)


def _write_owned_whitelist(path: Path, entries: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "schema": _OWNERSHIP_SCHEMA,
            "whitelist_paths": list(entries),
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _load_owned_devices(path: Path) -> tuple[tuple[str, ...], bool, tuple[str, ...] | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return (), False, None
    except (OSError, json.JSONDecodeError) as exc:
        raise HidHideSafetyError(f"Cannot read FHDS HidHide device journal: {exc}") from exc
    entries = payload.get("device_instance_ids") if isinstance(payload, dict) else None
    active_owned = payload.get("active_owned") if isinstance(payload, dict) else None
    baseline = payload.get("active_baseline") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema") != 1
        or not isinstance(entries, list)
        or not all(isinstance(entry, str) and entry and "\0" not in entry for entry in entries)
        or not isinstance(active_owned, bool)
        or (
            baseline is not None
            and (
                not isinstance(baseline, list)
                or not all(
                    isinstance(entry, str) and entry and "\0" not in entry
                    for entry in baseline
                )
            )
        )
        or (not active_owned and baseline is not None)
    ):
        raise HidHideSafetyError("FHDS HidHide device journal is invalid; manual recovery is required")
    return tuple(entries), active_owned, tuple(baseline) if baseline is not None else None


def _write_owned_devices(
    path: Path,
    entries: tuple[str, ...],
    active_owned: bool,
    active_baseline: tuple[str, ...] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "schema": 1,
            "device_instance_ids": list(entries),
            "active_owned": active_owned,
            "active_baseline": list(active_baseline) if active_baseline is not None else None,
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


class HidHideService:
    """Own only FHDS-added rules while preserving pre-existing user rules."""

    def __init__(
        self,
        *,
        api_factory: ApiFactory = _open_driver,
        application_path: Path | None = None,
        ownership_path: Path | None = None,
        device_ownership_path: Path | None = None,
        full_image_resolver: Callable[[Path], str] = application_full_image_name,
        standalone_supported: Callable[[], bool] = _standalone_supported,
        automatic_legacy: bool = True,
    ):
        self._api_factory = api_factory
        self._application_path = application_path
        self._ownership_path = ownership_path or (paths.DATA / "hidhide_owned.json")
        self._device_ownership_path = device_ownership_path or (
            paths.DATA / "hidhide_device_owned.json"
        )
        self._full_image_resolver = full_image_resolver
        self._standalone_supported = standalone_supported
        self._automatic_legacy = automatic_legacy
        self._lock = threading.RLock()
        self._started = False
        self._manual_configuration = False
        self._auto_legacy_session = False
        self._manual_image_name = ""
        self._hidden: dict[str, str] = {}
        self._snapshot = HidHideSnapshot()

    def snapshot(self) -> HidHideSnapshot:
        with self._lock:
            return self._snapshot

    @property
    def started(self) -> bool:
        with self._lock:
            return self._started

    def prepare_application_access(self) -> HidHideSnapshot:
        """Allow this EXE to read HID before a hidden controller is enumerated.

        This stage never changes Device hiding or adds a physical device rule.
        The virtual target must be connected before ``start`` does either.
        """
        with self._lock:
            if self._started:
                return self._snapshot
            if not self._standalone_supported():
                self._snapshot = HidHideSnapshot(
                    phase=HidHidePhase.UNAVAILABLE,
                    last_error="HidHide integration requires the Windows standalone EXE",
                )
                return self._snapshot
            try:
                image_name = self._full_image_resolver(
                    Path(self._application_path or sys.executable)
                )
                previous_owned = _load_owned_whitelist(self._ownership_path)
                with self._api_factory() as api:
                    if api.get_inverse():
                        raise HidHideSafetyError(
                            "Turn off inverse application cloak in the HidHide Configuration Client"
                        )
                    current = api.get_whitelist()
                    desired, new_owned = self._desired_whitelist(
                        current, previous_owned, image_name, inverse=False
                    )
                    if _canonical(desired) != _canonical(current):
                        # Keep both old and new owned paths in the journal until
                        # the driver write is verified, including on a crash.
                        _write_owned_whitelist(
                            self._ownership_path,
                            tuple(dict.fromkeys((*previous_owned, *new_owned))),
                        )
                        api.set_whitelist(desired)
                        if _canonical(api.get_whitelist()) != _canonical(desired):
                            raise HidHideError("HidHide did not retain the FHDS application rule")
                    _write_owned_whitelist(self._ownership_path, new_owned)
            except Exception as exc:
                phase, message = self._classify_error(exc)
                self._snapshot = HidHideSnapshot(phase=phase, last_error=message)
                log.warning("HidHide could not allow FHDS to read HID: %s", message)
                return self._snapshot
            self._snapshot = HidHideSnapshot(phase=HidHidePhase.READY)
            log.info("HidHide allows the current FHDS executable to read HID")
            return self._snapshot

    def start(self) -> HidHideSnapshot:
        with self._lock:
            if self._started:
                return self._snapshot
            if not self._standalone_supported():
                self._snapshot = HidHideSnapshot(
                    phase=HidHidePhase.UNAVAILABLE,
                    last_error="HidHide integration requires the Windows standalone EXE",
                )
                return self._snapshot

            application_path = Path(self._application_path or sys.executable)
            previous_owned = _load_owned_whitelist(self._ownership_path)
            manual_configuration = False
            try:
                full_image_name = self._full_image_resolver(application_path)
                with self._api_factory() as api:
                    try:
                        api.clear_session_blacklist()
                    except OSError as exc:
                        if not self._session_ioctl_unavailable(exc):
                            raise
                        manual_configuration = True
                    if manual_configuration:
                        if self._automatic_legacy:
                            self._prepare_legacy(api, full_image_name, previous_owned)
                        else:
                            self._verify_manual_application(api, full_image_name)
                    else:
                        original_whitelist: tuple[str, ...] | None = None
                        try:
                            self._cleanup_owned_devices(api)
                            original_whitelist = api.get_whitelist()
                            inverse = api.get_inverse()
                            if inverse:
                                raise HidHideSafetyError(
                                    "Turn off inverse application cloak in the HidHide Configuration Client"
                                )
                            self._inactive_rule_baseline(api)
                            desired, new_owned = self._desired_whitelist(
                                original_whitelist,
                                previous_owned,
                                full_image_name,
                                inverse=inverse,
                            )
                            if _canonical(desired) != _canonical(original_whitelist):
                                api.set_whitelist(desired)
                                if _canonical(api.get_whitelist()) != _canonical(desired):
                                    raise HidHideError(
                                        "HidHide did not retain the FHDS application rule"
                                    )
                            _write_owned_whitelist(self._ownership_path, new_owned)
                            self._enable_active_if_safe(api)
                        except Exception:
                            self._rollback_start(
                                api,
                                original_whitelist=original_whitelist,
                                previous_owned=previous_owned,
                            )
                            raise
            except Exception as exc:
                self._started = False
                self._manual_configuration = manual_configuration
                self._auto_legacy_session = manual_configuration and self._automatic_legacy
                self._manual_image_name = ""
                self._hidden.clear()
                phase, message = self._classify_error(exc)
                self._snapshot = HidHideSnapshot(
                    phase=phase,
                    last_error=message,
                    manual_configuration=manual_configuration,
                    automatic_configuration=self._auto_legacy_session,
                )
                log.warning("HidHide isolation unavailable: %s", message)
                return self._snapshot

            self._started = True
            self._manual_configuration = manual_configuration
            self._auto_legacy_session = manual_configuration and self._automatic_legacy
            self._manual_image_name = full_image_name if manual_configuration else ""
            self._hidden.clear()
            self._snapshot = HidHideSnapshot(
                phase=HidHidePhase.READY,
                manual_configuration=manual_configuration,
                automatic_configuration=self._auto_legacy_session,
            )
            log.info(
                "HidHide %s isolation is ready for the current FHDS executable",
                "manual" if manual_configuration else "session",
            )
            return self._snapshot

    @staticmethod
    def _session_ioctl_unavailable(exc: OSError) -> bool:
        return getattr(exc, "winerror", None) in {1, 50, 87}

    @staticmethod
    def _verify_manual_application(api: HidHideApi, image_name: str) -> None:
        if not api.get_active():
            raise HidHideSafetyError(
                "Enable Device hiding in the HidHide Configuration Client"
            )
        if api.get_inverse():
            raise HidHideSafetyError(
                "Turn off inverse application cloak in the HidHide Configuration Client"
            )
        if image_name.casefold() not in _canonical(api.get_whitelist()):
            raise HidHideSafetyError(
                "Add this FHDS executable to Applications in the HidHide Configuration Client"
            )

    def _prepare_legacy(
        self,
        api: HidHideApi,
        image_name: str,
        previous_owned: tuple[str, ...],
    ) -> None:
        self._cleanup_owned_devices(api)
        if api.get_inverse():
            raise HidHideSafetyError(
                "Turn off inverse application cloak in the HidHide Configuration Client"
            )
        self._inactive_rule_baseline(api)
        current_whitelist = api.get_whitelist()
        desired, newly_owned = self._desired_whitelist(
            current_whitelist, previous_owned, image_name, inverse=False
        )
        _write_owned_whitelist(self._ownership_path, newly_owned)
        if _canonical(desired) != _canonical(current_whitelist):
            api.set_whitelist(desired)
            if _canonical(api.get_whitelist()) != _canonical(desired):
                raise HidHideError("HidHide did not retain the FHDS application rule")
        self._enable_active_if_safe(api)

    @staticmethod
    def _inactive_rule_baseline(api: HidHideApi) -> tuple[str, ...] | None:
        if api.get_active():
            return None
        baseline = api.get_blacklist()
        if not all(_is_dualsense_device_rule(entry) for entry in baseline):
            raise HidHideSafetyError(
                "HidHide has non-DualSense device rules while Device hiding is off; "
                "review them in the Configuration Client before enabling Xbox App isolation"
            )
        return baseline

    def _enable_active_if_safe(self, api: HidHideApi) -> None:
        baseline = self._inactive_rule_baseline(api)
        if baseline is None:
            return
        _write_owned_devices(self._device_ownership_path, (), True, baseline)
        api.set_active(True)
        if not api.get_active():
            raise HidHideError("HidHide did not enable Device hiding")

    def _cleanup_owned_devices(self, api: HidHideApi) -> None:
        owned, active_owned, active_baseline = _load_owned_devices(self._device_ownership_path)
        if not owned and not active_owned:
            return
        current = api.get_blacklist()
        desired = tuple(entry for entry in current if entry.casefold() not in _canonical(owned))
        if _canonical(desired) != _canonical(current):
            api.set_blacklist(desired)
            if _canonical(api.get_blacklist()) != _canonical(desired):
                raise HidHideError("HidHide did not remove FHDS-owned device rules")
        if active_owned and api.get_active():
            unchanged = (
                not desired
                if active_baseline is None
                else _canonical(desired) == _canonical(active_baseline)
            )
            if unchanged:
                api.set_active(False)
                if api.get_active():
                    raise HidHideError("HidHide did not restore Device hiding")
            else:
                log.warning(
                    "Leaving HidHide Device hiding enabled because its device rules changed"
                )
        _write_owned_devices(self._device_ownership_path, (), False)

    @staticmethod
    def _desired_whitelist(
        current: tuple[str, ...],
        owned: tuple[str, ...],
        application: str,
        *,
        inverse: bool,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        owned_keys = _canonical(owned)
        desired = [entry for entry in current if entry.casefold() not in owned_keys]
        current_is_user_owned = any(
            entry.casefold() == application.casefold()
            and entry.casefold() not in owned_keys
            for entry in current
        )
        if inverse:
            if current_is_user_owned:
                raise HidHideSafetyError(
                    "HidHide inverse application cloak explicitly blocks this FHDS executable"
                )
            return tuple(desired), ()
        if current_is_user_owned:
            return tuple(desired), ()
        desired.append(application)
        return tuple(desired), (application,)

    def _rollback_start(
        self,
        api: HidHideApi,
        *,
        original_whitelist: tuple[str, ...] | None,
        previous_owned: tuple[str, ...],
    ) -> None:
        try:
            api.clear_session_blacklist()
        except Exception:
            pass
        try:
            self._cleanup_owned_devices(api)
        except Exception:
            log.exception("Could not restore FHDS-owned HidHide Device hiding state")
        if original_whitelist is not None:
            try:
                if _canonical(api.get_whitelist()) != _canonical(original_whitelist):
                    api.set_whitelist(original_whitelist)
            except Exception:
                log.exception("Could not roll back HidHide application rules")
        try:
            _write_owned_whitelist(self._ownership_path, previous_owned)
        except OSError:
            log.exception("Could not restore HidHide ownership journal")

    def register_device(self, info: dict[str, Any]) -> bool:
        try:
            instance_id = device_instance_id_from_hid_path(info.get("path", b""))
        except (TypeError, ValueError) as exc:
            log.warning("HidHide could not derive a device instance ID: %s", exc)
            return False
        key = instance_id.casefold()
        with self._lock:
            if not self._started:
                return False
            if key in self._hidden:
                checked = self.verify_active()
                if checked.phase is HidHidePhase.ACTIVE and key in self._hidden:
                    return True
                if checked.phase not in {HidHidePhase.READY, HidHidePhase.ACTIVE}:
                    return False
            try:
                with self._api_factory() as api:
                    if self._manual_configuration:
                        if self._auto_legacy_session:
                            if not api.get_active():
                                raise HidHideSafetyError("HidHide Device hiding was turned off")
                            current = api.get_blacklist()
                            if key not in _canonical(current):
                                owned, active_owned, active_baseline = _load_owned_devices(
                                    self._device_ownership_path
                                )
                                _write_owned_devices(
                                    self._device_ownership_path,
                                    (*owned, instance_id),
                                    active_owned,
                                    active_baseline,
                                )
                                desired = (*current, instance_id)
                                api.set_blacklist(desired)
                                if key not in _canonical(api.get_blacklist()):
                                    raise HidHideError("HidHide did not retain the DualSense rule")
                        else:
                            self._verify_manual_application(api, self._manual_image_name)
                            if key not in _canonical(api.get_blacklist()):
                                raise HidHideSafetyError(
                                    "Hide this DualSense in Devices in the HidHide Configuration Client"
                                )
                    else:
                        api.add_session_blacklist((instance_id,))
            except Exception as exc:
                _phase, message = self._classify_error(exc)
                self._snapshot = HidHideSnapshot(
                    phase=HidHidePhase.ERROR,
                    hidden_device_count=len(self._hidden),
                    last_error=message,
                    game_restart_recommended=bool(self._hidden),
                    manual_configuration=self._manual_configuration,
                    automatic_configuration=self._auto_legacy_session,
                )
                log.warning("HidHide could not hide %s: %s", instance_id, message)
                return False
            self._hidden[key] = instance_id
            self._snapshot = HidHideSnapshot(
                phase=HidHidePhase.ACTIVE,
                hidden_device_count=len(self._hidden),
                game_restart_recommended=True,
                manual_configuration=self._manual_configuration,
                automatic_configuration=self._auto_legacy_session,
            )
            log.info("HidHide verified %s", instance_id)
            return True

    def verify_active(self) -> HidHideSnapshot:
        """Read back global hiding and the current 1.5 device rules.

        HidHide 1.7 does not expose a read API for this process's session
        blacklist. There we verify the global switch and FHDS allowlist; the
        session rule itself was accepted by the driver's add IOCTL.
        """
        with self._lock:
            if not self._started or not self._hidden:
                return self._snapshot
            try:
                with self._api_factory() as api:
                    if not api.get_active():
                        raise HidHideSafetyError("HidHide Device hiding was turned off")
                    if api.get_inverse():
                        raise HidHideSafetyError("HidHide inverse application cloak is on")
                    image_name = self._full_image_resolver(
                        Path(self._application_path or sys.executable)
                    )
                    if image_name.casefold() not in _canonical(api.get_whitelist()):
                        raise HidHideSafetyError("FHDS is no longer in HidHide Applications")
                    if self._manual_configuration and not set(self._hidden).issubset(
                        _canonical(api.get_blacklist())
                    ):
                        self._hidden.clear()
                        self._snapshot = HidHideSnapshot(
                            phase=HidHidePhase.READY,
                            manual_configuration=True,
                            automatic_configuration=self._auto_legacy_session,
                            last_error="Physical DualSense hiding rule was removed",
                        )
                        return self._snapshot
            except Exception as exc:
                phase, message = self._classify_error(exc)
                self._snapshot = HidHideSnapshot(
                    phase=phase,
                    last_error=message,
                    manual_configuration=self._manual_configuration,
                    automatic_configuration=self._auto_legacy_session,
                )
                return self._snapshot
            self._snapshot = HidHideSnapshot(
                phase=HidHidePhase.ACTIVE,
                hidden_device_count=len(self._hidden),
                game_restart_recommended=True,
                manual_configuration=self._manual_configuration,
                automatic_configuration=self._auto_legacy_session,
            )
            return self._snapshot

    def stop(self, *, remove_allowlist: bool = False) -> HidHideSnapshot:
        with self._lock:
            if self._manual_configuration:
                if self._auto_legacy_session:
                    try:
                        with self._api_factory() as api:
                            self._cleanup_owned_devices(api)
                    except Exception as exc:
                        _phase, message = self._classify_error(exc)
                        self._snapshot = HidHideSnapshot(
                            phase=HidHidePhase.ERROR,
                            hidden_device_count=len(self._hidden),
                            last_error=message,
                            manual_configuration=True,
                            automatic_configuration=True,
                        )
                        return self._snapshot
                    self._started = False
                    self._manual_configuration = False
                    self._auto_legacy_session = False
                    self._manual_image_name = ""
                    self._hidden.clear()
                    if not remove_allowlist:
                        self._snapshot = HidHideSnapshot()
                        return self._snapshot
                else:
                    self._started = False
                    self._manual_configuration = False
                    self._manual_image_name = ""
                    self._hidden.clear()
                    self._snapshot = HidHideSnapshot()
                    return self._snapshot
            owned = (
                _load_owned_whitelist(self._ownership_path)
                if remove_allowlist
                else ()
            )
            if not self._started and not self._standalone_supported():
                self._snapshot = HidHideSnapshot()
                return self._snapshot
            try:
                owned_devices, active_owned, _baseline = _load_owned_devices(
                    self._device_ownership_path
                )
            except HidHideSafetyError as exc:
                self._snapshot = HidHideSnapshot(phase=HidHidePhase.ERROR, last_error=str(exc))
                return self._snapshot
            if not self._started and not owned and not owned_devices and not active_owned:
                self._snapshot = HidHideSnapshot()
                return self._snapshot
            error = ""
            try:
                with self._api_factory() as api:
                    if self._started:
                        api.clear_session_blacklist()
                    self._cleanup_owned_devices(api)
                    if owned:
                        desired = tuple(
                            entry
                            for entry in api.get_whitelist()
                            if entry.casefold() not in _canonical(owned)
                        )
                        api.set_whitelist(desired)
                        if _canonical(api.get_whitelist()) != _canonical(desired):
                            raise HidHideError(
                                "HidHide did not remove the FHDS application rule"
                            )
                        _write_owned_whitelist(self._ownership_path, ())
            except Exception as exc:
                _phase, error = self._classify_error(exc)
                log.warning("HidHide isolation cleanup failed: %s", error)
            if error:
                # The control device is exclusive and may briefly be held by
                # the official client. Retain ownership state so a later mode
                # sync/toggle can retry the clear instead of forgetting live
                # session entries while this process is still running.
                self._snapshot = HidHideSnapshot(
                    phase=HidHidePhase.ERROR,
                    hidden_device_count=len(self._hidden),
                    last_error=error,
                    game_restart_recommended=bool(self._hidden),
                )
                return self._snapshot
            self._started = False
            self._manual_configuration = False
            self._auto_legacy_session = False
            self._manual_image_name = ""
            self._hidden.clear()
            self._snapshot = HidHideSnapshot()
            return self._snapshot

    @staticmethod
    def _classify_error(exc: Exception) -> tuple[HidHidePhase, str]:
        if isinstance(exc, HidHideUnavailableError):
            return HidHidePhase.UNAVAILABLE, str(exc)
        winerror = getattr(exc, "winerror", None)
        if winerror in {1, 50, 87}:
            return (
                HidHidePhase.UNAVAILABLE,
                "HidHide control request is unavailable or incompatible",
            )
        message = str(exc).strip() or type(exc).__name__
        return HidHidePhase.ERROR, message


def _detect() -> bool:
    if sys.platform != "win32":
        return False
    # HidHide 1.5 may install the driver without HidHideCLI.exe. The service
    # registration is the installation marker; opening the control device is
    # a separate readiness check and can fail while the client holds it.
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Services\HidHide",
        ):
            return True
    except (ImportError, OSError):
        pass
    env = os.environ.get("HIDHIDE_CLI")
    if env and Path(env).is_file():
        return True
    if shutil.which("HidHideCLI.exe"):
        return True
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    return (
        Path(pf)
        / "Nefarius Software Solutions"
        / "HidHide"
        / "x64"
        / "HidHideCLI.exe"
    ).is_file()


_detected: bool | None = None


def is_detected() -> bool:
    global _detected
    if _detected is None:
        _detected = _detect()
    return _detected
