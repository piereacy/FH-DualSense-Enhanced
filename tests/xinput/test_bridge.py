import time

from modules.dualsense.input_state import DPad, DualSenseInputState
from modules.xinput.bridge import BridgeStatus, XInputBridge
from modules.xinput.vigem_client import ViGEmError, ViGEmErrorCode


class _Clock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class _Target:
    def __init__(self, events, *, fail_update_at=None):
        self.events = events
        self.reports = []
        self.closed = False
        self.fail_update_at = fail_update_at

    def update(self, report):
        self.reports.append(bytes(report))
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


def _state(*, left_x=128, buttons=frozenset()):
    return DualSenseInputState(
        left_x=left_x,
        left_y=128,
        right_x=128,
        right_y=128,
        left_trigger=0,
        right_trigger=0,
        dpad=DPad.NEUTRAL,
        buttons=buttons,
    )


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


def test_latest_slot_discards_backlog_before_worker_starts():
    clock = _Clock()
    client = _Client()
    bridge = XInputBridge(client_factory=lambda: client, clock=clock)
    for raw in range(129, 256):
        bridge.publish_latest(_state(left_x=raw))
    bridge.start()

    _wait(lambda: bridge.snapshot().status is BridgeStatus.ACTIVE)
    bridge.stop()

    assert len(client.targets[0].reports) == 3  # neutral, newest input, shutdown neutral
    assert bridge.snapshot().received_reports == 127
    assert bridge.snapshot().forwarded_reports == 1


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
    _wait(lambda: bridge.snapshot().status is BridgeStatus.WAITING_CONTROLLER)

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
    bridge._thread = stuck
    bridge._running = False

    bridge.start()
    assert bridge._thread is stuck

    bridge.stop()
    snapshot = bridge.snapshot()
    assert bridge._thread is stuck
    assert snapshot.status is BridgeStatus.ERROR
    assert "did not stop" in snapshot.last_error
