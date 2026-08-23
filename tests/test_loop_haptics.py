from modules import loop
from modules.config.settings import Settings
from modules.dualsense.adaptive_trigger import off, rigid, vibrate
from modules.dualsense.output_state import ControllerVisualState
from modules.haptics.frame import (
    CompatibleRumble,
    HapticFrame,
    SILENT_FRAME,
    to_compatible_rumble,
)
from modules.haptics.manager import HapticManager
from modules.haptics.lab import HapticsLab


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

    def set(self, *args, visual=None):
        self.calls.append(args)

class _DisconnectedDualSense(_DualSense):
    connected = False


class _LiveDisableDualSense(_DualSense):
    transport = "bluetooth"

    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    def set(self, *args, visual=None):
        super().set(*args, visual=visual)
        if len(self.calls) == 1:
            self.settings.enable_body_haptics = False


class _VisualDualSense(_DualSense):
    def __init__(self):
        super().__init__()
        self.visuals = []

    def set(self, *args, visual=None):
        self.visuals.append(visual)
        super().set(*args, visual=visual)


class _TriggerController:
    def __init__(self, settings):
        self.settings = settings

    def update(self, telemetry, settings, collision_signal=None):
        return LEFT, RIGHT


class _FailingTriggerController:
    def __init__(self, settings):
        pass

    def update(self, telemetry, settings, collision_signal=None):
        raise RuntimeError("synthetic trigger failure")


class _Mixer:
    instances = []

    def __init__(self):
        self.calls = []
        self.reset_calls = 0
        type(self).instances.append(self)

    def update(self, telemetry, settings, now, collision_signal=None):
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
        self.force_flags = []
        self.pause_calls = 0
        self.closed = False
        type(self).instances.append(self)

    def route(self, frame, *, force=False):
        self.frames.append(frame)
        self.force_flags.append(force)
        if type(self).raises:
            raise RuntimeError("haptic failure")
        return SILENT_RUMBLE if frame == SILENT_FRAME else RUMBLE

    def close(self):
        self.closed = True

    def pause(self):
        self.pause_calls += 1


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


def test_haptics_lab_uses_the_existing_feedback_output(monkeypatch):
    _install(monkeypatch)
    settings = _settings()
    settings.enable_body_haptics = False
    controller = _DualSense()
    listener = _Listener([])
    lab = HapticsLab()
    lab.start("brake_resistance", intensity=0.4, duration_s=1.0)

    loop.run(
        controller,
        listener,
        settings,
        stop_event=_StopEvent(2),
        haptics_lab=lab,
    )

    manager = _Manager.instances[-1]
    assert True in manager.force_flags
    assert any(call[0] != off() for call in controller.calls)


def test_live_telemetry_preempts_an_active_lab_preview(monkeypatch):
    _install(monkeypatch)
    controller = _DualSense()
    lab = HapticsLab()
    lab.start("road")

    loop.run(
        controller,
        _Listener([(b"packet", ("127.0.0.1", 5300))]),
        _settings(),
        stop_event=_StopEvent(1),
        haptics_lab=lab,
    )

    assert lab.snapshot().stop_reason == "game_telemetry"
    assert True in _Manager.instances[-1].force_flags
    assert _Mixer.instances[-1].calls


def test_haptics_lab_drops_pending_request_when_controller_disconnects(monkeypatch):
    _install(monkeypatch)
    controller = _DisconnectedDualSense()
    lab = HapticsLab()
    lab.start("brake_resistance")

    loop.run(
        controller,
        _Listener([]),
        _settings(),
        stop_event=_StopEvent(1),
        haptics_lab=lab,
    )

    assert lab.snapshot().stop_reason == "controller_disconnected"
    assert True not in _Manager.instances[-1].force_flags


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
    routed_telemetry = _Mixer.instances[0].calls[0][0]
    assert routed_telemetry["effective_redline_rpm"] == 0.0
    assert routed_telemetry["rev_limiter_active"] is False
    assert routed_telemetry["redline_alert_allowed"] is True
    assert controller.calls == [
        (LEFT, RIGHT, RUMBLE),
        (off(), off(), SILENT_RUMBLE),
    ]
    assert manager.closed is True


def test_active_haptics_lab_preview_uses_a_short_udp_wait(monkeypatch):
    _install(monkeypatch)

    class BoundedUDPListener:
        def __init__(self):
            self.waits = []
            self.lost = False

        def recv_latest(self, *, wait_timeout_s=None):
            self.waits.append(wait_timeout_s)
            return None, None

    monkeypatch.setattr(loop.forzahorizon, "UDPListener", BoundedUDPListener)
    listener = BoundedUDPListener()
    lab = HapticsLab()
    lab.start("road")

    loop.run(
        _DualSense(),
        listener,
        _settings(),
        stop_event=_StopEvent(1),
        haptics_lab=lab,
    )

    assert listener.waits == [0.05]


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


def test_malformed_traffic_cannot_keep_the_last_feedback_latched(monkeypatch):
    _install(monkeypatch)
    valid_parser = loop.forzahorizon.parse_packet

    def parse(packet):
        if packet == b"bad":
            raise ValueError("synthetic malformed telemetry")
        return valid_parser(packet)

    monkeypatch.setattr(loop.forzahorizon, "parse_packet", parse)
    ticks = iter((0.0, 0.0, 1.2))
    monkeypatch.setattr(loop.time, "monotonic", lambda: next(ticks))
    controller = _DualSense()
    listener = _Listener([
        (b"packet", ("127.0.0.1", 5300)),
        (b"bad", ("127.0.0.1", 5300)),
    ])

    loop.run(controller, listener, _settings(), stop_event=_StopEvent(2))

    assert _Mixer.instances[0].reset_calls == 1
    assert _Manager.instances[0].frames == [FRAME, SILENT_FRAME, SILENT_FRAME]
    assert controller.calls == [
        (LEFT, RIGHT, RUMBLE),
        (off(), off(), SILENT_RUMBLE),
    ]


def test_telemetry_loss_does_not_exit_when_game_close_exit_is_disabled(monkeypatch):
    _install(monkeypatch)
    ticks = iter((0.0, 0.0, 61.0, 62.0))
    monkeypatch.setattr(loop.time, "monotonic", lambda: next(ticks))
    controller = _DualSense()
    listener = _Listener([
        (b"packet", ("127.0.0.1", 5300)),
        (None, None),
        (None, None),
    ])
    stop_event = _StopEvent(3)

    loop.run(controller, listener, _settings(), stop_event=stop_event)

    assert stop_event.calls == 4


def test_telemetry_loss_exits_when_game_close_exit_is_enabled(monkeypatch):
    _install(monkeypatch)
    ticks = iter((0.0, 0.0, 61.0))
    monkeypatch.setattr(loop.time, "monotonic", lambda: next(ticks))
    controller = _DualSense()
    listener = _Listener([
        (b"packet", ("127.0.0.1", 5300)),
        (None, None),
    ])
    stop_event = _StopEvent(5)
    settings = _settings()
    settings.exit_on_game_close = True

    loop.run(controller, listener, settings, stop_event=stop_event)

    assert stop_event.calls == 2


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


def test_trigger_failure_releases_triggers_without_dropping_body_haptics(monkeypatch):
    _install(monkeypatch)
    monkeypatch.setattr(loop.forzahorizon, "Controller", _FailingTriggerController)
    controller = _DualSense()
    listener = _Listener([(b"packet", ("127.0.0.1", 5300))])

    loop.run(controller, listener, _settings(), stop_event=_StopEvent(1))

    assert _Manager.instances[0].frames == [FRAME, SILENT_FRAME]
    assert controller.calls == [
        (off(), off(), RUMBLE),
        (off(), off(), SILENT_RUMBLE),
    ]


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


def test_loop_forwards_atomic_visual_state_and_blanks_it_on_shutdown(monkeypatch):
    _install(monkeypatch)
    active = ControllerVisualState(lightbar=(57, 197, 187), player_leds=0x04)
    blank = ControllerVisualState(lightbar=(0, 0, 0), player_leds=0)

    class _Lighting:
        def update(self, telemetry, settings, now):
            return active if telemetry.get("on") else blank

    monkeypatch.setattr(loop.forzahorizon, "LightingController", _Lighting)
    controller = _VisualDualSense()
    listener = _Listener([(b"packet", ("127.0.0.1", 5300))])

    loop.run(controller, listener, _settings(), stop_event=_StopEvent(1))

    assert controller.visuals == [active, blank]
