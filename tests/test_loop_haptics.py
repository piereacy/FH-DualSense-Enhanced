from modules import loop
from modules.config.settings import Settings
from modules.dualsense.adaptive_trigger import off, rigid, vibrate
from modules.haptics.frame import (
    CompatibleRumble,
    HapticFrame,
    SILENT_FRAME,
    to_compatible_rumble,
)
from modules.haptics.manager import HapticManager


LEFT = rigid(30)
RIGHT = vibrate(20, 10)
FRAME = HapticFrame(left_low=0.4)
RUMBLE = CompatibleRumble(low_frequency=0.4, high_frequency=0.2)
SILENT_RUMBLE = CompatibleRumble()


class _StopEvent:
    def __init__(self, iterations):
        self.iterations = iterations
        self.calls = 0

    def is_set(self):
        self.calls += 1
        return self.calls > self.iterations


class _Listener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.lost = False

    def recv_latest(self):
        if self.responses:
            return self.responses.pop(0)
        return None, None


class _DualSense:
    is_dsx = False

    def __init__(self):
        self.calls = []

    def set(self, *args):
        self.calls.append(args)


class _LiveDisableDualSense(_DualSense):
    transport = "bluetooth"

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    def set(self, *args):
        super().set(*args)
        if len(self.calls) == 1:
            self.settings.enable_body_haptics = False


class _TriggerController:
    def __init__(self, settings):
        self.settings = settings

    def update(self, telemetry, settings):
        return LEFT, RIGHT


class _Mixer:
    instances = []

    def __init__(self):
        self.calls = []
        self.reset_calls = 0
        type(self).instances.append(self)

    def update(self, telemetry, settings, now):
        self.calls.append((telemetry, now))
        return FRAME

    def reset(self):
        self.reset_calls += 1


class _Manager:
    instances = []
    raises = False

    def __init__(self, controller, settings, audio=None):
        self.controller = controller
        self.audio = audio
        self.frames = []
        self.closed = False
        type(self).instances.append(self)

    def route(self, frame):
        self.frames.append(frame)
        if type(self).raises:
            raise RuntimeError("haptic failure")
        return SILENT_RUMBLE if frame == SILENT_FRAME else RUMBLE

    def close(self):
        self.closed = True


class _Watcher:
    def __init__(self, *args):
        pass

    def should_exit(self):
        return False


def _install(monkeypatch, manager_class=_Manager):
    _Mixer.instances.clear()
    _Manager.instances.clear()
    _Manager.raises = False
    monkeypatch.setattr(loop, "HapticMixer", _Mixer, raising=False)
    monkeypatch.setattr(loop, "HapticManager", manager_class, raising=False)
    monkeypatch.setattr(loop, "ProcessWatcher", _Watcher)
    monkeypatch.setattr(loop.forzahorizon, "Controller", _TriggerController)
    telemetry = {
        "on": True,
        "speed": 50.0,
        "gear": 2,
        "accel": 100,
        "brake": 20,
    }
    for prefix in ("tire_slip_ratio", "tire_combined_slip"):
        for wheel in ("fl", "fr", "rl", "rr"):
            telemetry[f"{prefix}_{wheel}"] = 0.0
    monkeypatch.setattr(loop.forzahorizon, "parse_packet", lambda packet: telemetry)


def _settings():
    value = Settings()
    value.enable_body_haptics = True
    value.exit_on_game_close = False
    return value


def test_packet_routes_haptics_and_writes_one_atomic_controller_frame(monkeypatch):
    _install(monkeypatch)
    controller = _DualSense()
    listener = _Listener([(b"packet", ("127.0.0.1", 5300))])

    loop.run(controller, listener, _settings(), stop_event=_StopEvent(1))

    manager = _Manager.instances[0]
    assert manager.frames == [FRAME, SILENT_FRAME]
    assert controller.calls == [
        (LEFT, RIGHT, RUMBLE),
        (off(), off(), SILENT_RUMBLE),
    ]
    assert manager.closed is True


def test_live_disable_forwards_one_rumble_release_then_trigger_only(monkeypatch):
    _install(monkeypatch, manager_class=HapticManager)
    settings = _settings()
    controller = _LiveDisableDualSense(settings)
    listener = _Listener([
        (b"packet", ("127.0.0.1", 5300)),
        (b"packet", ("127.0.0.1", 5300)),
        (b"packet", ("127.0.0.1", 5300)),
    ])

    loop.run(controller, listener, settings, stop_event=_StopEvent(3))

    assert controller.calls == [
        (LEFT, RIGHT, to_compatible_rumble(FRAME)),
        (LEFT, RIGHT, SILENT_RUMBLE),
        (LEFT, RIGHT, None),
        (off(), off(), None),
    ]


def test_idle_timeout_sends_silent_haptics_and_trigger_off(monkeypatch):
    _install(monkeypatch)
    ticks = iter((0.0, 0.0, 1.2))
    monkeypatch.setattr(loop.time, "monotonic", lambda: next(ticks))
    controller = _DualSense()
    listener = _Listener([
        (b"packet", ("127.0.0.1", 5300)),
        (None, None),
    ])

    loop.run(controller, listener, _settings(), stop_event=_StopEvent(2))

    assert _Manager.instances[0].frames == [FRAME, SILENT_FRAME, SILENT_FRAME]
    assert _Mixer.instances[0].reset_calls == 1
    assert controller.calls == [
        (LEFT, RIGHT, RUMBLE),
        (off(), off(), SILENT_RUMBLE),
    ]


def test_haptics_failure_does_not_block_trigger_output(monkeypatch):
    _install(monkeypatch)
    _Manager.raises = True
    controller = _DualSense()
    listener = _Listener([(b"packet", ("127.0.0.1", 5300))])

    loop.run(controller, listener, _settings(), stop_event=_StopEvent(1))

    assert controller.calls == [
        (LEFT, RIGHT, None),
        (off(), off(), None),
    ]
    assert _Manager.instances[0].closed is True


def test_loop_injects_shared_usb_audio_into_haptic_manager(monkeypatch):
    _install(monkeypatch)
    controller = _DualSense()
    listener = _Listener([(b"packet", ("127.0.0.1", 5300))])
    shared_audio = object()

    loop.run(
        controller,
        listener,
        _settings(),
        stop_event=_StopEvent(1),
        usb_audio=shared_audio,
    )

    assert _Manager.instances[0].audio is shared_audio
