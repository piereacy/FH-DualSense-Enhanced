import threading
import time

import pytest

from modules.dualsense.input_state import DPad, InputTransport
from modules.dualsense.main import BT, USB, DualSense


def _report(transport, *, left_x=128):
    bluetooth = transport is InputTransport.BLUETOOTH
    report = bytearray(78 if bluetooth else 64)
    report[0] = 0x31 if bluetooth else 0x01
    base = 2 if bluetooth else 1
    report[base:base + 6] = bytes((left_x, 128, 128, 128, 0, 0))
    report[base + 7] = DPad.NEUTRAL
    return report


class _Device:
    def __init__(self, reports):
        self.reports = list(reports)
        self.read_threads = []
        self.closed = False

    def read(self, _size, timeout_ms=0):
        assert timeout_ms == 0
        self.read_threads.append(threading.get_ident())
        if self.reports:
            return self.reports.pop(0)
        return []

    def write(self, report):
        return len(report)

    def close(self):
        self.closed = True


def _run_controller(layout, reports, consumer):
    controller = DualSense(enable_startup_pulse=False)
    controller.lay = layout
    controller.dev = _Device(reports)
    controller._ever_connected = True
    controller.set_input_consumer(consumer)
    controller._running = True
    thread = threading.Thread(target=controller._io)
    thread.start()
    return controller, thread


@pytest.mark.parametrize(
    ("layout", "transport"),
    [(USB, InputTransport.USB), (BT, InputTransport.BLUETOOTH)],
)
def test_existing_io_thread_parses_and_publishes_input(layout, transport):
    received = []
    ready = threading.Event()

    def consume(state, received_at):
        received.append((state, received_at, threading.get_ident()))
        ready.set()

    controller, thread = _run_controller(layout, [_report(transport, left_x=255)], consume)
    try:
        assert ready.wait(1.0)
    finally:
        controller._running = False
        controller._wake.set()
        thread.join(timeout=1.0)

    state, received_at, callback_thread = received[0]
    assert state.left_x == 255
    assert received_at <= time.monotonic()
    assert callback_thread == thread.ident
    assert set(controller.dev.read_threads) == {thread.ident}


def test_malformed_input_is_not_published_and_next_valid_report_recovers():
    received = []
    ready = threading.Event()

    def consume(state, _received_at):
        received.append(state)
        ready.set()

    controller, thread = _run_controller(
        USB,
        [bytes(63), _report(InputTransport.USB, left_x=1)],
        consume,
    )
    try:
        assert ready.wait(1.0)
    finally:
        controller._running = False
        controller._wake.set()
        thread.join(timeout=1.0)

    assert [state.left_x for state in received] == [1]
    assert controller._input_parse_errors == 1


def test_consumer_exception_does_not_stop_hid_io_thread():
    calls = []
    ready = threading.Event()

    def consume(state, _received_at):
        calls.append(state.left_x)
        if len(calls) == 1:
            raise RuntimeError("synthetic bridge failure")
        ready.set()

    controller, thread = _run_controller(
        USB,
        [
            _report(InputTransport.USB, left_x=1),
            _report(InputTransport.USB, left_x=2),
        ],
        consume,
    )
    try:
        assert ready.wait(1.0)
    finally:
        controller._running = False
        controller._wake.set()
        thread.join(timeout=1.0)

    assert calls == [1, 2]
    assert controller._input_consumer_errors == 1


def test_disabling_consumer_restores_idle_poll_path():
    controller = DualSense(enable_startup_pulse=False)

    controller.set_input_consumer(lambda _state, _received_at: None)
    controller.set_input_consumer(None)

    assert controller._input_consumer is None
