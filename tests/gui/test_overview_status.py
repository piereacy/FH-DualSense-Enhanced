from types import SimpleNamespace
from pathlib import Path

from modules.config.settings import Settings
from modules.forzahorizon import TelemetryPhase, TelemetrySnapshot
from modules.gui.overview_status import (
    controller_status,
    fh6_launch_button_status,
    profile_status,
    telemetry_status,
    update_status,
)
from modules.update import UpdatePhase, UpdateSnapshot


def _t(value: str) -> str:
    return value


class _Listener:
    def __init__(self, snapshot):
        self._snapshot = snapshot

    def snapshot(self):
        return self._snapshot


class _Updater:
    def __init__(self, snapshot=UpdateSnapshot(), *, supported=True):
        self._snapshot = snapshot
        self.supported = supported

    def snapshot(self):
        return self._snapshot


def test_controller_card_distinguishes_hid_dsx_reconnect_and_errors():
    settings = Settings()
    connected = SimpleNamespace(connected=True, transport="bluetooth")
    assert controller_status(connected, settings, _t).value == "Connected"
    assert controller_status(connected, settings, _t).hint == "Transport: BLUETOOTH"

    settings.enable_reconnect = True
    settings.reconnect_interval_s = 2.5
    waiting = controller_status(None, settings, _t)
    assert waiting.value == "Waiting for controller"
    assert waiting.hint == "Retrying every 2.5 seconds"

    settings.use_dsx = True
    dsx = controller_status(SimpleNamespace(connected=True), settings, _t)
    assert dsx.value == "DSX enabled"
    assert "127.0.0.1:6969" in dsx.hint
    assert "no acknowledgement" in dsx.hint

    failed = controller_status(None, settings, _t, error="open failed")
    assert failed.value == "Controller backend error"
    assert failed.hint == "open failed"


def test_telemetry_card_maps_waiting_receiving_lost_and_bind_failure():
    settings = Settings()
    waiting = TelemetrySnapshot(
        TelemetryPhase.WAITING, 0, None, "", None, settings.udp_port
    )
    assert telemetry_status(_Listener(waiting), settings, _t).value == "Waiting for packets"

    receiving = TelemetrySnapshot(
        TelemetryPhase.RECEIVING, 42, 0.1, "192.168.1.50", 5300, settings.udp_port
    )
    visible = telemetry_status(_Listener(receiving), settings, _t)
    assert visible.value == "Receiving telemetry"
    assert visible.hint == "Packet 42 from 192.168.1.50"

    lost = TelemetrySnapshot(
        TelemetryPhase.LOST, 42, 2.25, "192.168.1.50", 5300, settings.udp_port
    )
    visible = telemetry_status(_Listener(lost), settings, _t)
    assert visible.value == "Telemetry lost"
    assert visible.hint == "Last packet 2.2 seconds ago on UDP 5300"

    failed = telemetry_status(None, settings, _t, error="address already in use")
    assert failed.value == "UDP bind failed"
    assert failed.hint == "address already in use"


def test_profile_and_update_cards_never_fall_back_to_placeholder_dash():
    assert profile_status("Default", _t).value == "Default"
    assert profile_status("", _t).value == "(none)"
    assert profile_status("", _t, error="bad JSON").value == "Profile unavailable"

    settings = Settings()
    assert update_status(_Updater(), settings, _t).value == "Waiting for automatic check"
    settings.check_for_updates = False
    assert update_status(_Updater(), settings, _t).value == "Update checks disabled"
    assert update_status(_Updater(supported=False), settings, _t).value == (
        "Unavailable in this runtime"
    )

    downloading = UpdateSnapshot(
        phase=UpdatePhase.DOWNLOADING,
        downloaded=25,
        total=100,
    )
    visible = update_status(_Updater(downloading), settings, _t)
    assert visible.value == "Downloading update"
    assert visible.hint == "Downloaded 25%"

    error = UpdateSnapshot(phase=UpdatePhase.ERROR, message="network unavailable")
    visible = update_status(_Updater(error), settings, _t)
    assert visible.value == "Update failed"
    assert visible.hint == "network unavailable"

    long_error = UpdateSnapshot(
        phase=UpdatePhase.ERROR,
        message=(
            "network request failed: <urlopen error "
            "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol>"
        ),
    )
    visible = update_status(_Updater(long_error), settings, _t)
    assert len(visible.hint) <= 64
    assert "UNEXPECTED_EOF" in visible.hint
    assert visible.hint.endswith("…")


def test_fh6_launch_button_prioritizes_running_launching_scan_and_ready_states():
    status = fh6_launch_button_status(
        _t,
        supported=True,
        scanning=False,
        installed=True,
        running=False,
        launching=False,
    )
    assert status.label == "Launch FH6"
    assert status.enabled is True

    cases = (
        ({"running": True}, "FH6 is running"),
        ({"launching": True}, "Starting FH6..."),
        ({"scanning": True}, "Finding FH6..."),
        ({"supported": False, "installed": True}, "FH6 not found"),
        ({"installed": False}, "FH6 not found"),
    )
    defaults = {
        "supported": True,
        "scanning": False,
        "installed": True,
        "running": False,
        "launching": False,
    }
    for override, label in cases:
        visible = fh6_launch_button_status(_t, **(defaults | override))
        assert visible.label == label
        assert visible.enabled is False


def test_gui_refreshes_overview_immediately_and_on_the_runtime_status_tick():
    root = Path(__file__).resolve().parents[2]
    overview = (root / "src/modules/gui/overview_tab.py").read_text(encoding="utf-8")
    main = (root / "src/modules/gui/main.py").read_text(encoding="utf-8")

    assert "app.register_refresh(self.refresh)\n        self.refresh()" in overview
    tick = main.split("def _tick_status(self):", 1)[1].split("def _refresh_update_badge", 1)[0]
    assert "self.overview_tab.refresh()" in tick


def test_overview_launches_fh6_only_from_the_explicit_async_button():
    root = Path(__file__).resolve().parents[2]
    overview = (root / "src/modules/gui/overview_tab.py").read_text(encoding="utf-8")

    assert "command=self._launch_fh6" in overview
    assert "columnspan=2" in overview
    assert "launch_fh6_via_steam(install)" in overview
    assert 'name="fhds-fh6-steam-launch"' in overview
    assert "FH6_LAUNCH_TIMEOUT_S = 20.0" in overview
    assert "queue.SimpleQueue" in overview
    assert "_fh6_scan_results.put(install)" in overview
    assert "_fh6_launch_results.put(error)" in overview
    assert "and self._fh6_install is None" in overview
    assert "root.after" not in overview
    assert "os.startfile" not in overview
