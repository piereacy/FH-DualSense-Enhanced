import threading
from pathlib import Path

from modules.dualsense.input_state import DPad, DualSenseButton, DualSenseInputState
from modules.xinput.hot_switch import (
    KeyboardMouseActivityMonitor,
    _WindowsRawInputListener,
    controller_input_changed,
    controller_input_is_active,
)


ROOT = Path(__file__).resolve().parents[2]


def _state(
    *,
    left_x=128,
    left_trigger=0,
    dpad=DPad.NEUTRAL,
    buttons=frozenset(),
):
    return DualSenseInputState(
        left_x=left_x,
        left_y=128,
        right_x=128,
        right_y=128,
        left_trigger=left_trigger,
        right_trigger=0,
        dpad=dpad,
        buttons=buttons,
    )


class _Listener:
    def __init__(self, callback, *, start_error=None):
        self.callback = callback
        self.start_error = start_error
        self.start_calls = 0
        self.stop_calls = 0
        self._running = False

    @property
    def alive(self):
        return self._running

    @property
    def running(self):
        return self._running

    def start(self):
        self.start_calls += 1
        if self.start_error is not None:
            raise self.start_error
        self._running = True
        return True

    def stop(self):
        self.stop_calls += 1
        self._running = False

    def emit(self):
        self.callback()


def test_keyboard_mouse_monitor_coalesces_raw_input_and_owns_listener_lifecycle():
    listeners = []

    def factory(callback):
        listener = _Listener(callback)
        listeners.append(listener)
        return listener

    monitor = KeyboardMouseActivityMonitor(factory)

    assert monitor.available
    assert monitor.start()
    assert monitor.start()
    assert monitor.running
    assert listeners[0].start_calls == 1
    assert not monitor.poll()

    listeners[0].emit()
    listeners[0].emit()
    assert monitor.poll()
    assert not monitor.poll()

    monitor.stop()
    monitor.stop()
    assert not monitor.running
    assert listeners[0].stop_calls == 1
    assert not monitor.poll()

    assert monitor.start()
    assert len(listeners) == 2
    monitor.stop()
    assert listeners[1].stop_calls == 1


def test_keyboard_mouse_monitor_does_not_replace_timed_out_live_listener():
    startup_entered = threading.Event()
    release_startup = threading.Event()
    listeners = []

    class _DelayedRawInputListener(_WindowsRawInputListener):
        def __init__(self, callback):
            super().__init__(
                callback,
                start_timeout_s=0.01,
                stop_timeout_s=0.01,
            )
            self.startup_calls = 0

        def _before_startup(self):
            self.startup_calls += 1
            startup_entered.set()
            release_startup.wait(timeout=1.0)

    def factory(callback):
        if not listeners:
            listener = _DelayedRawInputListener(callback)
        else:
            listener = _Listener(callback)
        listeners.append(listener)
        return listener

    monitor = KeyboardMouseActivityMonitor(factory)

    assert not monitor.start()
    assert startup_entered.is_set()
    delayed_listener = listeners[0]
    assert delayed_listener.alive
    assert delayed_listener.startup_calls == 1

    assert not monitor.start()
    assert len(listeners) == 1
    assert delayed_listener.startup_calls == 1

    worker = delayed_listener._thread
    assert worker is not None
    release_startup.set()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert not delayed_listener.alive
    assert delayed_listener._thread is None

    assert monitor.start()
    assert len(listeners) == 2
    assert monitor.running
    monitor.stop()
    assert not monitor.running


def test_keyboard_mouse_monitor_fails_open_when_listener_start_raises():
    def factory(callback):
        return _Listener(callback, start_error=OSError("input desktop unavailable"))

    monitor = KeyboardMouseActivityMonitor(factory)

    assert not monitor.start()
    assert monitor.available
    assert not monitor.running
    assert not monitor.poll()


def test_tui_system_status_exposes_keyboard_mouse_owner_and_resume_hint():
    source = (ROOT / "src/modules/tui/system_tab.py").read_text(encoding="utf-8")

    assert "InputOwner.KEYBOARD_MOUSE" in source
    assert 't("Keyboard and mouse active")' in source
    assert "Virtual Xbox input is neutral; move or press the DualSense to resume" in source


def test_controller_activity_ignores_noise_but_accepts_accumulated_motion():
    baseline = _state()

    assert not controller_input_changed(baseline, _state(left_x=139))
    assert controller_input_changed(baseline, _state(left_x=140))
    assert not controller_input_changed(baseline, _state(left_trigger=7))
    assert controller_input_changed(baseline, _state(left_trigger=8))


def test_controller_buttons_and_dpad_are_deliberate_activity():
    baseline = _state()

    assert controller_input_is_active(
        _state(buttons=frozenset({DualSenseButton.CROSS}))
    )
    assert controller_input_changed(baseline, _state(dpad=DPad.NORTH))
    assert not controller_input_is_active(_state())
