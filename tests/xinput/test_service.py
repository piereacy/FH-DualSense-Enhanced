import threading
import time
from dataclasses import replace

from modules.config.settings import Settings
from modules.dualsense.hidhide import HidHidePhase, HidHideSnapshot
from modules.dualsense.input_state import DPad, DualSenseButton, DualSenseInputState
from modules.xinput.bridge import BridgeSnapshot, BridgeStatus, InputOwner, XInputBridge
from modules.xinput.report import XUSBButton, XUSBReport
from modules.xinput.driver import InstallResult, InstallStatus
from modules.xinput.mapping import DEFAULT_BUTTON_MAPPING
from modules.xinput.gyro import DEFAULT_GYRO_MAPPING, GyroMode
from modules.xinput.service import (
    STEAM_PLATFORM,
    XBOX_APP_PLATFORM,
    XInputBridgeService as RuntimeXInputBridgeService,
    custom_xinput_mapping_available,
    hidhide_presentation,
    normalize_forza_platform,
    xbox_isolation_ready,
)


def test_custom_mapping_is_available_only_for_the_xbox_app_platform():
    assert custom_xinput_mapping_available(XBOX_APP_PLATFORM) is True
    assert custom_xinput_mapping_available(" XBOX_APP ") is True
    assert custom_xinput_mapping_available(STEAM_PLATFORM) is False
    assert custom_xinput_mapping_available("future-platform") is False


class _Bridge:
    def __init__(self, *, target_connected=False):
        self.calls = []
        self.published = []
        self.mappings = []
        self.gyro_mappings = []
        self._snapshot = BridgeSnapshot(
            status=(
                BridgeStatus.ACTIVE
                if target_connected
                else BridgeStatus.WAITING_CONTROLLER
            ),
            target_connected=target_connected,
        )
        self._target_state_callback = None

    def set_button_mapping(self, mapping):
        self.mappings.append(mapping)

    def set_gyro_mapping(self, mapping):
        self.gyro_mappings.append(mapping)

    def start(self):
        self.calls.append("start")

    def stop(self):
        self.calls.append("stop")

    def publish_latest(self, _state, _received_at):
        self.published.append((_state, _received_at))

    def snapshot(self):
        return self._snapshot

    def set_target_state_callback(self, callback):
        self._target_state_callback = callback

    def set_target_connected(self, connected):
        connected = bool(connected)
        self._snapshot = replace(
            self._snapshot,
            status=(
                BridgeStatus.ACTIVE
                if connected
                else BridgeStatus.WAITING_CONTROLLER
            ),
            target_connected=connected,
        )
        if self._target_state_callback is not None:
            self._target_state_callback(connected)


class _Backend:
    def __init__(self):
        self.connected = True
        self.consumers = []
        self.visibility_observers = []
        self.lifecycle = []

    def open(self):
        self.lifecycle.append("open")

    def close(self):
        self.lifecycle.append("close")

    def set_input_consumer(self, consumer):
        self.consumers.append(consumer)

    def set_device_visibility_observer(self, observer):
        self.visibility_observers.append(observer)

class _HidHide:
    def __init__(self):
        self.calls = []
        self._snapshot = HidHideSnapshot()
        self.started = False

    def start(self):
        self.calls.append("start")
        self.started = True
        self._snapshot = HidHideSnapshot(phase=HidHidePhase.READY)
        return self._snapshot

    def prepare_application_access(self):
        self.calls.append("prepare_access")
        self._snapshot = HidHideSnapshot(phase=HidHidePhase.READY)
        return self._snapshot

    def stop(self, *, remove_allowlist=False):
        self.calls.append(("stop", remove_allowlist))
        self.started = False
        self._snapshot = HidHideSnapshot()
        return self._snapshot

    def snapshot(self):
        return self._snapshot

    def register_device(self, info):
        self.calls.append(("register", info))
        self._snapshot = HidHideSnapshot(
            phase=HidHidePhase.ACTIVE,
            hidden_device_count=1,
        )
        return True


class _RetryTimer:
    def __init__(self, delay, callback):
        self.delay = delay
        self.callback = callback
        self.daemon = False
        self.started = False
        self.cancelled = False

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        # Also exercises a timer callback that was already queued at cancel.
        self.callback()


class _InputActivityMonitor:
    available = True

    def __init__(self):
        self.calls = []

    def start(self):
        self.calls.append("start")
        return True

    def stop(self):
        self.calls.append("stop")


XInputBridgeService = RuntimeXInputBridgeService


def test_unknown_platform_normalizes_to_safe_steam_default():
    assert normalize_forza_platform("XBOX_APP") == XBOX_APP_PLATFORM
    assert normalize_forza_platform("future-store") == STEAM_PLATFORM


def test_keyboard_owner_does_not_block_hidhide_bootstrap_or_first_real_press():
    reports = []
    activity = threading.Event()
    activity.set()

    def poll_activity():
        pending = activity.is_set()
        activity.clear()
        return pending

    class Target:
        def update(self, report):
            reports.append(bytes(report))

        def close(self):
            pass

    class Client:
        def connect(self):
            pass

        def create_x360_target(self):
            return Target()

        def close(self):
            pass

    class Backend(_Backend):
        def set_device_visibility_observer(self, observer):
            super().set_device_visibility_observer(observer)
            if observer is not None:
                observer({"path": b"synthetic-dualsense"})

    def wait_for(predicate):
        deadline = time.monotonic() + 1.0
        while not predicate():
            assert time.monotonic() < deadline, "XInput isolation did not converge"
            time.sleep(0.002)

    bridge = XInputBridge(client_factory=Client, keyboard_mouse_activity=poll_activity)
    service = XInputBridgeService(
        Settings(preferred_forza_platform=XBOX_APP_PLATFORM, enable_hidhide=True),
        bridge=bridge,
        hidhide_service=_HidHide(),
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
        hidhide_retry_timer_factory=_RetryTimer,
    )
    backend = Backend()
    state = DualSenseInputState(128, 128, 128, 128, 0, 0, DPad.NEUTRAL,
                               frozenset({DualSenseButton.CROSS}))
    try:
        service.sync(backend)
        wait_for(lambda: bridge.snapshot().input_owner is InputOwner.KEYBOARD_MOUSE)
        backend.consumers[-1](state, time.monotonic())
        wait_for(service.isolation_confirmed)
        assert reports == [bytes(12)]
        assert bridge.snapshot().input_owner is InputOwner.KEYBOARD_MOUSE
        backend.consumers[-1](state, time.monotonic())
        wait_for(lambda: bridge.snapshot().forwarded_reports == 1)
        assert XUSBReport.from_buffer_copy(reports[-1]).wButtons & XUSBButton.A
        assert bridge.snapshot().input_owner is InputOwner.CONTROLLER
    finally:
        service.stop()


def test_steam_mode_never_starts_bridge_or_attaches_input_consumer():
    settings = Settings()
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        platform_supported=lambda: True,
    )

    service.sync(backend)

    assert bridge.calls == ["stop"]
    assert backend.consumers == []
    assert backend.lifecycle == []
    assert service.snapshot().status is BridgeStatus.DISABLED


def test_xbox_app_mode_starts_bridge_and_attaches_latest_publisher():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        platform_supported=lambda: True,
    )

    service.sync(backend)

    assert bridge.calls == ["stop", "start"]
    assert len(backend.consumers) == 1 and callable(backend.consumers[0])
    assert bridge.mappings[-1] == DEFAULT_BUTTON_MAPPING
    assert bridge.gyro_mappings[-1] == DEFAULT_GYRO_MAPPING


def test_xbox_input_stays_neutral_until_the_current_dualsense_is_hidden():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM, enable_hidhide=True)
    bridge = _Bridge(target_connected=True)
    backend = _Backend()
    isolation = _HidHide()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
    )
    service.sync(backend)
    publisher = backend.consumers[-1]
    state = DualSenseInputState(
        left_x=190,
        left_y=128,
        right_x=128,
        right_y=128,
        left_trigger=30,
        right_trigger=0,
        dpad=DPad.NORTH,
        buttons=frozenset({DualSenseButton.CROSS}),
    )

    publisher(state, 1.0)
    neutral = bridge.published[-1][0]
    assert neutral.left_x == 128
    assert neutral.left_trigger == 0
    assert neutral.dpad is DPad.NEUTRAL
    assert not neutral.buttons
    assert not service.isolation_confirmed()

    assert backend.visibility_observers[-1]({"path": b"controller"})
    assert service.isolation_confirmed()
    publisher(state, 2.0)
    assert bridge.published[-1][0] is state

    isolation._snapshot = HidHideSnapshot(phase=HidHidePhase.READY)
    publisher(state, 3.0)
    assert bridge.published[-1][0] == neutral
    assert not service.verify_isolation()


def test_xbox_isolation_requires_a_live_target_controller_and_hidden_rule():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM, enable_hidhide=True)
    bridge = BridgeSnapshot(status=BridgeStatus.ACTIVE, target_connected=True)
    isolation = HidHideSnapshot(phase=HidHidePhase.ACTIVE, hidden_device_count=1)
    assert xbox_isolation_ready(settings, bridge, isolation, controller_connected=True)
    assert not xbox_isolation_ready(settings, bridge, isolation, controller_connected=False)
    assert not xbox_isolation_ready(
        settings, bridge, HidHideSnapshot(phase=HidHidePhase.READY), controller_connected=True
    )
    settings.enable_hidhide = False
    assert not xbox_isolation_ready(settings, bridge, isolation, controller_connected=True)


def test_custom_mapping_refresh_does_not_restart_the_bridge():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        platform_supported=lambda: True,
    )
    service.sync(backend)
    calls_before = list(bridge.calls)

    settings.enable_custom_xinput_mapping = True
    settings.xinput_mapping_cross = "y"
    mapping = service.refresh_button_mapping()

    assert bridge.calls == calls_before
    assert mapping.target_for("cross") == "y"
    assert bridge.mappings[-1] == mapping


def test_gyro_mapping_refresh_requires_master_and_child_switch_without_restart():
    settings = Settings(
        preferred_forza_platform=XBOX_APP_PLATFORM,
        enable_custom_xinput_mapping=False,
        enable_xinput_gyro=True,
        xinput_gyro_mode="camera",
        xinput_gyro_output_stick="right",
    )
    bridge = _Bridge()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        platform_supported=lambda: True,
    )
    service.sync(_Backend())
    calls_before = list(bridge.calls)

    mapping = service.refresh_gyro_mapping()

    assert bridge.calls == calls_before
    assert mapping.mode is GyroMode.OFF
    assert bridge.gyro_mappings[-1] == mapping

    settings.enable_custom_xinput_mapping = True
    settings.enable_xinput_gyro = False
    mapping = service.refresh_gyro_mapping()
    assert mapping.mode is GyroMode.OFF

    settings.enable_xinput_gyro = True
    mapping = service.refresh_gyro_mapping()
    assert bridge.calls == calls_before
    assert mapping.mode is GyroMode.CAMERA
    assert bridge.gyro_mappings[-1] == mapping

    settings.enable_custom_xinput_mapping = False
    service.refresh_button_mapping()
    assert bridge.calls == calls_before
    assert bridge.gyro_mappings[-1] == DEFAULT_GYRO_MAPPING


def test_switching_back_to_steam_detaches_before_bridge_stops():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(settings, bridge=bridge, platform_supported=lambda: True)
    service.sync(backend)
    settings.preferred_forza_platform = STEAM_PLATFORM

    service.sync(backend)

    assert backend.consumers[-1] is None
    assert bridge.calls[-1] == "stop"


def test_input_activity_monitor_runs_only_while_xbox_bridge_is_selected():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    monitor = _InputActivityMonitor()
    backend = _Backend()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        input_activity_monitor=monitor,
        platform_supported=lambda: True,
    )

    service.sync(backend)
    assert monitor.calls == ["stop", "start"]

    settings.preferred_forza_platform = STEAM_PLATFORM
    service.sync(backend)
    assert monitor.calls == ["stop", "start", "stop"]

    settings.preferred_forza_platform = XBOX_APP_PLATFORM
    service.sync(backend)
    service.stop()
    assert monitor.calls[-3:] == ["stop", "start", "stop"]


def test_dsx_backend_is_reported_as_incompatible_without_starting_bridge():
    class _DSXBackend:
        def open(self):
            pass

        def close(self):
            pass

    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    service = XInputBridgeService(settings, bridge=bridge, platform_supported=lambda: True)

    service.sync(_DSXBackend())

    snapshot = service.snapshot()
    assert snapshot.status is BridgeStatus.ERROR
    assert "disable DSX" in snapshot.last_error
    assert "start" not in bridge.calls


def test_non_windows_x64_platform_stays_disabled():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    service = XInputBridgeService(settings, bridge=bridge, platform_supported=lambda: False)

    service.sync(_Backend())

    assert service.snapshot().status is BridgeStatus.DISABLED
    assert "Windows x64" in service.snapshot().last_error
    assert "start" not in bridge.calls


def test_stop_detaches_consumer_and_is_idempotent():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(settings, bridge=bridge, platform_supported=lambda: True)
    service.sync(backend)

    service.stop()
    service.stop()

    assert backend.consumers[-1] is None


def test_confirmed_driver_install_exposes_installing_then_restarts_bridge():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(settings, bridge=bridge, platform_supported=lambda: True)
    service.sync(backend)
    observed = []

    result = service.install_driver(
        lambda: observed.append(service.snapshot().status)
        or InstallResult(InstallStatus.SUCCESS, exit_code=0)
    )

    assert observed == [BridgeStatus.INSTALLING]
    assert result.status is InstallStatus.SUCCESS
    assert bridge.calls[-1] == "start"
    assert callable(backend.consumers[-1])


def test_cancelled_and_restart_required_installs_keep_explicit_status():
    for install_status, bridge_status in (
        (InstallStatus.CANCELLED, BridgeStatus.DRIVER_MISSING),
        (InstallStatus.RESTART_REQUIRED, BridgeStatus.RESTART_REQUIRED),
        (InstallStatus.FAILED, BridgeStatus.ERROR),
    ):
        settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
        service = XInputBridgeService(
            settings,
            bridge=_Bridge(),
            platform_supported=lambda: True,
        )
        service.sync(_Backend())

        service.install_driver(
            lambda status=install_status: InstallResult(status, error="synthetic result")
        )

        assert service.snapshot().status is bridge_status
        assert service.snapshot().last_error == "synthetic result"


def test_hidhide_session_starts_only_after_vigem_is_ready_in_direct_hid_mode():
    settings = Settings(
        preferred_forza_platform=XBOX_APP_PLATFORM,
        enable_hidhide=True,
    )
    bridge = _Bridge()
    backend = _Backend()
    isolation = _HidHide()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
    )

    service.sync(backend)

    assert isolation.calls
    assert "prepare_access" in isolation.calls
    assert "start" not in isolation.calls
    assert not any(observer is not None for observer in backend.visibility_observers)

    bridge.set_target_connected(True)
    service.sync_hidhide()

    assert isolation.calls[-1] == "start"
    observer = backend.visibility_observers[-1]
    assert observer.__self__ is isolation
    assert observer({"path": b"controller"}) is True
    assert isolation.calls[-1] == ("register", {"path": b"controller"})


def test_hidhide_application_access_precedes_hid_open_without_a_virtual_target():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM, enable_hidhide=True)
    backend = _Backend()
    isolation = _HidHide()
    service = XInputBridgeService(
        settings,
        bridge=_Bridge(),
        hidhide_service=isolation,
        platform_supported=lambda: True,
    )

    assert service.prepare_controller_access(backend).phase is HidHidePhase.READY
    assert isolation.calls == ["prepare_access"]
    assert backend.visibility_observers == []
    assert "start" not in isolation.calls

    settings.preferred_forza_platform = STEAM_PLATFORM
    service.prepare_controller_access(backend)
    assert isolation.calls == ["prepare_access"]


def test_hidhide_session_is_cleared_when_the_actual_virtual_target_is_lost():
    settings = Settings(
        preferred_forza_platform=XBOX_APP_PLATFORM,
        enable_hidhide=True,
    )
    bridge = _Bridge(target_connected=True)
    backend = _Backend()
    isolation = _HidHide()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
    )
    service.sync(backend)
    assert isolation.calls[-1] == "start"

    bridge.set_target_connected(False)
    service.sync_hidhide()

    assert backend.visibility_observers[-1] is None
    assert isolation.calls[-2:] == [("stop", False), "prepare_access"]


def test_hidhide_does_not_hide_without_a_ready_virtual_controller_driver():
    settings = Settings(
        preferred_forza_platform=XBOX_APP_PLATFORM,
        enable_hidhide=True,
    )
    backend = _Backend()
    isolation = _HidHide()
    bridge = _Bridge()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: False,
        platform_supported=lambda: True,
    )

    service.sync(backend)
    bridge.set_target_connected(True)
    service.sync_hidhide()

    assert isolation.calls
    assert "prepare_access" in isolation.calls
    assert "start" not in isolation.calls
    assert not any(observer is not None for observer in backend.visibility_observers)


def test_hidhide_enable_retries_after_a_transient_driver_probe_failure():
    settings = Settings(
        preferred_forza_platform=XBOX_APP_PLATFORM,
        enable_hidhide=True,
    )
    driver_ready = [False]
    isolation = _HidHide()
    service = XInputBridgeService(
        settings,
        bridge=_Bridge(target_connected=True),
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: driver_ready[0],
        platform_supported=lambda: True,
    )
    service.sync(_Backend())
    assert "start" not in isolation.calls

    driver_ready[0] = True
    service.sync_hidhide()
    assert isolation.calls[-1] == "start"


def test_hidhide_retries_automatically_after_configuration_client_releases_driver():
    class BusyHidHide(_HidHide):
        busy = True

        def start(self):
            if self.busy:
                self.calls.append("busy_start")
                self._snapshot = HidHideSnapshot(
                    phase=HidHidePhase.UNAVAILABLE,
                    last_error="HidHide control device is busy",
                )
                return self._snapshot
            return super().start()

    timers = []

    def make_timer(delay, callback):
        timer = _RetryTimer(delay, callback)
        timers.append(timer)
        return timer

    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM, enable_hidhide=True)
    backend = _Backend()
    isolation = BusyHidHide()
    service = XInputBridgeService(
        settings,
        bridge=_Bridge(target_connected=True),
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
        hidhide_retry_timer_factory=make_timer,
    )

    service.sync(backend)
    assert isolation.calls[-1] == "busy_start"
    assert len(timers) == 1 and timers[0].started and timers[0].daemon
    assert timers[0].delay == 5.0
    assert not any(observer is not None for observer in backend.visibility_observers)

    isolation.busy = False
    timers[0].fire()
    assert isolation.calls[-1] == "start"
    assert backend.visibility_observers[-1].__self__ is isolation
    assert len(timers) == 2 and timers[1].started


def test_hidhide_access_retry_stops_when_isolation_is_switched_off():
    class BusyAccess(_HidHide):
        def prepare_application_access(self):
            self.calls.append("busy_access")
            self._snapshot = HidHideSnapshot(phase=HidHidePhase.UNAVAILABLE)
            return self._snapshot

    timers = []

    def make_timer(delay, callback):
        timer = _RetryTimer(delay, callback)
        timers.append(timer)
        return timer

    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM, enable_hidhide=True)
    isolation = BusyAccess()
    service = XInputBridgeService(
        settings,
        bridge=_Bridge(),
        hidhide_service=isolation,
        platform_supported=lambda: True,
        hidhide_retry_timer_factory=make_timer,
    )
    service.sync(_Backend())
    assert len(timers) == 1 and timers[0].started

    settings.enable_hidhide = False
    service.sync_hidhide()
    assert timers[0].cancelled is True
    before = list(isolation.calls)
    timers[0].fire()
    assert isolation.calls == before
    assert service.hidhide_snapshot().phase is HidHidePhase.DISABLED


def test_hidhide_access_retries_without_hiding_before_target_connects():
    class BusyAccess(_HidHide):
        busy = True

        def prepare_application_access(self):
            if self.busy:
                self.calls.append("busy_access")
                self._snapshot = HidHideSnapshot(phase=HidHidePhase.UNAVAILABLE)
                return self._snapshot
            return super().prepare_application_access()

    timers = []

    def make_timer(delay, callback):
        timer = _RetryTimer(delay, callback)
        timers.append(timer)
        return timer

    isolation = BusyAccess()
    backend = _Backend()
    service = XInputBridgeService(
        Settings(preferred_forza_platform=XBOX_APP_PLATFORM, enable_hidhide=True),
        bridge=_Bridge(),
        hidhide_service=isolation,
        platform_supported=lambda: True,
        hidhide_retry_timer_factory=make_timer,
    )
    service.sync(backend)
    assert isolation.calls[-1] == "busy_access"
    assert len(timers) == 1

    isolation.busy = False
    timers[0].fire()
    assert isolation.calls[-1] == "prepare_access"
    assert service.hidhide_snapshot().phase is HidHidePhase.READY
    assert "start" not in isolation.calls
    assert not any(observer is not None for observer in backend.visibility_observers)
    assert len(timers) == 1


def test_hidhide_requires_a_healthy_connected_bridge_snapshot():
    settings = Settings(
        preferred_forza_platform=XBOX_APP_PLATFORM,
        enable_hidhide=True,
    )
    bridge = _Bridge(target_connected=True)
    bridge._snapshot = replace(bridge.snapshot(), status=BridgeStatus.ERROR)
    isolation = _HidHide()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
    )

    service.sync(_Backend())

    assert "start" not in isolation.calls


def test_hidhide_toggle_is_hot_applied_without_restarting_virtual_target():
    settings = Settings(
        preferred_forza_platform=XBOX_APP_PLATFORM,
        enable_hidhide=True,
    )
    bridge = _Bridge(target_connected=True)
    backend = _Backend()
    isolation = _HidHide()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
    )
    service.sync(backend)
    bridge_calls = list(bridge.calls)

    settings.enable_hidhide = False
    snapshot = service.sync_hidhide()

    assert bridge.calls == bridge_calls
    assert backend.visibility_observers[-1] is None
    assert isolation.calls[-1] == ("stop", True)
    assert snapshot.phase is HidHidePhase.DISABLED


def test_overlapping_hidhide_toggles_finish_in_the_latest_setting():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    backend = _Backend()
    isolation = _HidHide()
    driver_probe_entered = threading.Event()
    release_driver_probe = threading.Event()

    def driver_ready():
        driver_probe_entered.set()
        assert release_driver_probe.wait(1.0)
        return True

    service = XInputBridgeService(
        settings,
        bridge=_Bridge(target_connected=True),
        hidhide_service=isolation,
        hidhide_driver_ready=driver_ready,
        platform_supported=lambda: True,
    )
    service.sync(backend)
    isolation.calls.clear()

    settings.enable_hidhide = True
    enable_thread = threading.Thread(target=service.sync_hidhide)
    enable_thread.start()
    assert driver_probe_entered.wait(1.0)

    settings.enable_hidhide = False
    disable_thread = threading.Thread(target=service.sync_hidhide)
    disable_thread.start()
    release_driver_probe.set()
    enable_thread.join(timeout=1.0)
    disable_thread.join(timeout=1.0)

    assert not enable_thread.is_alive()
    assert not disable_thread.is_alive()
    assert service.hidhide_snapshot().phase is HidHidePhase.DISABLED
    assert backend.visibility_observers[-1] is None
    assert isolation.calls[-1] == ("stop", True)


def test_hidhide_never_starts_in_steam_or_dsx_mode():
    for backend in (_Backend(), object()):
        settings = Settings(
            preferred_forza_platform=(
                STEAM_PLATFORM if isinstance(backend, _Backend) else XBOX_APP_PLATFORM
            ),
            enable_hidhide=True,
        )
        isolation = _HidHide()
        service = XInputBridgeService(
            settings,
            bridge=_Bridge(),
            hidhide_service=isolation,
            hidhide_driver_ready=lambda: True,
            platform_supported=lambda: True,
        )

        service.sync(backend)

        assert "start" not in isolation.calls


def test_hidhide_presentation_distinguishes_hidden_and_paused_states():
    def translate(value):
        return value

    settings = Settings(
        preferred_forza_platform=XBOX_APP_PLATFORM,
        enable_hidhide=True,
    )
    bridge = BridgeSnapshot(status=BridgeStatus.WAITING_CONTROLLER)

    hidden = hidhide_presentation(
        settings,
        bridge,
        HidHideSnapshot(phase=HidHidePhase.ACTIVE, hidden_device_count=2),
        translate,
    )
    assert hidden.title == "Physical DualSense hidden from games"
    assert "2" in hidden.detail

    manual = hidhide_presentation(
        settings,
        bridge,
        HidHideSnapshot(
            phase=HidHidePhase.ACTIVE,
            hidden_device_count=1,
            manual_configuration=True,
        ),
        translate,
    )
    assert manual.title == "Manual HidHide rules verified"
    assert "restart" in manual.detail

    waiting = hidhide_presentation(
        settings,
        BridgeSnapshot(status=BridgeStatus.WAITING_CONTROLLER),
        HidHideSnapshot(),
        translate,
    )
    assert waiting.title == "HidHide isolation is waiting"
    assert "Connect or reconnect" in waiting.detail

    settings.preferred_forza_platform = STEAM_PLATFORM
    paused = hidhide_presentation(settings, bridge, HidHideSnapshot(), translate)
    assert paused.title == "HidHide isolation is paused"
    assert "Xbox App" in paused.detail

    settings.enable_hidhide = False
    cleanup_error = hidhide_presentation(
        settings,
        bridge,
        HidHideSnapshot(
            phase=HidHidePhase.ERROR,
            last_error="session cleanup pending",
        ),
        translate,
    )
    assert cleanup_error.title == "HidHide isolation error"
    assert cleanup_error.detail == "session cleanup pending"
