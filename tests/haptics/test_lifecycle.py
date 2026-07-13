from modules.config.settings import Settings
from modules.haptics.frame import SILENT_FRAME
from modules.haptics.lifecycle import UsbAudioLifecycle


class _Controller:
    def __init__(self, transport="usb", is_dsx=False):
        self.transport = transport
        self.is_dsx = is_dsx


class _Audio:
    def __init__(self, outcomes=(True,), running=False):
        self.outcomes = list(outcomes)
        self.running = running
        self.start_calls = 0
        self.stop_calls = 0
        self.frames = []

    def start(self):
        self.start_calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else True
        self.running = outcome
        return outcome

    def set_frame(self, frame):
        self.frames.append(frame)

    def stop(self):
        self.stop_calls += 1
        self.running = False


def _settings(enabled=True):
    value = Settings()
    value.enable_body_haptics = enabled
    return value


def test_sync_starts_eligible_usb_audio_once():
    audio = _Audio()
    lifecycle = UsbAudioLifecycle(audio)

    assert lifecycle.sync(_Controller("usb"), _settings()) is True
    assert lifecycle.sync(_Controller("usb"), _settings()) is True
    assert audio.start_calls == 1


def test_sync_retries_a_failed_usb_start():
    audio = _Audio(outcomes=(False, True))
    lifecycle = UsbAudioLifecycle(audio)

    assert lifecycle.sync(_Controller("usb"), _settings()) is False
    assert lifecycle.sync(_Controller("usb"), _settings()) is True
    assert audio.start_calls == 2


def test_sync_silences_and_stops_audio_when_usb_becomes_ineligible():
    audio = _Audio(running=True)
    lifecycle = UsbAudioLifecycle(audio)

    assert lifecycle.sync(_Controller("bluetooth"), _settings()) is False
    assert audio.frames == [SILENT_FRAME]
    assert audio.stop_calls == 1


def test_sync_never_starts_usb_audio_for_dsx_or_bluetooth():
    controllers = (_Controller("bluetooth"), _Controller(None, is_dsx=True))
    for controller in controllers:
        audio = _Audio()
        lifecycle = UsbAudioLifecycle(audio)

        assert lifecycle.sync(controller, _settings()) is False
        assert audio.start_calls == 0


def test_close_is_idempotent():
    audio = _Audio(running=True)
    lifecycle = UsbAudioLifecycle(audio)

    lifecycle.close()
    lifecycle.close()

    assert audio.frames == [SILENT_FRAME]
    assert audio.stop_calls == 1
