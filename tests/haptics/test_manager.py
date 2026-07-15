from modules.config.settings import Settings
from modules.haptics.frame import (
    CompatibleRumble,
    HapticFrame,
    SILENT_FRAME,
    to_compatible_rumble,
)
from modules.haptics.manager import HapticManager


class _Controller:
    def __init__(self, transport="usb", is_dsx=False):
        self.transport = transport
        self.is_dsx = is_dsx


class _Audio:
    def __init__(self, starts=True):
        self.starts = starts
        self.running = False
        self.start_calls = 0
        self.stop_calls = 0
        self.frames = []

    def start(self):
        self.start_calls += 1
        self.running = self.starts
        return self.starts

    def set_frame(self, frame):
        self.frames.append(frame)

    def stop(self):
        self.stop_calls += 1
        self.running = False


class _AudioFactory:
    def __init__(self, starts=True):
        self.starts = starts
        self.instances = []

    def __call__(self):
        value = _Audio(self.starts)
        self.instances.append(value)
        return value


def _settings(enabled=True):
    value = Settings()
    value.enable_body_haptics = enabled
    return value


def test_usb_starts_audio_once_and_publishes_every_frame():
    factory = _AudioFactory()
    manager = HapticManager(_Controller("usb"), _settings(), audio_factory=factory)
    first = HapticFrame(left_low=0.2)
    second = HapticFrame(right_high=0.4)

    assert manager.route(first) is None
    assert manager.route(second) is None

    audio = factory.instances[0]
    assert len(factory.instances) == 1
    assert audio.start_calls == 1
    assert audio.frames == [first, second]


def test_bluetooth_returns_compatible_rumble_without_creating_audio():
    factory = _AudioFactory()
    manager = HapticManager(_Controller("bluetooth"), _settings(), audio_factory=factory)
    frame = HapticFrame(left_low=0.4, right_high=0.7, engine_amplitude=0.2)

    assert manager.route(frame) == to_compatible_rumble(frame)
    assert factory.instances == []


def test_bluetooth_uses_explicit_priority_event_motor_projection():
    factory = _AudioFactory()
    manager = HapticManager(_Controller("bluetooth"), _settings(), audio_factory=factory)
    frame = HapticFrame(
        left_high=0.8,
        compatible_low_frequency=0.8,
        compatible_high_frequency=0.0,
    )

    assert manager.route(frame) == CompatibleRumble(
        low_frequency=0.8,
        high_frequency=0.0,
    )
    assert factory.instances == []


def test_disabling_bluetooth_releases_rumble_exactly_once():
    settings = _settings()
    manager = HapticManager(_Controller("bluetooth"), settings)

    assert manager.route(HapticFrame(left_low=0.4)) == CompatibleRumble(
        low_frequency=0.4
    )

    settings.enable_body_haptics = False

    assert manager.route(HapticFrame(left_low=0.4)) == CompatibleRumble()
    assert manager.route(HapticFrame(left_low=0.4)) is None


def test_switching_from_usb_to_bluetooth_stops_audio():
    controller = _Controller("usb")
    factory = _AudioFactory()
    manager = HapticManager(controller, _settings(), audio_factory=factory)
    manager.route(HapticFrame(left_low=0.2))
    audio = factory.instances[0]

    controller.transport = "bluetooth"
    rumble = manager.route(HapticFrame(right_low=0.6))

    assert audio.stop_calls == 1
    assert rumble == to_compatible_rumble(HapticFrame(right_low=0.6))


def test_disabling_after_usb_stops_audio_and_returns_none():
    settings = _settings()
    factory = _AudioFactory()
    manager = HapticManager(_Controller("usb"), settings, audio_factory=factory)
    manager.route(HapticFrame(left_low=0.2))
    audio = factory.instances[0]

    settings.enable_body_haptics = False

    assert manager.route(HapticFrame(right_low=0.6)) is None
    assert audio.stop_calls == 1


def test_disconnect_stops_audio_and_silences_output():
    controller = _Controller("usb")
    factory = _AudioFactory()
    manager = HapticManager(controller, _settings(), audio_factory=factory)
    manager.route(HapticFrame(left_low=0.2))
    audio = factory.instances[0]

    controller.transport = None

    assert manager.route(HapticFrame(right_low=0.6)) is None
    assert audio.stop_calls == 1


def test_dsx_never_creates_a_body_haptics_backend():
    factory = _AudioFactory()
    manager = HapticManager(_Controller(None, is_dsx=True), _settings(), audio_factory=factory)

    assert manager.route(HapticFrame(left_low=1.0)) is None
    assert factory.instances == []


def test_silence_keeps_usb_stream_open_but_publishes_silent_frame():
    factory = _AudioFactory()
    manager = HapticManager(_Controller("usb"), _settings(), audio_factory=factory)
    manager.route(HapticFrame(left_low=0.2))
    audio = factory.instances[0]

    assert manager.route(SILENT_FRAME) is None
    assert audio.running is True
    assert audio.frames[-1] == SILENT_FRAME


def test_close_is_idempotent_and_stops_audio():
    factory = _AudioFactory()
    manager = HapticManager(_Controller("usb"), _settings(), audio_factory=factory)
    manager.route(HapticFrame(left_low=0.2))
    audio = factory.instances[0]

    manager.close()
    manager.close()

    assert audio.stop_calls == 1


def test_failed_usb_start_is_not_retried_for_every_telemetry_frame():
    factory = _AudioFactory(starts=False)
    manager = HapticManager(_Controller("usb"), _settings(), audio_factory=factory)

    manager.route(HapticFrame(left_low=0.2))
    manager.route(HapticFrame(right_low=0.3))

    assert factory.instances[0].start_calls == 1


def test_failed_usb_start_is_retried_after_transport_reconnect():
    controller = _Controller("usb")
    factory = _AudioFactory(starts=False)
    manager = HapticManager(controller, _settings(), audio_factory=factory)

    manager.route(HapticFrame(left_low=0.2))
    controller.transport = None
    manager.route(SILENT_FRAME)
    controller.transport = "usb"
    manager.route(HapticFrame(right_low=0.3))

    assert factory.instances[0].start_calls == 2


def test_external_usb_audio_receives_frames_without_worker_lifecycle_calls():
    audio = _Audio()
    manager = HapticManager(_Controller("usb"), _settings(), audio=audio)
    frame = HapticFrame(left_low=0.3)

    assert manager.route(frame) is None
    manager.close()

    assert audio.start_calls == 0
    assert audio.stop_calls == 0
    assert audio.frames == [frame, SILENT_FRAME]


def test_external_usb_audio_does_not_change_bluetooth_routing():
    audio = _Audio()
    manager = HapticManager(_Controller("bluetooth"), _settings(), audio=audio)
    frame = HapticFrame(right_high=0.7)

    assert manager.route(frame) == to_compatible_rumble(frame)
    assert audio.start_calls == 0
    assert audio.stop_calls == 0
    assert audio.frames == [SILENT_FRAME]
