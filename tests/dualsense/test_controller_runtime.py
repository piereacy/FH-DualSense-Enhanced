import struct
import threading
import time
import zlib

import pytest

from modules.dualsense import main as dualsense_main
from modules.dualsense.controller_state import ControllerPhase
from modules.dualsense.input_state import BatteryStatus, InputTransport
from modules.dualsense.topology import path_key


def _report(transport, *, level=6, charging=0, left_x=0):
    bluetooth = transport is InputTransport.BLUETOOTH
    report = bytearray(78 if bluetooth else 64)
    report[0] = 0x31 if bluetooth else 0x01
    base = 2 if bluetooth else 1
    report[base] = left_x
    report[base + 7] = 8
    report[base + 52] = (charging << 4) | level
    if bluetooth:
        crc = zlib.crc32(memoryview(report)[:74], zlib.crc32(b"\xA1"))
        struct.pack_into("<I", report, 74, crc)
    return bytes(report)


class _IdleDevice:
    def __init__(self, *, events=None, label="device"):
        self.closed = threading.Event()
        self.close_thread = None
        self.events = events if events is not None else []
        self.label = label

    def read(self, _size, timeout_ms=0):
        assert timeout_ms == 0
        return []

    def write(self, report):
        return len(report)

    def close(self):
        self.events.append(f"{self.label}.close")
        self.close_thread = threading.get_ident()
        self.closed.set()


class _QueuedDevice(_IdleDevice):
    def __init__(self, reports):
        super().__init__()
        self.reports = list(reports)
        self.read_count = 0

    def read(self, _size, timeout_ms=0):
        assert timeout_ms == 0
        self.read_count += 1
        return self.reports.pop(0) if self.reports else []


class _NonblockingFailureDevice(_IdleDevice):
    def open_path(self, _path):
        return None

    def set_nonblocking(self, _enabled):
        raise OSError("synthetic nonblocking failure")


class _OpeningDevice(_IdleDevice):
    def __init__(
        self,
        *,
        events=None,
        label="device",
        feature_result=48,
        feature_error=None,
    ):
        super().__init__(events=events, label=label)
        self.writes = []
        self.feature_reports = []
        self.feature_result = feature_result
        self.feature_error = feature_error

    def open_path(self, _path):
        return None

    def set_nonblocking(self, _enabled):
        return None

    def write(self, report):
        self.events.append(f"{self.label}.write")
        self.writes.append(bytes(report))
        return len(report)

    def send_feature_report(self, report):
        self.events.append(f"{self.label}.feature")
        self.feature_reports.append(bytes(report))
        if self.feature_error is not None:
            raise self.feature_error
        return self.feature_result


class _CandidateDevice(_OpeningDevice):
    def __init__(self, reports, **kwargs):
        super().__init__(**kwargs)
        self.reports = list(reports)

    def read(self, _size, timeout_ms=0):
        assert timeout_ms == 0
        return self.reports.pop(0) if self.reports else []


def _connected(controller, transport, *, identity="001122334455", path=b"current"):
    now = time.monotonic()
    controller.lay = (
        dualsense_main.BT if transport is InputTransport.BLUETOOTH else dualsense_main.USB
    )
    controller.dev_path = path
    controller.dev_serial = identity
    controller._last_input_at = now
    controller._ever_connected = True
    controller._current_info = {
        "path": path,
        "serial_number": identity,
        "bus_type": 2 if transport is InputTransport.BLUETOOTH else 1,
    }
    controller._update_snapshot(
        phase=ControllerPhase.CONNECTED,
        transport=transport,
        identity=identity,
        last_input_at=now,
        battery_level=8,
        battery_status=BatteryStatus.DISCHARGING,
    )


def test_valid_input_updates_connection_and_battery_without_xinput_consumer():
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.lay = dualsense_main.USB
    controller.dev_serial = "001122334455"

    assert controller._publish_input(
        _report(InputTransport.USB, level=6, charging=1),
        123.0,
    ) is True

    snapshot = controller.snapshot()
    assert snapshot.connected is True
    assert snapshot.battery_percent == 60
    assert snapshot.battery_status is BatteryStatus.CHARGING
    assert controller._ever_connected is True


def test_invalid_input_cannot_refresh_liveness_or_stale_battery():
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.lay = dualsense_main.USB
    before = controller.snapshot()

    assert controller._publish_input(bytes(63), 999.0) is False

    assert controller._last_input_at == 0.0
    assert controller.snapshot() == before


def test_input_drain_consumes_entire_queue_in_one_iteration():
    reports = [
        _report(InputTransport.USB, level=level)
        for level in (2, 4, 8)
    ]
    device = _QueuedDevice(reports)
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.dev = device
    controller.lay = dualsense_main.USB
    controller.dev_serial = "001122334455"
    published = []
    controller.set_input_consumer(lambda state, _received_at: published.append(state))

    saturated = controller._drain_input_queue()

    assert saturated is False
    assert device.read_count == 4
    assert [state.battery_level for state in published] == [2, 4, 8]
    assert controller.snapshot().battery_percent == 80


def test_input_drain_reports_saturation_without_sleeping_on_remaining_queue():
    device = _QueuedDevice([_report(InputTransport.USB)] * 3)
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.dev = device
    controller.lay = dualsense_main.USB

    assert controller._drain_input_queue(max_reports=2) is True
    assert len(device.reports) == 1


def test_input_drain_can_publish_only_the_newest_state_for_xinput():
    device = _QueuedDevice(
        [_report(InputTransport.BLUETOOTH, left_x=value) for value in (1, 2, 255)]
    )
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.dev = device
    controller.lay = dualsense_main.BT
    controller._bt_haptics_pending = bytes(64)
    published = []
    controller.set_input_consumer(lambda state, _received_at: published.append(state))

    saturated = controller._drain_input_queue(publish_latest_only=True)

    assert saturated is False
    assert device.read_count == 4
    assert [state.left_x for state in published] == [255]
    assert controller._bt_haptics_pending == bytes(64)


def test_latest_only_drain_falls_back_from_a_malformed_tail_report():
    valid = _report(InputTransport.BLUETOOTH, left_x=77)
    malformed = valid[:-1]
    device = _QueuedDevice([valid, malformed])
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.dev = device
    controller.lay = dualsense_main.BT
    published = []
    controller.set_input_consumer(lambda state, _received_at: published.append(state))

    controller._drain_input_queue(publish_latest_only=True)

    assert [state.left_x for state in published] == [77]


def test_stale_input_backlog_is_drained_before_watchdog_disconnect(monkeypatch):
    controller = dualsense_main.DualSense(
        enable_startup_pulse=False,
        enable_reconnect=False,
    )
    device = _QueuedDevice([_report(InputTransport.USB)] * 500)
    controller.dev = device
    _connected(controller, InputTransport.USB)
    controller._input_idle_timeout = 0.03
    controller._topology_interval = 999.0
    controller._last_topology_scan = time.monotonic()
    controller._running = True
    monkeypatch.setattr(dualsense_main, "_raw_dualsense_interfaces", lambda: [])
    thread = threading.Thread(target=controller._io)
    thread.start()
    try:
        assert device.closed.wait(1.0)
    finally:
        controller._running = False
        controller._wake.set()
        thread.join(timeout=1.0)

    assert device.reports == []
    assert controller.connected is False


def test_connect_failure_after_open_closes_temporary_hid_handle(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    device = _NonblockingFailureDevice()
    monkeypatch.setattr(dualsense_main.hid, "device", lambda: device)
    info = {
        "path": b"usb-test",
        "bus_type": 1,
        "serial_number": "00:11:22:33:44:55",
        "product_id": 0x0CE6,
        "usage_page": 1,
        "usage": 5,
    }

    assert controller._try_connect(info) is False
    assert device.closed.is_set()


def test_out_of_range_startup_pulse_is_clamped_before_hid_write(monkeypatch):
    controller = dualsense_main.DualSense(
        startup_pulse_force=10000,
        enable_startup_pulse=True,
    )
    device = _OpeningDevice()
    monkeypatch.setattr(dualsense_main.hid, "device", lambda: device)
    monkeypatch.setattr(dualsense_main.time, "sleep", lambda _duration: None)
    info = {
        "path": b"usb-test",
        "bus_type": 1,
        "serial_number": "00:11:22:33:44:55",
        "product_id": 0x0CE6,
        "usage_page": 1,
        "usage": 5,
    }

    assert controller._try_connect(info) is True
    assert len(device.writes) == 2
    assert device.writes[0][dualsense_main.USB["r"] + 2] == 255
    assert device.writes[0][dualsense_main.USB["l"] + 2] == 255


def test_transport_handover_never_replays_the_startup_trigger_pulse(monkeypatch):
    controller = dualsense_main.DualSense(
        startup_pulse_force=180,
        enable_startup_pulse=True,
    )
    device = _OpeningDevice()
    monkeypatch.setattr(dualsense_main.hid, "device", lambda: device)
    info = {
        "path": b"usb-test",
        "bus_type": 1,
        "serial_number": "00:11:22:33:44:55",
        "product_id": 0x0CE6,
        "usage_page": 1,
        "usage": 5,
    }

    assert controller._try_connect(info, switching=True) is True
    assert device.writes == []


def test_enumeration_failure_is_reported_without_escaping_the_io_retry(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)

    def fail_enumeration():
        raise RuntimeError("synthetic enumerate failure")

    monkeypatch.setattr(dualsense_main, "_enumerate_dualsenses", fail_enumeration)

    assert controller._try_connect() is False
    snapshot = controller.snapshot()
    assert snapshot.phase is ControllerPhase.ERROR
    assert snapshot.error == "synthetic enumerate failure"


def test_open_is_idempotent_while_io_worker_is_alive(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    started = threading.Event()

    def worker():
        started.set()
        while controller._running:
            controller._wake.wait(0.01)
            controller._wake.clear()

    monkeypatch.setattr(controller, "_io", worker)
    monkeypatch.setattr(dualsense_main.hidhide, "is_detected", lambda: False)

    controller.open()
    assert started.wait(1.0)
    first_thread = controller._thread
    controller.open()
    controller.close()

    assert controller._thread is None
    assert first_thread is not None
    assert first_thread.is_alive() is False


def test_unexpected_io_failure_is_supervised_and_recovers(monkeypatch):
    controller = dualsense_main.DualSense(
        enable_startup_pulse=False,
        enable_reconnect=True,
    )
    recovered = threading.Event()
    calls = []

    def io_session():
        calls.append(threading.get_ident())
        if len(calls) == 1:
            raise RuntimeError("synthetic HID session failure")
        recovered.set()
        while controller._running:
            controller._wake.wait(0.01)
            controller._wake.clear()

    monkeypatch.setattr(controller, "_io_loop", io_session)
    monkeypatch.setattr(dualsense_main, "IO_RECOVERY_DELAYS_S", (0.001,))
    monkeypatch.setattr(dualsense_main.hidhide, "is_detected", lambda: False)

    controller.open()
    assert recovered.wait(1.0)
    worker = controller._thread
    controller.close()

    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert controller._io_recovery_count == 1
    assert worker is not None
    assert worker.is_alive() is False


def test_force_reconnect_restarts_missing_io_worker(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    restarted = []
    monkeypatch.setattr(controller, "open", lambda: restarted.append(True))

    controller.force_reconnect()

    assert restarted == [True]
    assert controller._take_reconnect_request() is True


def test_close_does_not_touch_hid_when_worker_failed_to_stop(monkeypatch):
    class _StuckThread:
        def join(self, timeout=None):
            assert timeout == 2.0

        def is_alive(self):
            return True

    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller._running = True
    controller._thread = _StuckThread()
    monkeypatch.setattr(
        controller,
        "_disconnect",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("caller must not close HID while I/O worker is alive")
        ),
    )

    controller.close()

    assert controller._thread is not None


def test_invalid_reconnect_intervals_fall_back_to_safe_default():
    controller = dualsense_main.DualSense(reconnect_interval_s=float("nan"))
    assert controller._reconnect_interval == 5.0

    controller.set_reconnect_interval(-1)
    assert controller._reconnect_interval == 5.0


def test_watchdog_disconnects_stale_handle_even_when_auto_reconnect_is_off(monkeypatch):
    controller = dualsense_main.DualSense(
        enable_startup_pulse=False,
        enable_reconnect=False,
    )
    device = _IdleDevice()
    controller.dev = device
    _connected(controller, InputTransport.BLUETOOTH)
    controller._input_idle_timeout = 0.03
    controller._topology_interval = 999.0
    controller._running = True
    monkeypatch.setattr(dualsense_main.hidhide, "is_detected", lambda: True)
    thread = threading.Thread(target=controller._io)
    thread.start()
    try:
        assert device.closed.wait(1.0)
    finally:
        controller._running = False
        controller._wake.set()
        thread.join(timeout=1.0)

    snapshot = controller.snapshot()
    assert snapshot.connected is False
    assert snapshot.transport is None
    assert snapshot.battery_percent is None
    assert snapshot.phase is ControllerPhase.WAITING


def test_force_reconnect_closes_handle_on_io_thread_not_caller(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    device = _IdleDevice()
    controller.dev = device
    _connected(controller, InputTransport.USB)
    controller._topology_interval = 999.0
    controller._running = True
    monkeypatch.setattr(dualsense_main, "_enumerate_dualsenses", lambda: [])
    caller = threading.get_ident()
    thread = threading.Thread(target=controller._io)
    controller._thread = thread
    thread.start()
    try:
        controller.force_reconnect()
        assert device.closed.wait(1.0)
    finally:
        controller._running = False
        controller._wake.set()
        thread.join(timeout=1.0)

    assert device.close_thread == thread.ident
    assert device.close_thread != caller


def test_io_loop_keeps_bluetooth_hd_during_temporary_input_gap():
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    device = _OpeningDevice()
    controller.dev = device
    _connected(controller, InputTransport.BLUETOOTH)
    controller._last_input_at = time.monotonic() - 0.5
    controller._bt_haptics_streamed = True
    controller._input_idle_timeout = 60.0
    controller._topology_interval = 999.0
    controller._last_topology_scan = time.monotonic()
    controller._running = True
    thread = threading.Thread(target=controller._io)
    thread.start()
    try:
        time.sleep(0.05)
        assert controller.bt_haptics_failed is False
        assert controller.queue_bt_haptics(bytes(64)) is True
    finally:
        controller._running = False
        controller._wake.set()
        thread.join(timeout=1.0)


def test_bluetooth_to_usb_candidate_requires_stability_and_same_identity(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.dev = object()
    _connected(controller, InputTransport.BLUETOOTH, path=b"bt-current")
    usb = {"path": b"usb-new", "bus_type": 1, "serial_number": ""}
    dualsense_main._mac_cache[path_key(usb)] = "001122334455"
    monkeypatch.setattr(dualsense_main, "_raw_dualsense_interfaces", lambda: [usb])

    assert controller._topology_handover_candidate(1.0) is None
    candidate = controller._topology_handover_candidate(2.1)

    assert candidate is not None
    assert candidate["path"] == b"usb-new"


def test_bluetooth_to_usb_audio_gate_waits_three_seconds_without_blocking_bt(monkeypatch):
    readiness_calls = []
    controller = dualsense_main.DualSense(
        enable_startup_pulse=False,
        usb_handover_ready=lambda: readiness_calls.append("ready") or True,
        usb_handover_settle_s=3.0,
    )
    controller.dev = object()
    _connected(controller, InputTransport.BLUETOOTH, path=b"bt-current")
    usb = {
        "path": b"usb-new",
        "bus_type": 1,
        "serial_number": "001122334455",
    }
    monkeypatch.setattr(dualsense_main, "_raw_dualsense_interfaces", lambda: [usb])
    assert controller.queue_bt_haptics(bytes(64)) is True

    assert controller._topology_handover_candidate(1.0) is None
    assert controller._topology_handover_candidate(2.1) is None
    assert controller._topology_handover_candidate(3.2) is None
    assert controller._topology_handover_candidate(4.3) is None
    candidate = controller._topology_handover_candidate(5.4)

    assert readiness_calls == ["ready"]
    assert candidate is not None
    assert candidate["path"] == b"usb-new"
    assert controller._take_pending_bt_haptics() == bytes(64)
    assert controller.transport == "bluetooth"


def test_usb_audio_gate_retains_bt_then_retries_without_second_settle_window(monkeypatch):
    readiness = iter((False, True))
    controller = dualsense_main.DualSense(
        enable_startup_pulse=False,
        usb_handover_ready=lambda: next(readiness),
        usb_handover_settle_s=3.0,
    )
    old_device = object()
    controller.dev = old_device
    _connected(controller, InputTransport.BLUETOOTH, path=b"bt-current")
    usb = {
        "path": b"usb-new",
        "bus_type": 1,
        "serial_number": "001122334455",
    }
    key = path_key(usb)
    monkeypatch.setattr(dualsense_main, "_raw_dualsense_interfaces", lambda: [usb])

    assert controller._topology_handover_candidate(1.0) is None
    assert controller._topology_handover_candidate(2.1) is None
    assert controller._topology_handover_candidate(5.2) is None
    assert controller._handover_settle_deadlines[key] == pytest.approx(5.1)
    assert controller._handover_retries[key].retry_at == pytest.approx(6.2)
    assert controller.dev is old_device
    assert controller.transport == "bluetooth"

    candidate = controller._topology_handover_candidate(6.3)

    assert candidate is not None
    assert candidate["path"] == b"usb-new"
    assert controller._handover_settle_deadlines[key] == pytest.approx(5.1)


def test_usb_audio_gate_probe_exception_retains_bluetooth(monkeypatch):
    def fail_readiness():
        raise PermissionError("synthetic endpoint probe failure")

    controller = dualsense_main.DualSense(
        enable_startup_pulse=False,
        usb_handover_ready=fail_readiness,
        usb_handover_settle_s=0.0,
    )
    old_device = object()
    controller.dev = old_device
    _connected(controller, InputTransport.BLUETOOTH, path=b"bt-current")
    usb = {
        "path": b"usb-new",
        "bus_type": 1,
        "serial_number": "001122334455",
    }
    monkeypatch.setattr(dualsense_main, "_raw_dualsense_interfaces", lambda: [usb])

    assert controller._topology_handover_candidate(1.0) is None
    assert controller._topology_handover_candidate(2.1) is None

    assert controller.dev is old_device
    assert controller.transport == "bluetooth"
    assert controller._handover_retries[path_key(usb)].retry_at == pytest.approx(3.1)


def test_other_usb_controller_cannot_steal_active_bluetooth_connection(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.dev = object()
    _connected(controller, InputTransport.BLUETOOTH, path=b"bt-current")
    other = {
        "path": b"usb-other",
        "bus_type": 1,
        "serial_number": "aabbccddeeff",
    }
    monkeypatch.setattr(dualsense_main, "_raw_dualsense_interfaces", lambda: [other])

    assert controller._topology_handover_candidate(1.0) is None
    assert controller._topology_handover_candidate(2.1) is None


def test_unknown_usb_identity_is_retried_after_one_second(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.dev = object()
    _connected(controller, InputTransport.BLUETOOTH, path=b"bt-current")
    usb = {"path": b"usb-new", "bus_type": 1, "serial_number": ""}
    attempts = []

    def resolve(info):
        attempts.append(info["path"])
        if len(attempts) == 1:
            return ""
        info["serial_number"] = "001122334455"
        return "001122334455"

    monkeypatch.setattr(dualsense_main, "_mac_cache", {})
    monkeypatch.setattr(dualsense_main, "_resolve_dualsense_identity", resolve)
    monkeypatch.setattr(dualsense_main, "_raw_dualsense_interfaces", lambda: [usb])

    assert controller._topology_handover_candidate(1.0) is None
    assert controller._topology_handover_candidate(2.1) is None
    assert controller._topology_handover_candidate(3.0) is None
    candidate = controller._topology_handover_candidate(3.2)

    assert attempts == [b"usb-new", b"usb-new"]
    assert candidate is not None
    assert candidate["serial_number"] == "001122334455"


def test_failed_handover_candidate_is_cooled_down_until_retry_window(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.dev = object()
    _connected(controller, InputTransport.BLUETOOTH, path=b"bt-current")
    usb = {
        "path": b"usb-new",
        "bus_type": 1,
        "serial_number": "001122334455",
    }
    monkeypatch.setattr(dualsense_main, "_raw_dualsense_interfaces", lambda: [usb])
    monkeypatch.setattr(
        controller,
        "_validate_handover_candidate",
        lambda _target: (None, "synthetic validation failure"),
    )

    assert controller._topology_handover_candidate(1.0) is None
    candidate = controller._topology_handover_candidate(2.1)
    assert candidate is not None
    assert controller._perform_handover(candidate, now=2.1) is False

    assert controller._topology_handover_candidate(3.0) is None
    retried = controller._topology_handover_candidate(3.2)
    assert retried is not None
    assert retried["path"] == b"usb-new"

    assert controller._perform_handover(retried, now=3.2) is False
    assert controller._topology_handover_candidate(4.3) is None
    retried = controller._topology_handover_candidate(5.3)
    assert retried is not None

    assert controller._perform_handover(retried, now=5.3) is False
    assert controller._topology_handover_candidate(6.4) is None
    assert controller._topology_handover_candidate(9.9) is None
    assert controller._topology_handover_candidate(10.9) is not None


def test_failed_handover_cooldown_clears_when_candidate_disappears(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.dev = object()
    _connected(controller, InputTransport.BLUETOOTH, path=b"bt-current")
    usb = {
        "path": b"usb-new",
        "bus_type": 1,
        "serial_number": "001122334455",
    }
    visible = [usb]
    monkeypatch.setattr(dualsense_main, "_raw_dualsense_interfaces", lambda: visible)
    controller._handover_retries[path_key(usb)] = dualsense_main._HandoverRetryState(
        failures=3,
        retry_at=100.0,
    )
    controller._handover_settle_deadlines[path_key(usb)] = 50.0
    controller._handover_readiness_logged.add(path_key(usb))

    assert controller._topology_handover_candidate(1.0) is None
    visible.clear()
    assert controller._topology_handover_candidate(2.1) is None
    assert controller._handover_retries == {}
    assert controller._handover_settle_deadlines == {}
    assert controller._handover_readiness_logged == set()


def test_failed_candidate_validation_keeps_active_bluetooth_untouched(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    old_device = _OpeningDevice()
    controller.dev = old_device
    _connected(controller, InputTransport.BLUETOOTH, path=b"bt-current")
    before = controller.snapshot()
    candidate = _NonblockingFailureDevice()
    controller._handover_input_timeout = 0.0
    monkeypatch.setattr(dualsense_main.hid, "device", lambda: candidate)
    usb = {
        "path": b"usb-new",
        "bus_type": 1,
        "serial_number": "001122334455",
    }

    assert controller._perform_handover(usb, now=10.0) is False

    assert controller.dev is old_device
    assert old_device.closed.is_set() is False
    assert old_device.writes == []
    assert candidate.closed.is_set() is True
    assert controller.snapshot() == before


def test_validated_usb_candidate_is_adopted_without_disconnected_snapshot(monkeypatch):
    controller = dualsense_main.DualSense(
        startup_pulse_force=180,
        enable_startup_pulse=True,
    )
    events = []
    old_device = _OpeningDevice(events=events, label="bt")
    controller.dev = old_device
    _connected(controller, InputTransport.BLUETOOTH, path=b"bt-current")
    candidate = _CandidateDevice(
        [_report(InputTransport.USB, level=3, charging=1)],
        events=events,
        label="usb",
    )
    monkeypatch.setattr(dualsense_main.hid, "device", lambda: candidate)
    usb = {
        "path": b"usb-new",
        "bus_type": 1,
        "serial_number": "001122334455",
    }

    assert controller._perform_handover(usb, now=10.0) is True

    snapshot = controller.snapshot()
    assert controller.dev is candidate
    assert controller.transport == "usb"
    assert snapshot.phase is ControllerPhase.CONNECTED
    assert snapshot.battery_percent == 30
    assert snapshot.battery_status is BatteryStatus.CHARGING
    assert old_device.closed.is_set() is True
    assert len(old_device.writes) == 1
    assert len(old_device.feature_reports) == 1
    assert old_device.feature_reports[0][0:2] == bytes((0x08, 0x02))
    assert events == ["bt.write", "bt.feature", "bt.close"]
    assert candidate.writes == []


@pytest.mark.parametrize(
    ("feature_result", "feature_error"),
    [
        (0, None),
        (48, OSError("synthetic feature failure")),
    ],
    ids=["zero-return", "exception"],
)
def test_bluetooth_teardown_failure_retains_active_transport_and_closes_candidate(
    monkeypatch,
    feature_result,
    feature_error,
):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    old_device = _OpeningDevice(
        label="bt",
        feature_result=feature_result,
        feature_error=feature_error,
    )
    controller.dev = old_device
    _connected(controller, InputTransport.BLUETOOTH, path=b"bt-current")
    before = controller.snapshot()
    candidate = _CandidateDevice([_report(InputTransport.USB)], label="usb")
    monkeypatch.setattr(dualsense_main.hid, "device", lambda: candidate)
    usb = {
        "path": b"usb-new",
        "bus_type": 1,
        "serial_number": "001122334455",
    }

    assert controller._perform_handover(usb, now=10.0) is False

    assert controller.dev is old_device
    assert controller.transport == "bluetooth"
    assert controller.snapshot() == before
    assert old_device.closed.is_set() is False
    assert len(old_device.feature_reports) == 1
    assert candidate.closed.is_set() is True
    retry = controller._handover_retries[path_key(usb)]
    assert retry.failures == 1
    assert retry.retry_at == 11.0


def test_usb_to_bluetooth_handover_does_not_send_power_control(monkeypatch):
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    old_device = _OpeningDevice(label="usb")
    controller.dev = old_device
    _connected(controller, InputTransport.USB, path=b"usb-current")
    candidate = _CandidateDevice(
        [_report(InputTransport.BLUETOOTH)],
        label="bt",
    )
    monkeypatch.setattr(dualsense_main.hid, "device", lambda: candidate)
    bluetooth = {
        "path": b"bt-new",
        "bus_type": 2,
        "serial_number": "001122334455",
    }

    assert controller._perform_handover(bluetooth, now=10.0) is True

    assert controller.transport == "bluetooth"
    assert old_device.feature_reports == []
