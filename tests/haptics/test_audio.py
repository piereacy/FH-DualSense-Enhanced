import numpy as np

from modules.haptics import audio as audio_module
from modules.haptics.audio import UsbAudioHaptics, find_dualsense_output_device
from modules.haptics.frame import HapticFrame


class _FakeStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.callback = kwargs["callback"]
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class _FakeSoundDevice:
    def __init__(self, devices=None):
        self._hostapis = [{"name": "Windows WASAPI"}]
        self._devices = devices if devices is not None else [{
            "name": "DualSense Wireless Controller",
            "hostapi": 0,
            "max_output_channels": 4,
        }]
        self.stream = None

    def query_hostapis(self):
        return self._hostapis

    def query_devices(self):
        return self._devices

    def OutputStream(self, **kwargs):
        self.stream = _FakeStream(**kwargs)
        return self.stream


def _devices():
    return [
        {
            "name": "DualSense Wireless Controller microphone",
            "hostapi": 0,
            "max_output_channels": 0,
        },
        {
            "name": "DualSense Wireless Controller stereo",
            "hostapi": 0,
            "max_output_channels": 2,
        },
        {
            "name": "DualSense Wireless Controller",
            "hostapi": 1,
            "max_output_channels": 4,
        },
        {
            "name": "DualSense Wireless Controller",
            "hostapi": 2,
            "max_output_channels": 4,
        },
    ]


def test_windows_selects_four_channel_wasapi_dualsense():
    hostapis = [
        {"name": "MME"},
        {"name": "Windows WASAPI"},
        {"name": "Windows DirectSound"},
    ]

    assert find_dualsense_output_device(_devices(), hostapis, "win32") == 2


def test_linux_selects_four_channel_alsa_dualsense():
    hostapis = [
        {"name": "PulseAudio"},
        {"name": "JACK"},
        {"name": "ALSA"},
    ]

    assert find_dualsense_output_device(_devices(), hostapis, "linux") == 3


def test_selection_rejects_non_dualsense_and_stereo_devices():
    devices = [
        {"name": "Speakers", "hostapi": 0, "max_output_channels": 8},
        {"name": "Wireless Controller", "hostapi": 0, "max_output_channels": 2},
    ]

    assert find_dualsense_output_device(devices, [{"name": "Windows WASAPI"}], "win32") is None


def test_selection_returns_none_without_supported_host_api():
    assert find_dualsense_output_device(_devices(), [{"name": "MME"}], "win32") is None


def test_start_opens_four_channel_float32_stream():
    fake_sd = _FakeSoundDevice()
    audio = UsbAudioHaptics(sounddevice_module=fake_sd, numpy_module=np, platform="win32")

    assert audio.start() is True
    assert audio.running is True
    assert fake_sd.stream.started is True
    assert fake_sd.stream.kwargs["samplerate"] == 48000
    assert fake_sd.stream.kwargs["channels"] == 4
    assert fake_sd.stream.kwargs["dtype"] == "float32"


def test_default_sounddevice_is_loaded_only_when_usb_stream_starts(monkeypatch):
    fake_sd = _FakeSoundDevice()
    loads = []

    def load_sounddevice():
        loads.append("sounddevice")
        return fake_sd

    monkeypatch.setattr(audio_module, "_load_sounddevice", load_sounddevice)
    audio = UsbAudioHaptics(numpy_module=np, platform="win32")

    assert loads == []
    assert audio.start() is True
    assert loads == ["sounddevice"]
    assert audio.start() is True
    assert loads == ["sounddevice"]


def test_callback_routes_left_haptics_only_to_channel_three():
    fake_sd = _FakeSoundDevice()
    audio = UsbAudioHaptics(sounddevice_module=fake_sd, numpy_module=np, platform="win32")
    assert audio.start()
    audio.set_frame(HapticFrame(left_low=1.0))
    out = np.zeros((128, 4), dtype=np.float32)

    fake_sd.stream.callback(out, len(out), None, None)

    assert np.all(out[:, 0] == 0.0)
    assert np.all(out[:, 1] == 0.0)
    assert np.any(out[:, 2] != 0.0)
    assert np.all(out[:, 3] == 0.0)


def test_callback_routes_right_haptics_only_to_channel_four():
    fake_sd = _FakeSoundDevice()
    audio = UsbAudioHaptics(sounddevice_module=fake_sd, numpy_module=np, platform="win32")
    assert audio.start()
    audio.set_frame(HapticFrame(right_high=1.0))
    out = np.zeros((128, 4), dtype=np.float32)

    fake_sd.stream.callback(out, len(out), None, None)

    assert np.all(out[:, 0] == 0.0)
    assert np.all(out[:, 1] == 0.0)
    assert np.all(out[:, 2] == 0.0)
    assert np.any(out[:, 3] != 0.0)


def test_stop_silences_callback_and_closes_stream():
    fake_sd = _FakeSoundDevice()
    audio = UsbAudioHaptics(sounddevice_module=fake_sd, numpy_module=np, platform="win32")
    assert audio.start()
    stream = fake_sd.stream
    audio.set_frame(HapticFrame(left_low=1.0, right_low=1.0))

    audio.stop()
    out = np.ones((64, 4), dtype=np.float32)
    stream.callback(out, len(out), None, None)

    assert np.all(out == 0.0)
    assert audio.running is False
    assert stream.stopped is True
    assert stream.closed is True


def test_start_fails_cleanly_without_dependencies_or_endpoint():
    without_dependencies = UsbAudioHaptics(
        sounddevice_module=None,
        numpy_module=None,
        platform="win32",
    )
    without_endpoint = UsbAudioHaptics(
        sounddevice_module=_FakeSoundDevice(devices=[]),
        numpy_module=np,
        platform="win32",
    )

    assert without_dependencies.start() is False
    assert without_endpoint.start() is False
