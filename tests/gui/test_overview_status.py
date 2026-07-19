from types import SimpleNamespace
from pathlib import Path

from modules.config.settings import Settings
from modules.forzahorizon import (
    ForzaInstall,
    TelemetryPhase,
    TelemetrySnapshot,
    get_forza_game,
)
from modules.gui.overview_tab import OverviewTab
from modules.gui.overview_status import (
    controller_status,
    forza_launch_button_status,
    profile_status,
    should_scan_forza_install,
    telemetry_status,
    update_status,
    xinput_bridge_status,
)
from modules.update import UpdatePhase, UpdateSnapshot
from modules.xinput.bridge import BridgeSnapshot, BridgeStatus


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


class _XInput:
    def __init__(self, snapshot):
        self._snapshot = snapshot

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


def test_xinput_status_distinguishes_platform_driver_active_stale_and_error():
    steam = xinput_bridge_status(None, "steam", _t)
    assert steam.value == "Steam Input mode"
    assert steam.hint == "XInput bridge is off"

    missing = xinput_bridge_status(
        _XInput(BridgeSnapshot(status=BridgeStatus.DRIVER_MISSING)),
        "xbox_app",
        _t,
    )
    assert missing.value == "ViGEmBus required"

    active = xinput_bridge_status(
        _XInput(
            BridgeSnapshot(
                status=BridgeStatus.ACTIVE,
                forwarded_reports=42,
            )
        ),
        "xbox_app",
        _t,
    )
    assert active.value == "Xbox 360 controller active"
    assert active.hint == "Forwarded 42 input reports"

    stale = xinput_bridge_status(
        _XInput(BridgeSnapshot(status=BridgeStatus.STALE)),
        "xbox_app",
        _t,
    )
    assert stale.value == "Controller input paused"

    error = xinput_bridge_status(
        _XInput(BridgeSnapshot(status=BridgeStatus.ERROR, last_error="bad target")),
        "xbox_app",
        _t,
    )
    assert error.value == "XInput bridge error"
    assert error.hint == "bad target"


def test_forza_launch_button_prioritizes_running_launching_scan_and_ready_states():
    status = forza_launch_button_status(
        _t,
        game_label="FH5",
        supported=True,
        scanning=False,
        installed=True,
        running=False,
        launching=False,
    )
    assert status.label == "Launch FH5"
    assert status.enabled is True

    cases = (
        ({"running": True}, "FH5 is running"),
        ({"launching": True}, "Starting FH5..."),
        ({"scanning": True}, "Finding FH5..."),
        ({"supported": False, "installed": True}, "FH5 not found"),
        ({"installed": False}, "FH5 not found"),
    )
    defaults = {
        "supported": True,
        "scanning": False,
        "installed": True,
        "running": False,
        "launching": False,
    }
    for override, label in cases:
        visible = forza_launch_button_status(
            _t,
            game_label="FH5",
            **(defaults | override),
        )
        assert visible.label == label
        assert visible.enabled is False


def test_steam_discovery_stops_after_success_and_retries_missing_after_30_seconds():
    base = dict(
        supported=True,
        installed=False,
        scanning=False,
        launching=False,
        last_scan=100.0,
        retry_interval=30.0,
    )
    assert should_scan_forza_install(**base, has_result=False, now=100.0)
    assert not should_scan_forza_install(**base, has_result=True, now=129.999)
    assert should_scan_forza_install(**base, has_result=True, now=130.0)
    assert not should_scan_forza_install(
        **(base | {"installed": True}),
        has_result=True,
        now=1000.0,
    )


def test_gui_refreshes_overview_immediately_and_on_the_runtime_status_tick():
    root = Path(__file__).resolve().parents[2]
    overview = (root / "src/modules/gui/overview_tab.py").read_text(encoding="utf-8")
    main = (root / "src/modules/gui/main.py").read_text(encoding="utf-8")

    assert "app.register_refresh(self.refresh)\n        self.refresh()" in overview
    tick = main.split("def _tick_status(self):", 1)[1].split("def _refresh_update_badge", 1)[0]
    assert "self.overview_tab.refresh()" in tick


def test_update_notice_dot_is_drawn_directly_on_the_nav_button_canvas():
    root = Path(__file__).resolve().parents[2]
    main = (root / "src/modules/gui/main.py").read_text(encoding="utf-8")
    widgets = (root / "src/modules/gui/widgets.py").read_text(encoding="utf-8")

    assert "btn = W.NavButton(" in main
    assert "button.set_notice_visible(" in main
    assert "class NavButton(ctk.CTkButton):" in widgets
    assert "self._canvas.create_oval(" in widgets
    assert 'fill="white"' in widgets
    assert 'text="●"' not in main


def test_overview_uses_an_explicit_async_split_button_for_selected_game():
    root = Path(__file__).resolve().parents[2]
    overview = (root / "src/modules/gui/overview_tab.py").read_text(encoding="utf-8")

    assert "command=self._launch_selected_game" in overview
    assert "command=self._show_forza_game_menu" in overview
    assert "add_radiobutton" in overview
    assert "columnspan=2" in overview
    assert "launch_forza_via_steam(install)" in overview
    assert "launch_forza_via_xbox_app(game)" in overview
    assert 'name=f"fhds-{key}-{platform}-launch"' in overview
    assert "FORZA_LAUNCH_TIMEOUT_S = 20.0" in overview
    assert "queue.SimpleQueue" in overview
    assert "_game_scan_results.put((key, serial, install))" in overview
    assert "_game_launch_results.put((key, platform, error, direct))" in overview
    assert "discover_forza_install(game, cached_path)" in overview
    scan_worker = overview.split("def _start_game_scan", 1)[1].split(
        "def _apply_game_scan", 1
    )[0]
    launch_worker = overview.split("def _launch_selected_game", 1)[1].split(
        "def _finish_game_launch", 1
    )[0]
    assert "root.after" not in scan_worker
    assert "root.after" not in launch_worker
    assert "os.startfile" not in overview


class _ChoiceVar:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = value


def _overview_logic_only(settings=None):
    tab = OverviewTab.__new__(OverviewTab)
    tab.settings = settings or Settings()
    tab.app = SimpleNamespace(_tearing_down=False)
    tab._selected_game_key = "fh6"
    tab._selected_platform = "steam"
    tab._game_choice_var = _ChoiceVar()
    tab._game_installs = {}
    tab._game_scan_busy = {}
    tab._game_scan_has_result = {"fh4": False, "fh5": False, "fh6": False}
    tab._game_last_scan = {"fh4": 1.0, "fh5": 1.0, "fh6": 1.0}
    tab._game_path_hints = {"fh4": "", "fh5": "", "fh6": ""}
    tab._launching_game_key = None
    tab._launch_request_busy = False
    tab._game_launch_deadline = 0.0
    tab._refresh_forza_launch = lambda: None
    return tab


def test_game_menu_selection_persists_without_launching(monkeypatch):
    settings = Settings()
    tab = _overview_logic_only(settings)
    saves = []
    monkeypatch.setattr("modules.gui.overview_tab.preferences.save", saves.append)

    tab._select_forza_game("fh4")

    assert tab._selected_game_key == "fh4"
    assert tab._game_choice_var.value == "fh4"
    assert settings.preferred_forza_game == "fh4"
    assert saves == [settings]


def test_stale_scan_result_cannot_replace_the_new_selected_game():
    tab = _overview_logic_only()
    tab._selected_game_key = "fh5"
    tab._game_scan_busy = {"fh6": 7}
    old_install = ForzaInstall(get_forza_game("fh6"), Path("D:/FH6"), "test")

    tab._apply_game_scan("fh6", 7, old_install)

    assert "fh6" not in tab._game_scan_busy
    assert "fh6" not in tab._game_installs
