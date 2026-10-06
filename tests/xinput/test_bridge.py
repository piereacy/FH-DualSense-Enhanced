from dataclasses import replace
import threading
import time

from modules.config.settings import Settings
from modules.dualsense.input_state import DPad, DualSenseButton, DualSenseInputState
from modules.xinput import bridge as bridge_module
from modules.xinput.bridge import BridgeStatus, InputOwner, XInputBridge
from modules.xinput.mapping import active_mapping_from_settings
from modules.xinput.gyro import (
    GyroHorizontalAxis,
    GyroMode,
    GyroOutputStick,
    XInputGyroMapping,
)
from modules.xinput.report import XUSBButton, XUSBReport
from modules.xinput.vigem_client import ViGEmError, ViGEmErrorCode


class _Clock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class _Activity:
    def __init__(self):
        self.pending = False

    def trigger(self):
        self.pending = True

    def __call__(self):
        pending, self.pending = self.pending, False
        return pending


class _Target:
    def __init__(self, events, *, fail_update_at=None):
        self.events = events
        self.reports = []
        self.update_times = []
        self.closed = False
        self.fail_update_at = fail_update_at

    def update(self, report):
        self.reports.append(bytes(report))
        self.update_times.append(time.monotonic())
        self.events.append(("update", bytes(report)))
        if self.fail_update_at == len(self.reports):
            raise ViGEmError("synthetic update failure", ViGEmErrorCode.INVALID_TARGET)

    def close(self):
        self.closed = True
        self.events.append(("target_close", None))


class _Client:
    def __init__(self, *, connect_error=None, fail_update_at=None):
        self.events = []
        self.targets = []
        self.connect_error = connect_error
        self.fail_update_at = fail_update_at

    def connect(self):
        self.events.append(("connect", None))
        if self.connect_error:
            raise self.connect_error

    def create_x360_target(self):
        target = _Target(self.events, fail_update_at=self.fail_update_at)
        self.targets.append(target)
        self.events.append(("target_create", None))
        return target

    def close(self):
        self.events.append(("client_close", None))


class _BlockedUpdateTarget(_Target):
    def __init__(self, events, update_entered, release_update, lifecycle):
        super().__init__(events)
        self.update_entered = update_entered
        self.release_update = release_update
        self.lifecycle = lifecycle

    def update(self, report):
        super().update(report)
        if len(self.reports) == 3:
            self.lifecycle.append("old_update_blocked")
            self.update_entered.set()
            assert self.release_update.wait(2.0)

    def close(self):
        self.lifecycle.append("old_target_close")
        super().close()


class _BlockedUpdateClient(_Client):
    def __init__(self, update_entered, release_update, lifecycle):
        super().__init__()
        self.update_entered = update_entered
        self.release_update = release_update
        self.lifecycle = lifecycle

    def create_x360_target(self):
        target = _BlockedUpdateTarget(
            self.events,
            self.update_entered,
            self.release_update,
            self.lifecycle,
        )
        self.targets.append(target)
        self.events.append(("target_create", None))
        return target


def _state(*, left_x=128, buttons=frozenset(), **changes):
    values = dict(
        left_x=left_x,
        left_y=128,
        right_x=128,
        right_y=128,
        left_trigger=0,
        right_trigger=0,
        dpad=DPad.NEUTRAL,
        buttons=buttons,
    )
    values.update(changes)
    return DualSenseInputState(**values)


def _wait(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("timed out waiting for bridge state")


def test_first_input_creates_target_from_neutral_then_applies_current_state():
    clock = _Clock()
    client = _Client()
    bridge = XInputBridge(client_factory=lambda: client, clock=clock)
    bridge.start()
    bridge.publish_latest(_state(left_x=255))

    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)
    bridge.stop()

    assert client.targets[0].reports[0] == bytes(12)
    assert client.targets[0].reports[1] != bytes(12)
    assert bridge.snapshot().received_reports == 1
    assert bridge.snapshot().forwarded_reports == 1


def test_live_mapping_change_reapplies_held_input_without_recreating_target():
    clock = _Clock()
    client = _Client()
    bridge = XInputBridge(client_factory=lambda: client, clock=clock)
    bridge.start()
    bridge.publish_latest(_state(buttons=frozenset({DualSenseButton.CROSS})))
    _wait(lambda: bridge.snapshot().forwarded_reports == 1)

    settings = Settings(
        enable_custom_xinput_mapping=True,
        xinput_mapping_cross="y",
    )
    bridge.set_button_mapping(active_mapping_from_settings(settings))
    _wait(lambda: bridge.snapshot().forwarded_reports == 2)

    assert len(client.targets) == 1
    before = XUSBReport.from_buffer_copy(client.targets[0].reports[-2])
    after = XUSBReport.from_buffer_copy(client.targets[0].reports[-1])
    assert before.wButtons == XUSBButton.A
    assert after.wButtons == XUSBButton.Y
    bridge.stop()


def test_latest_slot_discards_backlog_before_worker_starts():
    clock = _Clock()
    connect_entered = threading.Event()
    release_connect = threading.Event()

    class _BlockedClient(_Client):
        def connect(self):
            connect_entered.set()
            assert release_connect.wait(1.0)
            super().connect()

    client = _BlockedClient()
    bridge = XInputBridge(client_factory=lambda: client, clock=clock)
    bridge.start()
    assert connect_entered.wait(1.0)
    try:
        for raw in range(129, 256):
            bridge.publish_latest(_state(left_x=raw))
    finally:
        release_connect.set()

    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)
    bridge.stop()

    assert len(client.targets[0].reports) == 3  # neutral, newest input, shutdown neutral
    assert bridge.snapshot().received_reports == 127
    assert bridge.snapshot().forwarded_reports == 1


def test_short_button_press_and_release_survive_latest_slot_coalescing():
    connect_entered = threading.Event()
    release_connect = threading.Event()

    class _BlockedClient(_Client):
        def connect(self):
            connect_entered.set()
            assert release_connect.wait(1.0)
            super().connect()

    client = _BlockedClient()
    bridge = XInputBridge(client_factory=lambda: client)
    bridge.start()
    assert connect_entered.wait(1.0)
    try:
        bridge.publish_latest(_state())
        bridge.publish_latest(_state(buttons=frozenset({DualSenseButton.CROSS})))
        bridge.publish_latest(_state())
    finally:
        release_connect.set()

    _wait(lambda: bridge.snapshot().forwarded_reports >= 2)
    bridge.stop()

    reports = [XUSBReport.from_buffer_copy(raw) for raw in client.targets[0].reports]
    assert any(report.wButtons & XUSBButton.A for report in reports)
    assert reports[-2].wButtons == 0
    press_index = next(
        index for index, report in enumerate(reports) if report.wButtons & XUSBButton.A
    )
    assert (
        client.targets[0].update_times[press_index + 1]
        - client.targets[0].update_times[press_index]
        >= bridge_module.MIN_DIGITAL_EDGE_HOLD_S - 0.005
    )


def test_expired_button_edges_are_not_replayed_after_bridge_connects():
    connect_entered = threading.Event()
    release_connect = threading.Event()

    class _BlockedClient(_Client):
        def connect(self):
            connect_entered.set()
            assert release_connect.wait(1.0)
            super().connect()

    clock = _Clock()
    client = _BlockedClient()
    bridge = XInputBridge(client_factory=lambda: client, clock=clock)
    bridge.start()
    assert connect_entered.wait(1.0)
    try:
        bridge.publish_latest(_state(buttons=frozenset({DualSenseButton.CROSS})))
        bridge.publish_latest(_state())
        clock.advance(0.2)
        bridge.publish_latest(_state())
    finally:
        release_connect.set()

    _wait(lambda: bridge.snapshot().forwarded_reports == 1)
    bridge.stop()

    reports = [XUSBReport.from_buffer_copy(raw) for raw in client.targets[0].reports]
    assert all(not report.wButtons & XUSBButton.A for report in reports)


def test_stale_input_is_neutralized_at_100ms_without_removing_player_slot():
    clock = _Clock()
    client = _Client()
    bridge = XInputBridge(client_factory=lambda: client, clock=clock)
    bridge.start()
    bridge.publish_latest(_state(left_x=255))
    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)

    clock.advance(0.101)
    bridge._wake.set()
    _wait(lambda: bridge.snapshot().status is BridgeStatus.STALE)
    assert client.targets[0].reports[-1] == bytes(12)

    clock.advance(2.900)
    bridge._wake.set()
    time.sleep(0.02)
    assert bridge.snapshot().status is BridgeStatus.STALE
    assert bridge.snapshot().target_connected is True
    assert client.targets[0].closed is False
    assert bridge.snapshot().stale_neutralizations == 1
    bridge.stop()

    assert client.targets[0].closed is True


def test_recovery_after_prolonged_stale_reuses_existing_target():
    clock = _Clock()
    client = _Client()
    bridge = XInputBridge(client_factory=lambda: client, clock=clock)
    bridge.start()
    bridge.publish_latest(_state(left_x=255))
    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)
    clock.advance(3.1)
    bridge._wake.set()
    _wait(lambda: bridge.snapshot().status is BridgeStatus.STALE)

    bridge.publish_latest(_state(left_x=0))
    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)
    bridge.stop()

    assert len(client.targets) == 1
    assert client.targets[0].reports[0] == bytes(12)
    assert client.targets[0].reports[1] != client.targets[0].reports[3]


def test_keyboard_mouse_input_neutralizes_target_until_deliberate_controller_change():
    clock = _Clock()
    activity = _Activity()
    client = _Client()
    bridge = XInputBridge(
        client_factory=lambda: client,
        clock=clock,
        keyboard_mouse_activity=activity,
    )
    bridge.start()
    bridge.publish_latest(_state(left_x=255))
    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)

    activity.trigger()
    bridge._wake.set()
    _wait(lambda: bridge.snapshot().input_owner is InputOwner.KEYBOARD_MOUSE)
    assert client.targets[0].reports[-1] == bytes(12)
    reports_after_keyboard = len(client.targets[0].reports)

    bridge.publish_latest(_state(left_x=250))
    time.sleep(0.02)
    assert bridge.snapshot().input_owner is InputOwner.KEYBOARD_MOUSE
    assert len(client.targets[0].reports) == reports_after_keyboard

    bridge.publish_latest(_state(left_x=243))
    _wait(lambda: bridge.snapshot().input_owner is InputOwner.CONTROLLER)
    _wait(lambda: bridge.snapshot().forwarded_reports == 2)
    assert len(client.targets) == 1
    assert client.targets[0].reports[-1] != bytes(12)
    bridge.stop()


def test_repeated_mouse_activity_does_not_advance_controller_resume_baseline():
    clock = _Clock()
    activity = _Activity()
    client = _Client()
    bridge = XInputBridge(
        client_factory=lambda: client,
        clock=clock,
        keyboard_mouse_activity=activity,
    )
    bridge.start()
    bridge.publish_latest(_state(left_x=128))
    _wait(lambda: bridge.snapshot().forwarded_reports == 1)

    activity.trigger()
    bridge._wake.set()
    _wait(lambda: bridge.snapshot().input_owner is InputOwner.KEYBOARD_MOUSE)
    bridge.publish_latest(_state(left_x=135))
    _wait(lambda: bridge.snapshot().received_reports == 2)
    assert bridge.snapshot().input_owner is InputOwner.KEYBOARD_MOUSE

    activity.trigger()
    bridge._wake.set()
    _wait(lambda: not activity.pending)
    bridge.publish_latest(_state(left_x=140))
    _wait(lambda: bridge.snapshot().input_owner is InputOwner.CONTROLLER)
    _wait(lambda: bridge.snapshot().forwarded_reports == 2)
    assert client.targets[0].reports[-1] != bytes(12)
    bridge.stop()


def test_button_press_arriving_with_mouse_activity_is_not_used_as_resume_baseline():
    connect_entered = threading.Event()
    release_connect = threading.Event()

    class _BlockedClient(_Client):
        def connect(self):
            connect_entered.set()
            assert release_connect.wait(1.0)
            super().connect()

    activity = _Activity()
    client = _BlockedClient()
    bridge = XInputBridge(
        client_factory=lambda: client,
        keyboard_mouse_activity=activity,
    )
    bridge.start()
    assert connect_entered.wait(1.0)
    try:
        activity.trigger()
        bridge.publish_latest(_state(buttons=frozenset({DualSenseButton.CROSS})))
    finally:
        release_connect.set()

    _wait(lambda: bridge.snapshot().forwarded_reports == 1)
    pressed = XUSBReport.from_buffer_copy(client.targets[0].reports[-1])
    assert pressed.wButtons & XUSBButton.A
    assert bridge.snapshot().input_owner is InputOwner.CONTROLLER
    bridge.stop()


def test_motion_already_active_at_keyboard_handover_does_not_immediately_reclaim():
    activity = _Activity()
    client = _Client()
    bridge = XInputBridge(
        client_factory=lambda: client,
        keyboard_mouse_activity=activity,
    )
    bridge.set_gyro_mapping(
        XInputGyroMapping(
            mode=GyroMode.CAMERA,
            horizontal_axis=GyroHorizontalAxis.YAW,
            deadzone_dps=0.0,
            smoothing_ms=0.0,
        )
    )
    bridge.start()
    bridge.publish_latest(_state(gyro_y=1600))
    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)

    activity.trigger()
    bridge._wake.set()
    _wait(lambda: bridge.snapshot().input_owner is InputOwner.KEYBOARD_MOUSE)
    reports_after_keyboard = len(client.targets[0].reports)

    bridge.publish_latest(_state(gyro_y=1600))
    time.sleep(0.02)
    assert bridge.snapshot().input_owner is InputOwner.KEYBOARD_MOUSE
    assert len(client.targets[0].reports) == reports_after_keyboard

    bridge.publish_latest(_state(gyro_y=0))
    time.sleep(0.02)
    bridge.publish_latest(_state(gyro_y=1600))
    _wait(lambda: bridge.snapshot().input_owner is InputOwner.CONTROLLER)
    bridge.stop()


def test_live_gyro_mapping_reapplies_latest_motion_without_recreating_target():
    clock = _Clock()
    client = _Client()
    bridge = XInputBridge(client_factory=lambda: client, clock=clock)
    bridge.start()
    bridge.publish_latest(_state())
    _wait(lambda: bridge.snapshot().forwarded_reports == 1)

    bridge.set_gyro_mapping(
        XInputGyroMapping(
            mode=GyroMode.CAMERA,
            output_stick=GyroOutputStick.RIGHT,
            horizontal_axis=GyroHorizontalAxis.YAW,
            sensitivity_dps=100.0,
            deadzone_dps=0.0,
            smoothing_ms=0.0,
        )
    )
    bridge.publish_latest(_state(gyro_y=1600))
    _wait(lambda: bridge.snapshot().forwarded_reports == 2)

    report = XUSBReport.from_buffer_copy(client.targets[0].reports[-1])
    assert len(client.targets) == 1
    assert report.sThumbRX == -32768
    assert report.sThumbLX == 0
    bridge.stop()


def test_keyboard_mouse_activity_before_target_keeps_a_neutral_target_for_isolation():
    activity = _Activity()
    client = _Client()
    bridge = XInputBridge(
        client_factory=lambda: client,
        keyboard_mouse_activity=activity,
    )
    bridge.start()

    activity.trigger()
    bridge._wake.set()
    _wait(lambda: bridge.snapshot().input_owner is InputOwner.KEYBOARD_MOUSE)
    bridge.publish_latest(_state())
    _wait(lambda: bridge.snapshot().target_connected)
    assert len(client.targets) == 1
    assert client.targets[0].reports == [bytes(12)]
    assert bridge.snapshot().input_owner is InputOwner.KEYBOARD_MOUSE
    assert bridge.snapshot().forwarded_reports == 0

    bridge.publish_latest(_state(buttons=frozenset({DualSenseButton.CROSS})))
    _wait(lambda: bridge.snapshot().input_owner is InputOwner.CONTROLLER)
    _wait(lambda: len(client.targets) == 1)
    bridge.stop()


def test_incoming_reports_do_not_shorten_recovery_backoff():
    attempts = []
    retried = threading.Event()

    class FailingClient(_Client):
        def connect(self):
            attempts.append(time.monotonic())
            if len(attempts) >= 2:
                retried.set()
            raise RuntimeError("transient ViGEm failure")

    bridge = XInputBridge(client_factory=FailingClient, recovery_delays_s=(0.15,))
    bridge.start()
    try:
        _wait(lambda: bridge.snapshot().recovery_attempts == 1)
        for _ in range(10):
            bridge.publish_latest(_state())
            time.sleep(0.002)
        assert len(attempts) == 1
        assert retried.wait(1.0)
        assert attempts[1] - attempts[0] >= 0.14
    finally:
        bridge.stop()


def test_keyboard_mouse_detector_failure_keeps_controller_forwarding():
    class _BrokenActivity:
        def __init__(self):
            self.calls = 0

        def __call__(self):
            self.calls += 1
            raise OSError("Raw Input listener stopped")

    activity = _BrokenActivity()
    client = _Client()
    bridge = XInputBridge(
        client_factory=lambda: client,
        keyboard_mouse_activity=activity,
    )
    bridge.start()
    bridge.publish_latest(_state(left_x=255))
    _wait(lambda: bridge.snapshot().forwarded_reports == 1)
    bridge.publish_latest(_state(left_x=0))
    _wait(lambda: bridge.snapshot().forwarded_reports == 2)
    bridge.stop()

    assert activity.calls == 1
    assert bridge.snapshot().input_owner is InputOwner.CONTROLLER


def test_bus_connection_failure_has_stable_driver_missing_status():
    client = _Client(
        connect_error=ViGEmError("vigem_connect", ViGEmErrorCode.BUS_NOT_FOUND)
    )
    bridge = XInputBridge(client_factory=lambda: client)
    bridge.start()

    _wait(lambda: bridge.snapshot().status is BridgeStatus.DRIVER_MISSING)
    bridge.stop()

    assert "BUS_NOT_FOUND" in bridge.snapshot().last_error
    assert not client.targets


def test_update_error_rebuilds_vigem_session_and_resumes_forwarding():
    clock = _Clock()
    clients = [_Client(fail_update_at=3), _Client()]

    def factory():
        return clients.pop(0)

    first = clients[0]
    second = clients[1]
    bridge = XInputBridge(
        client_factory=factory,
        clock=clock,
        recovery_delays_s=(0.001,),
    )
    bridge.start()
    bridge.publish_latest(_state(left_x=255))
    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)
    bridge.publish_latest(_state(left_x=0))

    _wait(lambda: bridge.snapshot().recovery_attempts == 1)
    bridge.publish_latest(_state(left_x=64))
    _wait(lambda: len(second.targets) == 1 and bridge.snapshot().status is BridgeStatus.ACTIVE)
    bridge.stop()

    names = [name for name, _payload in first.events]
    assert names.index("target_close") < names.index("client_close")
    assert second.targets[0].reports[1] != bytes(12)
    assert bridge.snapshot().recovery_attempts == 1


def test_stop_sends_neutral_before_target_close_and_client_close():
    client = _Client()
    bridge = XInputBridge(client_factory=lambda: client)
    bridge.start()
    bridge.publish_latest(_state(left_x=255))
    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)

    bridge.stop()

    names = [name for name, _payload in client.events]
    close_index = names.index("target_close")
    assert client.events[close_index - 1] == ("update", bytes(12))
    assert names.index("target_close") < names.index("client_close")
    assert bridge.snapshot().status is BridgeStatus.DISABLED


def test_start_and_stop_are_idempotent():
    client = _Client()
    bridge = XInputBridge(client_factory=lambda: client)
    bridge.start()
    bridge.start()
    _wait(lambda: ("connect", None) in client.events)

    bridge.stop()
    bridge.stop()

    assert [name for name, _payload in client.events].count("connect") == 1
    assert [name for name, _payload in client.events].count("client_close") == 1


def test_restart_does_not_replay_state_published_before_stop():
    clients = []

    def factory():
        client = _Client()
        clients.append(client)
        return client

    bridge = XInputBridge(client_factory=factory)
    bridge.start()
    bridge.publish_latest(_state(left_x=255))
    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)
    bridge.stop()

    bridge.start()
    _wait(lambda: bridge.snapshot().status is BridgeStatus.WAITING_CONTROLLER)
    time.sleep(0.02)
    assert clients[1].targets == []
    bridge.publish_latest(_state(left_x=0))
    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)
    bridge.stop()

    assert len(clients[1].targets) == 1


def test_late_consumer_from_stopped_session_cannot_publish_into_restart():
    clients = []

    def factory():
        client = _Client()
        clients.append(client)
        return client

    bridge = XInputBridge(client_factory=factory)
    bridge.start()
    _wait(lambda: len(clients) == 1)
    old_consumer = bridge.publish_latest
    bridge.stop()

    bridge.start()
    _wait(lambda: len(clients) == 2)
    assert bridge.publish_latest is not old_consumer

    old_consumer(_state(buttons=frozenset({DualSenseButton.CROSS})))
    time.sleep(0.02)
    assert clients[1].targets == []

    bridge.publish_latest(_state(left_x=0))
    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)
    bridge.stop()

    assert len(clients[1].targets) == 1


def test_bad_timeout_configuration_is_rejected():
    for kwargs in (
        {"stale_after_s": 0},
        {"stale_after_s": -1},
        {"recovery_delays_s": ()},
    ):
        try:
            XInputBridge(**kwargs)
        except ValueError:
            continue
        raise AssertionError(kwargs)


def test_stuck_worker_is_not_replaced_or_reported_as_cleanly_disabled():
    class _StuckThread:
        def join(self, timeout=None):
            assert timeout == 2.0

        def is_alive(self):
            return True

    bridge = XInputBridge()
    stuck = _StuckThread()
    target_states = []
    bridge.set_target_state_callback(target_states.append)
    bridge._thread = stuck
    bridge._running = True
    bridge._snapshot = replace(
        bridge._snapshot,
        status=BridgeStatus.ACTIVE,
        target_connected=True,
    )

    bridge.stop()
    snapshot = bridge.snapshot()
    assert bridge._thread is stuck
    assert snapshot.status is BridgeStatus.ERROR
    assert snapshot.target_connected is False
    assert "did not stop" in snapshot.last_error
    assert target_states == [False]

    old_consumer = bridge.publish_latest
    bridge.start()
    assert bridge._thread is stuck
    assert bridge._restart_pending is True
    assert bridge.publish_latest is not old_consumer
    assert bridge.snapshot().target_connected is False


def test_timed_out_worker_launches_exactly_one_pending_successor(monkeypatch):
    monkeypatch.setattr(bridge_module, "WORKER_STOP_TIMEOUT_S", 0.01)
    update_entered = threading.Event()
    release_update = threading.Event()
    lifecycle = []
    clients = []

    def factory():
        index = len(clients)
        lifecycle.append(f"client_{index}_create")
        client = (
            _BlockedUpdateClient(update_entered, release_update, lifecycle)
            if index == 0
            else _Client()
        )
        clients.append(client)
        return client

    bridge = XInputBridge(client_factory=factory)
    target_states = []
    bridge.set_target_state_callback(target_states.append)
    bridge.start()
    old_consumer = bridge.publish_latest
    old_consumer(_state(left_x=255))
    _wait(lambda: target_states == [True])
    old_consumer(_state(left_x=64))
    assert update_entered.wait(1.0)

    bridge.stop()
    assert bridge.snapshot().status is BridgeStatus.ERROR
    assert target_states == [True, False]
    bridge.start()
    pending_consumer = bridge.publish_latest
    bridge.start()
    bridge.start()

    assert pending_consumer is bridge.publish_latest
    assert pending_consumer is not old_consumer
    assert len(clients) == 1

    pending_consumer(_state(left_x=0))
    received_reports = bridge.snapshot().received_reports
    old_consumer(_state(buttons=frozenset({DualSenseButton.CROSS})))
    assert bridge.snapshot().received_reports == received_reports

    release_update.set()
    _wait(
        lambda: len(clients) == 2
        and bridge.snapshot().status is BridgeStatus.ACTIVE,
        timeout=2.0,
    )
    _wait(lambda: target_states == [True, False, True])

    assert lifecycle.index("old_target_close") < lifecycle.index("client_1_create")
    assert bridge.publish_latest is pending_consumer
    time.sleep(0.03)
    assert len(clients) == 2
    report = XUSBReport.from_buffer_copy(clients[1].targets[0].reports[1])
    assert report.sThumbLX < 0
    assert report.wButtons == 0

    monkeypatch.setattr(bridge_module, "WORKER_STOP_TIMEOUT_S", 2.0)
    bridge.stop()


def test_second_stop_cancels_pending_successor(monkeypatch):
    monkeypatch.setattr(bridge_module, "WORKER_STOP_TIMEOUT_S", 0.01)
    update_entered = threading.Event()
    release_update = threading.Event()
    lifecycle = []
    clients = []

    def factory():
        index = len(clients)
        lifecycle.append(f"client_{index}_create")
        client = (
            _BlockedUpdateClient(update_entered, release_update, lifecycle)
            if index == 0
            else _Client()
        )
        clients.append(client)
        return client

    bridge = XInputBridge(client_factory=factory)
    bridge.start()
    bridge.publish_latest(_state(left_x=255))
    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)
    bridge.publish_latest(_state(left_x=64))
    assert update_entered.wait(1.0)
    bridge.stop()

    bridge.start()
    bridge.publish_latest(_state(left_x=0))
    assert bridge._restart_pending is True
    bridge.stop()
    assert bridge._restart_pending is False

    release_update.set()
    _wait(lambda: bridge._thread is None, timeout=2.0)
    time.sleep(0.03)

    assert len(clients) == 1
    assert bridge.snapshot().target_connected is False


def test_worker_cannot_republish_target_readiness_after_logical_stop():
    bridge = None
    states_before_stop = []

    class _StoppingTarget(_Target):
        def update(self, report):
            super().update(report)
            if len(self.reports) == 2:
                states_before_stop.extend(target_states)
                bridge.stop()

    class _StoppingClient(_Client):
        def create_x360_target(self):
            target = _StoppingTarget(self.events)
            self.targets.append(target)
            self.events.append(("target_create", None))
            return target

    client = _StoppingClient()
    target_states = []
    bridge = XInputBridge(client_factory=lambda: client)
    bridge.set_target_state_callback(target_states.append)
    bridge.start()
    bridge.publish_latest(_state(left_x=255))

    _wait(lambda: ("client_close", None) in client.events)

    assert bridge.snapshot().status is BridgeStatus.ERROR
    assert bridge.snapshot().target_connected is False
    assert states_before_stop == [True]
    assert target_states == [True, False]
