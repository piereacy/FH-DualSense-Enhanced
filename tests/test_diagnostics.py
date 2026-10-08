import json
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from modules.config.settings import Settings
from modules.diagnostics import DiagnosticsCollector

DEVICE_PATH = (
    rb"\\?\hid#vid_054c&pid_0ce6&mi_03#8&2f5a32d1&0&0000"
    rb"#{4d1e55b2-f16f-11cf-88cb-001111000030}"
)
INSTANCE_ID = r"HID\VID_054C&PID_0CE6&MI_03\8&2F5A32D1&0&0000"
CONTROLLER_SERIAL = "aabbccddeeff"


@dataclass(frozen=True)
class _ControllerState:
    connected: bool
    identity: str
    last_input_at: float


class _Component:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def snapshot(self):
        return self._snapshot


class _Controller(_Component):
    def diagnostics_snapshot(self):
        return {"valid_input_report_count": 42}


class _XInput(_Component):
    def hidhide_snapshot(self):
        return {"active": False}


def _collector(settings, controller, listener, xinput):
    return DiagnosticsCollector(
        settings,
        controller_provider=lambda: controller,
        listener_provider=lambda: listener,
        xinput_service=xinput,
        usb_audio=_Component({"output_underflow_count": 2}),
        haptics_lab=_Component({"active": False}),
        error_provider=lambda: {"udp": ""},
        runtime_mode="test",
    )


def test_diagnostic_snapshot_hashes_controller_identity_and_excludes_profiles():
    settings = Settings()
    controller = _Controller(_ControllerState(True, "AA:BB:CC:DD", 123.0))
    listener = _Component({"packet_rate_hz": 60.0})
    xinput = _XInput({"input_owner": "keyboard_mouse"})

    payload = _collector(settings, controller, listener, xinput).snapshot()

    assert payload["controller"]["identity"].startswith("sha256:")
    assert payload["controller"]["identity"] != "AA:BB:CC:DD"
    assert payload["controller"]["last_input_at"] is None
    assert payload["controller_diagnostics"]["valid_input_report_count"] == 42
    assert payload["telemetry"]["packet_rate_hz"] == 60.0
    assert payload["privacy"]["preferences_included"] is False
    assert "profiles" not in payload


def test_export_creates_reviewable_zip_without_preferences(tmp_path, monkeypatch):
    settings = Settings()
    controller = _Controller(_ControllerState(True, "controller-id", 1.0))
    collector = _collector(
        settings,
        controller,
        _Component({"packet_count": 1}),
        _XInput({"status": "waiting_game"}),
    )
    runtime_log = tmp_path / "runtime.log"
    ordinary_line = (
        r"Telemetry packet_count=42; install path C:\XboxGames\Forza Horizon 5\Content"
    )
    runtime_log.write_text(
        "2026-08-10 [INFO] fhds.hidhide: HidHide session-cloaked "
        f"{INSTANCE_ID}\n"
        "2026-08-10 [WARNING] fhds.dualsense: open_path failed on "
        f"{DEVICE_PATH!r} - another process likely holds the device exclusive\n"
        "2026-08-10 [INFO] fhds.gui.system: controller_lock_serial = "
        f"'{CONTROLLER_SERIAL}'\n"
        f"{ordinary_line}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(collector, "_log_files", lambda: (runtime_log,))

    bundle = collector.export(tmp_path / "bundles")

    assert bundle.is_file()
    with ZipFile(bundle) as archive:
        assert set(archive.namelist()) == {
            "README.txt",
            "diagnostics.json",
            "logs/runtime.log",
        }
        payload = json.loads(archive.read("diagnostics.json"))
        readme = archive.read("README.txt").decode("utf-8")
        log_text = archive.read("logs/runtime.log").decode("utf-8")
        assert payload["bundle_files"] == ["logs/runtime.log"]
        assert "preferences or profiles" in readme
        assert "short SHA-256 fingerprints" in readme
        assert "controller-id" not in archive.read("diagnostics.json").decode("utf-8")
        assert INSTANCE_ID not in log_text
        assert "2f5a32d1" not in log_text.casefold()
        assert CONTROLLER_SERIAL not in log_text
        assert len(re.findall(r"<controller-id sha256:[0-9a-f]{12}>", log_text)) == 2
        assert len(re.findall(r"<device-path sha256:[0-9a-f]{12}>", log_text)) == 1
        assert ordinary_line in log_text


def test_snapshot_sanitizes_sensitive_identifiers_embedded_in_error_text():
    controller = _Controller(
        {
            "connected": False,
            "identity": CONTROLLER_SERIAL,
            "error": f"HidHide failed for {INSTANCE_ID}",
            "device_path": DEVICE_PATH.decode(),
        }
    )

    payload = _collector(
        Settings(),
        controller,
        _Component({"packet_count": 1}),
        _XInput({"status": "waiting_game"}),
    ).snapshot()

    encoded = json.dumps(payload)
    assert CONTROLLER_SERIAL not in encoded
    assert INSTANCE_ID not in encoded
    assert "2f5a32d1" not in encoded.casefold()
    assert payload["controller"]["identity"].startswith("sha256:")
    assert payload["controller"]["device_path"].startswith("sha256:")
    assert "<controller-id sha256:" in payload["controller"]["error"]


def test_export_skips_log_that_rotates_before_snapshot(tmp_path, monkeypatch):
    collector = _collector(
        Settings(),
        _Controller(_ControllerState(True, "controller-id", 1.0)),
        _Component({"packet_count": 1}),
        _XInput({"status": "waiting_game"}),
    )
    vanished = tmp_path / "runtime.log"
    monkeypatch.setattr(collector, "_log_files", lambda: (vanished,))

    bundle = collector.export(tmp_path / "bundles")

    with ZipFile(bundle) as archive:
        payload = json.loads(archive.read("diagnostics.json"))
        assert payload["bundle_files"] == []
        assert set(archive.namelist()) == {"README.txt", "diagnostics.json"}


def test_parallel_exports_preserve_both_snapshots(tmp_path, monkeypatch):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime

    from modules import diagnostics

    class FrozenDatetime:
        @classmethod
        def now(cls):
            return datetime(2026, 10, 7, 12, 0, 0).astimezone()

    barrier = threading.Barrier(2)
    collectors = []
    for mode in ("gui", "tui"):
        collector = DiagnosticsCollector(
            Settings(),
            controller_provider=lambda: None,
            listener_provider=lambda: None,
            runtime_mode=mode,
        )
        original = collector.snapshot

        def synchronized_snapshot(original=original):
            barrier.wait(timeout=5)
            return original()

        monkeypatch.setattr(collector, "snapshot", synchronized_snapshot)
        monkeypatch.setattr(collector, "_log_files", lambda: ())
        collectors.append(collector)
    monkeypatch.setattr(diagnostics, "datetime", FrozenDatetime)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(collector.export, tmp_path) for collector in collectors]
        results = [future.result(timeout=10) for future in futures]

    assert len(set(results)) == 2
    assert len(list(tmp_path.glob("*.zip"))) == 2
    for mode, path in zip(("gui", "tui"), results, strict=True):
        with ZipFile(path) as archive:
            payload = json.loads(archive.read("diagnostics.json"))
        assert payload["application"]["runtime_mode"] == mode
    assert not list(tmp_path.glob(".*.tmp"))


def test_export_bounds_large_logs_and_keeps_recent_complete_lines(tmp_path, monkeypatch):
    collector = _collector(Settings(), None, None, None)
    log_paths = []
    for name in ("runtime.log", "runtime.log.1", "runtime.log.2", "crash.log"):
        path = tmp_path / name
        path.write_bytes(
            b"old content must be omitted\n"
            + b"x" * (3 * 1024 * 1024)
            + f"\ncontroller_lock_serial={CONTROLLER_SERIAL}\nrecent event\n".encode()
        )
        log_paths.append(path)
    monkeypatch.setattr(collector, "_log_files", lambda: tuple(log_paths))

    bundle = collector.export(tmp_path / "bundles")

    with ZipFile(bundle) as archive:
        for path in log_paths:
            payload = archive.read(f"logs/{path.name}")
            assert len(payload) < 2 * 1024 * 1024
            assert b"old content must be omitted" not in payload
            assert CONTROLLER_SERIAL.encode() not in payload
            assert b"<controller-id sha256:" in payload
            assert payload.endswith(b"recent event\n")


def test_log_tail_discards_partial_identifier_before_sanitizing(tmp_path, monkeypatch):
    collector = _collector(Settings(), None, None, None)
    path = tmp_path / "runtime.log"
    # The 2 MiB tail begins inside a labeled identifier. Keeping that fragment
    # would remove the label the sanitizer needs to recognize the sensitive value.
    fragment = b"secret-controller-suffix\n"
    trailing = b"recent event\n"
    limit = 2 * 1024 * 1024
    path.write_bytes(
        b"prefix that falls outside the tail\nserial="
        + b"a" * 32
        + fragment
        + b"." * (limit - len(fragment) - len(trailing))
        + trailing
    )
    monkeypatch.setattr(collector, "_log_files", lambda: (path,))

    payload = collector._log_payloads()[0][1]

    assert b"secret-controller-suffix" not in payload
    assert payload.endswith(trailing)


def test_log_tail_omits_oversized_unterminated_record(tmp_path, monkeypatch):
    collector = _collector(Settings(), None, None, None)
    path = tmp_path / "crash.log"
    path.write_bytes(b"serial=" + b"private" * (512 * 1024))
    monkeypatch.setattr(collector, "_log_files", lambda: (path,))

    payload = collector._log_payloads()[0][1]

    assert b"private" not in payload
    assert len(payload) < 1024


def test_log_read_requests_are_bounded(tmp_path, monkeypatch):
    collector = _collector(Settings(), None, None, None)
    path = tmp_path / "runtime.log"
    limit = 2 * 1024 * 1024

    class BoundedRead(BytesIO):
        def read(self, size=-1):
            assert 0 <= size <= limit
            return super().read(size)

    monkeypatch.setattr(collector, "_log_files", lambda: (path,))
    monkeypatch.setattr(
        Path,
        "open",
        lambda _path, _mode: BoundedRead(b"old\n" + b"x" * (limit + 1) + b"\nrecent\n"),
    )

    payload = collector._log_payloads()[0][1]

    assert payload == b"recent\n"


@pytest.mark.parametrize("record", [b"serial=x\n", b"\xff\xff\xff\n"])
def test_sanitized_log_stays_bounded_when_encoding_expands(tmp_path, monkeypatch, record):
    collector = _collector(Settings(), None, None, None)
    path = tmp_path / "runtime.log"
    limit = 2 * 1024 * 1024
    path.write_bytes(record * (limit // len(record)) + b"recent\n")
    monkeypatch.setattr(collector, "_log_files", lambda: (path,))

    payload = collector._log_payloads()[0][1]

    assert len(payload) <= limit
    assert payload.endswith(b"recent\n")
    assert payload.decode("utf-8").splitlines()[0] in {
        "serial=<controller-id sha256:2d711642b726>",
        "\ufffd\ufffd\ufffd",
    }


@pytest.mark.parametrize("phase", ["snapshot", "write", "publish"])
def test_failed_export_removes_reserved_name_and_temporary(tmp_path, monkeypatch, phase):
    from modules import diagnostics

    collector = _collector(Settings(), None, None, None)
    monkeypatch.setattr(collector, "_log_files", lambda: ())
    previous = tmp_path / "previous.zip"
    previous.write_bytes(b"previous bundle")

    def fail(*_args):
        raise OSError("simulated export failure")

    if phase == "snapshot":
        monkeypatch.setattr(collector, "snapshot", fail)
    elif phase == "write":
        original_write = diagnostics.ZipFile.writestr

        def fail_after_snapshot(archive, name, data):
            if name == "README.txt":
                fail()
            return original_write(archive, name, data)

        monkeypatch.setattr(diagnostics.ZipFile, "writestr", fail_after_snapshot)
    else:
        monkeypatch.setattr(diagnostics.os, "replace", fail)

    with pytest.raises(OSError, match="simulated export failure"):
        collector.export(tmp_path)

    assert list(tmp_path.iterdir()) == [previous]
    assert previous.read_bytes() == b"previous bundle"
