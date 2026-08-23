import threading
import time
from dataclasses import replace

from modules.config.settings import Settings
from modules.dualsense.hidhide import HidHidePhase, HidHideSnapshot
from modules.forzahorizon.process_watch import ProcessScanError
from modules.xinput.bridge import BridgeSnapshot, BridgeStatus
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
)


def test_custom_mapping_is_available_only_for_the_xbox_app_platform():
    assert custom_xinput_mapping_available(XBOX_APP_PLATFORM) is True
    assert custom_xinput_mapping_available(" XBOX_APP ") is True
    assert custom_xinput_mapping_available(STEAM_PLATFORM) is False
    assert custom_xinput_mapping_available("future-platform") is False


class _Bridge:
    def __init__(self, *, target_connected=False):
        self.calls = []
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
        pass

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
        self.consumers = []
        self.visibility_observers = []
        self.lifecycle = []
        self.startup_pulse_cancellations = 0
        self.runtime_enabled = []

    def open(self):
        self.lifecycle.append("open")

    def close(self):
        self.lifecycle.append("close")

    def set_input_consumer(self, consumer):
        self.consumers.append(consumer)

    def set_device_visibility_observer(self, observer):
        self.visibility_observers.append(observer)

    def cancel_startup_pulse(self):
        self.startup_pulse_cancellations += 1

    def set_runtime_enabled(self, enabled):
        self.runtime_enabled.append(bool(enabled))


class _HidHide:
    def __init__(self):
        self.calls = []
        self._snapshot = HidHideSnapshot()

    def start(self):
        self.calls.append("start")
        self._snapshot = HidHideSnapshot(phase=HidHidePhase.READY)
        return self._snapshot

    def stop(self, *, remove_allowlist=False):
        self.calls.append(("stop", remove_allowlist))
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


class _InputActivityMonitor:
    available = True

    def __init__(self):
        self.calls = []

    def start(self):
        self.calls.append("start")
        return True

    def stop(self):
        self.calls.append("stop")


class XInputBridgeService(RuntimeXInputBridgeService):
    def __init__(self, settings, **kwargs):
        kwargs.setdefault("forza_foreground", lambda: True)
        super().__init__(settings, **kwargs)


def test_unknown_platform_normalizes_to_safe_steam_default():
    assert normalize_forza_platform("XBOX_APP") == XBOX_APP_PLATFORM
    assert normalize_forza_platform("future-store") == STEAM_PLATFORM


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
    assert backend.consumers == [bridge.publish_latest]
    assert bridge.mappings[-1] == DEFAULT_BUTTON_MAPPING
    assert bridge.gyro_mappings[-1] == DEFAULT_GYRO_MAPPING


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
    assert backend.consumers[-1] == bridge.publish_latest


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


def test_forza_foreground_gate_starts_and_stops_the_physical_and_virtual_session():
    settings = Settings(
        preferred_forza_platform=XBOX_APP_PLATFORM,
        enable_hidhide=True,
    )
    bridge = _Bridge()
    backend = _Backend()
    monitor = _InputActivityMonitor()
    isolation = _HidHide()
    running = [False]
    now = [100.0]
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        input_activity_monitor=monitor,
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
        forza_foreground=lambda: running[0],
        clock=lambda: now[0],
    )

    service.sync(backend)

    assert service.snapshot().status is BridgeStatus.WAITING_GAME
    assert service.forza_active is False
    assert bridge.calls == ["stop"]
    assert backend.consumers == []
    assert backend.lifecycle == []
    assert backend.runtime_enabled[-1] is False
    assert "start" not in isolation.calls

    running[0] = True
    now[0] += 0.5
    assert service.poll_forza_foreground() is True

    assert service.forza_active is True
    assert bridge.calls[-1] == "start"
    assert backend.consumers[-1] == bridge.publish_latest
    assert monitor.calls[-1] == "start"
    assert "start" not in isolation.calls
    assert backend.lifecycle == []
    assert backend.runtime_enabled[-1] is True

    bridge.set_target_connected(True)
    assert service.poll_forza_foreground() is True
    assert isolation.calls[-1] == "start"

    running[0] = False
    now[0] += 0.5
    assert service.poll_forza_foreground() is False

    assert service.snapshot().status is BridgeStatus.WAITING_GAME
    assert service.forza_active is False
    assert backend.consumers[-1] is None
    assert bridge.calls[-1] == "stop"
    assert monitor.calls[-1] == "stop"
    assert isolation.calls[-1] == ("stop", False)
    assert backend.lifecycle == []
    assert backend.runtime_enabled[-1] is False


def test_stop_publishes_closed_gate_before_waiting_for_monitor_shutdown():
    observed_gate_states = []

    class OrderingService(XInputBridgeService):
        def _stop_foreground_monitor(self):
            observed_gate_states.append(self.forza_active)
            super()._stop_foreground_monitor()

    service = OrderingService(
        Settings(preferred_forza_platform=XBOX_APP_PLATFORM),
        bridge=_Bridge(),
        platform_supported=lambda: True,
    )
    service.sync(_Backend())
    assert service.forza_active is True
    observed_gate_states.clear()

    service.stop()

    assert observed_gate_states == [False]


def test_steam_foreground_gate_releases_physical_hid_but_keeps_passive_detection():
    settings = Settings(preferred_forza_platform=STEAM_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    running = [False]
    now = [10.0]
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        platform_supported=lambda: True,
        forza_foreground=lambda: running[0],
        clock=lambda: now[0],
    )

    service.sync(backend)

    assert service.forza_active is False
    assert service.snapshot().status is BridgeStatus.WAITING_GAME
    assert backend.lifecycle == []
    assert backend.runtime_enabled[-1] is False
    assert backend.consumers == []
    assert bridge.calls == ["stop"]

    running[0] = True
    now[0] += 0.5
    assert service.poll_forza_foreground() is True

    assert backend.lifecycle == []
    assert backend.runtime_enabled[-1] is True
    assert service.snapshot().status is BridgeStatus.DISABLED
    assert "start" not in bridge.calls

    running[0] = False
    now[0] += 0.5
    assert service.poll_forza_foreground() is False

    assert backend.lifecycle == []
    assert backend.runtime_enabled[-1] is False
    assert service.snapshot().status is BridgeStatus.WAITING_GAME


def test_non_forza_foreground_never_opens_physical_runtime_in_steam_mode():
    backend = _Backend()
    service = XInputBridgeService(
        Settings(preferred_forza_platform=STEAM_PLATFORM),
        bridge=_Bridge(),
        platform_supported=lambda: True,
        forza_foreground=lambda: False,
    )

    service.sync(backend)

    assert backend.lifecycle == []
    assert backend.runtime_enabled
    assert all(enabled is False for enabled in backend.runtime_enabled)
    assert service.forza_active is False


def test_explicit_lab_preview_temporarily_opens_only_the_physical_runtime():
    backend = _Backend()
    bridge = _Bridge()
    service = XInputBridgeService(
        Settings(preferred_forza_platform=STEAM_PLATFORM),
        bridge=bridge,
        platform_supported=lambda: True,
        forza_foreground=lambda: False,
    )
    service.sync(backend)

    assert service.request_preview_runtime(True) is True
    assert service.preview_requested is True
    assert backend.runtime_enabled[-1] is True
    assert bridge.calls == ["stop"]
    assert backend.consumers == []

    assert service.request_preview_runtime(False) is False
    assert service.preview_requested is False
    assert backend.runtime_enabled[-1] is False


def test_forza_preempts_an_explicit_lab_preview_runtime():
    running = [False]
    now = [0.0]
    backend = _Backend()
    service = XInputBridgeService(
        Settings(preferred_forza_platform=STEAM_PLATFORM),
        bridge=_Bridge(),
        platform_supported=lambda: True,
        forza_foreground=lambda: running[0],
        clock=lambda: now[0],
    )
    service.sync(backend)
    service.request_preview_runtime(True)

    running[0] = True
    now[0] += 0.5
    assert service.poll_forza_foreground() is True

    assert service.preview_requested is False
    assert service.forza_active is True
    assert backend.runtime_enabled[-1] is True


def test_forza_foreground_gate_is_throttled_and_fails_closed_on_scan_errors():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    now = [50.0]
    scans = [True]

    def detect():
        value = scans[-1]
        if isinstance(value, Exception):
            raise value
        return value

    service = XInputBridgeService(
        settings,
        bridge=bridge,
        platform_supported=lambda: True,
        forza_foreground=detect,
        clock=lambda: now[0],
        foreground_poll_interval_s=0.5,
    )
    service.sync(backend)
    assert service.forza_active is True

    scans.append(ProcessScanError("process table unavailable"))
    now[0] += 0.49
    assert service.poll_forza_foreground() is True
    assert bridge.calls[-1] == "start"

    now[0] += 0.01
    assert service.poll_forza_foreground() is False
    assert service.snapshot().status is BridgeStatus.WAITING_GAME
    assert bridge.calls[-1] == "stop"


def test_background_foreground_monitor_publishes_inactive_before_teardown_finishes():
    class BlockingStopBridge(_Bridge):
        def __init__(self):
            super().__init__()
            self.stop_count = 0
            self.blocking_stop_entered = threading.Event()
            self.release_blocking_stop = threading.Event()

        def stop(self):
            self.stop_count += 1
            self.calls.append("stop")
            if self.stop_count == 2:
                self.blocking_stop_entered.set()
                assert self.release_blocking_stop.wait(1.0)

    active = threading.Event()
    active.set()
    bridge = BlockingStopBridge()
    service = RuntimeXInputBridgeService(
        Settings(preferred_forza_platform=XBOX_APP_PLATFORM),
        bridge=bridge,
        platform_supported=lambda: True,
        forza_foreground=active.is_set,
        foreground_poll_interval_s=0.05,
        background_foreground_monitor=True,
    )
    service.sync(_Backend())
    assert service.forza_active is True

    active.clear()
    try:
        assert bridge.blocking_stop_entered.wait(0.5)
        # stop() is deliberately still blocked, but the telemetry-facing gate
        # has already become false and can release native output immediately.
        assert service.poll_forza_foreground() is False
    finally:
        bridge.release_blocking_stop.set()
        service.stop()


def test_background_detector_closes_gate_while_hidhide_start_is_blocked():
    class TrackingBridge(_Bridge):
        def __init__(self):
            super().__init__(target_connected=True)
            self.published = 0

        def publish_latest(self, _state, _received_at):
            self.published += 1

    class BlockingStartHidHide(_HidHide):
        def __init__(self):
            super().__init__()
            self.start_entered = threading.Event()
            self.release_start = threading.Event()
            self.cleaned_after_start = threading.Event()

        def start(self):
            self.calls.append("start")
            self.start_entered.set()
            assert self.release_start.wait(1.0)
            self._snapshot = HidHideSnapshot(phase=HidHidePhase.READY)
            return self._snapshot

        def stop(self, *, remove_allowlist=False):
            result = super().stop(remove_allowlist=remove_allowlist)
            if self.start_entered.is_set():
                self.cleaned_after_start.set()
            return result

    foreground = threading.Event()
    foreground.set()
    bridge = TrackingBridge()
    backend = _Backend()
    isolation = BlockingStartHidHide()
    service = RuntimeXInputBridgeService(
        Settings(
            preferred_forza_platform=XBOX_APP_PLATFORM,
            enable_hidhide=True,
        ),
        bridge=bridge,
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
        forza_foreground=foreground.is_set,
        foreground_poll_interval_s=0.05,
        background_foreground_monitor=True,
    )
    service.sync(backend)
    assert isolation.start_entered.wait(0.5)

    foreground.clear()
    deadline = time.monotonic() + 0.5
    while service.forza_active and time.monotonic() < deadline:
        threading.Event().wait(0.01)

    try:
        assert service.forza_active is False
        assert backend.startup_pulse_cancellations == 1
        # The child worker is still blocked, but its already-attached input
        # callback was invalidated atomically with the telemetry-facing gate.
        consumer = backend.consumers[-1]
        consumer(object(), 1.0)
        assert bridge.published == 0

        isolation.release_start.set()
        assert isolation.cleaned_after_start.wait(0.5)
        assert service.forza_active is False
        assert backend.consumers[-1] is None
        assert backend.visibility_observers[-1] is None
        assert isolation.snapshot().phase is HidHidePhase.DISABLED
    finally:
        isolation.release_start.set()
        service.stop()


def test_background_gate_rebinds_after_close_and_reopen_during_blocked_start():
    class TrackingBridge(_Bridge):
        def __init__(self):
            super().__init__(target_connected=True)
            self.published = 0

        def publish_latest(self, _state, _received_at):
            self.published += 1

    class BlockingFirstStartHidHide(_HidHide):
        def __init__(self):
            super().__init__()
            self.first_start_entered = threading.Event()
            self.release_first_start = threading.Event()
            self.start_count = 0

        def start(self):
            self.calls.append("start")
            self.start_count += 1
            if self.start_count == 1:
                self.first_start_entered.set()
                self.release_first_start.wait(1.0)
            self._snapshot = HidHideSnapshot(phase=HidHidePhase.READY)
            return self._snapshot

    foreground = threading.Event()
    foreground.set()
    bridge = TrackingBridge()
    backend = _Backend()
    isolation = BlockingFirstStartHidHide()
    service = RuntimeXInputBridgeService(
        Settings(
            preferred_forza_platform=XBOX_APP_PLATFORM,
            enable_hidhide=True,
        ),
        bridge=bridge,
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
        forza_foreground=foreground.is_set,
        foreground_poll_interval_s=0.05,
        background_foreground_monitor=True,
    )
    service.sync(backend)
    assert isolation.first_start_entered.wait(0.5)
    stale_consumer = backend.consumers[-1]

    foreground.clear()
    deadline = time.monotonic() + 0.5
    while service.forza_active and time.monotonic() < deadline:
        threading.Event().wait(0.01)
    assert service.forza_active is False

    foreground.set()
    deadline = time.monotonic() + 0.5
    while not service.forza_active and time.monotonic() < deadline:
        threading.Event().wait(0.01)
    assert service.forza_active is True

    try:
        isolation.release_first_start.set()
        deadline = time.monotonic() + 1.0
        while (
            (
                isolation.start_count < 2
                or backend.consumers[-1] is None
                or backend.consumers[-1] is stale_consumer
            )
            and time.monotonic() < deadline
        ):
            threading.Event().wait(0.01)

        current_consumer = backend.consumers[-1]
        assert isolation.start_count >= 2
        assert current_consumer is not None
        assert current_consumer is not stale_consumer
        stale_consumer(object(), 1.0)
        assert bridge.published == 0
        current_consumer(object(), 2.0)
        assert bridge.published == 1
    finally:
        isolation.release_first_start.set()
        service.stop()


def test_background_foreground_monitor_restarts_after_a_timed_out_join():
    old_monitor_entered = threading.Event()
    release_old_monitor = threading.Event()
    successor_polled = threading.Event()
    call_lock = threading.Lock()
    calls = 0

    def detect():
        nonlocal calls
        with call_lock:
            calls += 1
            call_number = calls
        if call_number == 2:
            old_monitor_entered.set()
            release_old_monitor.wait(1.0)
        if call_number >= 4:
            successor_polled.set()
        return True

    backend = _Backend()
    service = RuntimeXInputBridgeService(
        Settings(preferred_forza_platform=XBOX_APP_PLATFORM),
        bridge=_Bridge(),
        platform_supported=lambda: True,
        forza_foreground=detect,
        foreground_poll_interval_s=0.05,
        background_foreground_monitor=True,
    )
    service._foreground_monitor_stop_timeout = 0.01
    service.sync(backend)
    assert old_monitor_entered.wait(0.5)

    resync = threading.Thread(target=service.sync, args=(backend,))
    resync.start()
    try:
        assert service._foreground_monitor_stop.wait(0.5)
        threading.Event().wait(0.03)
        release_old_monitor.set()
        resync.join(timeout=1.0)

        assert not resync.is_alive()
        assert successor_polled.wait(0.5)
    finally:
        release_old_monitor.set()
        resync.join(timeout=1.0)
        service.stop()


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

    assert isolation.calls == [("stop", False)]
    assert backend.visibility_observers == []

    bridge.set_target_connected(True)
    service.poll_forza_foreground()

    assert isolation.calls == [("stop", False), "start"]
    observer = backend.visibility_observers[-1]
    assert observer.__self__ is isolation
    assert observer({"path": b"controller"}) is True
    assert isolation.calls[-1] == ("register", {"path": b"controller"})


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
    service.poll_forza_foreground()

    assert backend.visibility_observers[-1] is None
    assert isolation.calls[-1] == ("stop", False)


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
    service.poll_forza_foreground()

    assert isolation.calls == [("stop", False)]
    assert backend.visibility_observers == []


def test_hidhide_enable_retries_after_a_transient_driver_probe_failure():
    settings = Settings(
        preferred_forza_platform=XBOX_APP_PLATFORM,
        enable_hidhide=True,
    )
    now = [10.0]
    driver_ready = [False]
    isolation = _HidHide()
    service = XInputBridgeService(
        settings,
        bridge=_Bridge(target_connected=True),
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: driver_ready[0],
        platform_supported=lambda: True,
        clock=lambda: now[0],
    )
    service.sync(_Backend())
    assert "start" not in isolation.calls

    driver_ready[0] = True
    now[0] += 0.5
    service.poll_forza_foreground(force=True)
    assert "start" not in isolation.calls

    now[0] += 0.5
    service.poll_forza_foreground(force=True)
    assert isolation.calls[-1] == "start"


def test_hidhide_cleanup_retries_after_a_transient_stop_failure():
    class FlakyStopHidHide(_HidHide):
        fail_next_stop = False

        def stop(self, *, remove_allowlist=False):
            self.calls.append(("stop", remove_allowlist))
            if self.fail_next_stop:
                self.fail_next_stop = False
                self._snapshot = HidHideSnapshot(
                    phase=HidHidePhase.ERROR,
                    last_error="synthetic cleanup failure",
                )
                return self._snapshot
            self._snapshot = HidHideSnapshot()
            return self._snapshot

    settings = Settings(
        preferred_forza_platform=XBOX_APP_PLATFORM,
        enable_hidhide=True,
    )
    now = [20.0]
    foreground = [True]
    isolation = FlakyStopHidHide()
    service = XInputBridgeService(
        settings,
        bridge=_Bridge(target_connected=True),
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
        forza_foreground=lambda: foreground[0],
        clock=lambda: now[0],
    )
    service.sync(_Backend())
    isolation.calls.clear()

    isolation.fail_next_stop = True
    foreground[0] = False
    now[0] += 0.05
    service.poll_forza_foreground(force=True)
    assert isolation.snapshot().phase is HidHidePhase.ERROR
    assert isolation.calls == [("stop", False)]

    now[0] += 0.5
    service.poll_forza_foreground(force=True)
    assert isolation.calls == [("stop", False)]

    now[0] += 0.5
    service.poll_forza_foreground(force=True)
    assert isolation.snapshot().phase is HidHidePhase.DISABLED
    assert isolation.calls == [("stop", False), ("stop", False)]


def test_background_hidhide_cleanup_retries_without_another_foreground_edge():
    class FlakyStopHidHide(_HidHide):
        fail_next_stop = False

        def stop(self, *, remove_allowlist=False):
            self.calls.append(("stop", remove_allowlist))
            if self.fail_next_stop:
                self.fail_next_stop = False
                self._snapshot = HidHideSnapshot(
                    phase=HidHidePhase.ERROR,
                    last_error="synthetic cleanup failure",
                )
                return self._snapshot
            self._snapshot = HidHideSnapshot()
            return self._snapshot

    foreground = threading.Event()
    foreground.set()
    isolation = FlakyStopHidHide()
    service = RuntimeXInputBridgeService(
        Settings(
            preferred_forza_platform=XBOX_APP_PLATFORM,
            enable_hidhide=True,
        ),
        bridge=_Bridge(target_connected=True),
        hidhide_service=isolation,
        hidhide_driver_ready=lambda: True,
        platform_supported=lambda: True,
        forza_foreground=foreground.is_set,
        foreground_poll_interval_s=0.05,
        background_foreground_monitor=True,
    )
    service.sync(_Backend())
    deadline = time.monotonic() + 0.5
    while "start" not in isolation.calls and time.monotonic() < deadline:
        threading.Event().wait(0.01)
    assert "start" in isolation.calls
    isolation.calls.clear()

    isolation.fail_next_stop = True
    foreground.clear()
    try:
        deadline = time.monotonic() + 0.5
        while (
            isolation.snapshot().phase is not HidHidePhase.ERROR
            and time.monotonic() < deadline
        ):
            threading.Event().wait(0.01)
        assert isolation.snapshot().phase is HidHidePhase.ERROR
        assert isolation.calls == [("stop", False)]

        deadline = time.monotonic() + 1.5
        while (
            isolation.snapshot().phase is not HidHidePhase.DISABLED
            and time.monotonic() < deadline
        ):
            threading.Event().wait(0.01)
        assert isolation.snapshot().phase is HidHidePhase.DISABLED
        assert isolation.calls == [("stop", False), ("stop", False)]
    finally:
        service.stop()


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

    waiting = hidhide_presentation(
        settings,
        BridgeSnapshot(status=BridgeStatus.WAITING_GAME),
        HidHideSnapshot(),
        translate,
    )
    assert waiting.title == "HidHide isolation is waiting"
    assert "FH4, FH5, or FH6" in waiting.detail

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
