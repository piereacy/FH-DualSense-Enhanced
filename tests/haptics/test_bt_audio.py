import threading
import time

import numpy as np
import pytest

from modules.haptics.bt_audio import BluetoothAudioHaptics
from modules.haptics.frame import HapticFrame


class _Controller:
    def __init__(self, transport="bluetooth", accepts=True):
        self.transport = transport
        self.accepts = accepts
        self.payloads = []
        self.sent = threading.Event()

    def queue_bt_haptics(self, payload):
        self.payloads.append(bytes(payload))
        self.sent.set()
        return self.accepts


class _Renderer:
    def __init__(self):
        self.calls = []
        self.reset_calls = 0

    def render(self, frame, frames):
        self.calls.append((frame, frames))
        pcm = np.empty((frames, 2), dtype=np.float32)
        pcm[:, 0] = 0.25
        pcm[:, 1] = -0.25
        return pcm

    def reset(self):
        self.reset_calls += 1


def _wait_until(predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def test_bt_audio_streams_32_frame_stereo_chunks_and_stops_with_silence():
    controller = _Controller()
    renderer = _Renderer()
    backend = BluetoothAudioHaptics(
        controller,
        numpy_module=np,
        renderer=renderer,
    )
    frame = HapticFrame(left_low=0.5)
    backend.set_frame(frame)

    assert backend.start() is True
    assert controller.sent.wait(1.0)
    backend.stop()

    assert renderer.calls[0] == (frame, 32)
    assert controller.payloads[0][:4] == bytes((32, 224, 32, 224))
    assert controller.payloads[-1] == bytes(64)
    assert renderer.reset_calls == 1
    assert backend.running is False


def test_bt_audio_rejects_non_bluetooth_or_missing_queue_api():
    usb = BluetoothAudioHaptics(_Controller("usb"), numpy_module=np)

    class _NoQueue:
        transport = "bluetooth"

    missing_api = BluetoothAudioHaptics(_NoQueue(), numpy_module=np)

    assert usb.start() is False
    assert missing_api.start() is False


def test_bt_audio_marks_current_connection_failed_when_queue_rejects_packet():
    controller = _Controller(accepts=False)
    backend = BluetoothAudioHaptics(
        controller,
        numpy_module=np,
        renderer=_Renderer(),
    )

    assert backend.start() is True
    assert _wait_until(lambda: backend.failed)
    assert backend.running is False

    backend.stop()


def test_bt_audio_can_restart_after_transport_reconnect():
    controller = _Controller(accepts=False)
    backend = BluetoothAudioHaptics(
        controller,
        numpy_module=np,
        renderer=_Renderer(),
    )
    assert backend.start() is True
    assert _wait_until(lambda: backend.failed)

    controller.accepts = True
    backend.reset_failure()
    controller.sent.clear()

    assert backend.start() is True
    assert controller.sent.wait(1.0)
    backend.stop()


def test_bt_audio_uses_high_resolution_sleep_for_10667ms_period():
    class _Clock:
        def __init__(self):
            self.now = 0.0
            self.delays = []

        def monotonic(self):
            return self.now

        def sleep(self, delay):
            self.delays.append(delay)
            self.now += delay

    class _FiniteController(_Controller):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def queue_bt_haptics(self, payload):
            self.calls += 1
            super().queue_bt_haptics(payload)
            return self.calls < 5

    clock = _Clock()
    backend = BluetoothAudioHaptics(
        _FiniteController(),
        numpy_module=np,
        renderer=_Renderer(),
        monotonic=clock.monotonic,
        sleeper=clock.sleep,
    )

    assert backend.start() is True
    assert _wait_until(lambda: backend.failed)

    assert clock.delays[:3] == pytest.approx([32 / 3000] * 3)
    backend.stop()


def test_bt_audio_does_not_replace_a_worker_that_failed_to_stop():
    class _StuckThread:
        def join(self, timeout=None):
            assert timeout == 1.0

        def is_alive(self):
            return True

    controller = _Controller()
    backend = BluetoothAudioHaptics(
        controller,
        numpy_module=np,
        renderer=_Renderer(),
    )
    stuck = _StuckThread()
    backend._thread = stuck
    backend._running = False
    backend._failed = True

    backend.reset_failure()
    assert backend.failed is True
    assert backend.start() is False
    backend.stop()

    assert backend._thread is stuck
    assert controller.payloads == []
