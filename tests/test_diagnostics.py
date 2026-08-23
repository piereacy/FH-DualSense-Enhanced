import json
import re
from dataclasses import dataclass
from zipfile import ZipFile

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
