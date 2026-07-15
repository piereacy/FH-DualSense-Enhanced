from __future__ import annotations

import logging
import sys
import threading
import time
from collections.abc import Sequence

from .frame import HapticFrame, SILENT_FRAME
from .pcm import HapticPcmRenderer

try:
    import numpy as np
    import sounddevice as sd
except (ImportError, OSError):
    np = None
    sd = None

log = logging.getLogger("fhds.haptics.audio")


def find_dualsense_output_device(
    devices: Sequence[dict],
    hostapis: Sequence[dict],
    platform: str | None = None,
) -> int | None:
    platform = platform or sys.platform
    if platform.startswith("win"):
        supported_apis = {
            index for index, api in enumerate(hostapis)
            if str(api.get("name", "")).lower() == "windows wasapi"
        }
    elif platform.startswith("linux"):
        supported_apis = {
            index for index, api in enumerate(hostapis)
            if "alsa" in str(api.get("name", "")).lower()
        }
    else:
        return None

    for index, device in enumerate(devices):
        name = str(device.get("name", "")).lower()
        if (device.get("hostapi") in supported_apis
                and int(device.get("max_output_channels", 0)) >= 4
                and ("dualsense" in name or "wireless controller" in name)):
            return index
    return None


class UsbAudioHaptics:
    def __init__(
        self,
        sounddevice_module=sd,
        numpy_module=np,
        platform: str | None = None,
        sample_rate: int = 48_000,
        blocksize: int = 512,
        renderer: HapticPcmRenderer | None = None,
    ):
        self._sd = sounddevice_module
        self._np = numpy_module
        self._platform = platform or sys.platform
        self.sample_rate = sample_rate
        self.blocksize = blocksize
        self.channels = 4
        self._stream = None
        self._running = False
        self._device_index: int | None = None
        self._frame = SILENT_FRAME
        self._frame_lock = threading.Lock()
        self._renderer = renderer
        if self._renderer is None and self._np is not None:
            self._renderer = HapticPcmRenderer(
                numpy_module=self._np,
                sample_rate=self.sample_rate,
            )
        self._last_status_log = 0.0
        self._warned: set[str] = set()

    @property
    def running(self) -> bool:
        return self._running

    def _warn_once(self, key: str, message: str, *args) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        log.warning(message, *args)

    def start(self) -> bool:
        if self._running:
            return True
        if self._sd is None or self._np is None:
            self._warn_once("dependencies", "USB body haptics unavailable: NumPy or sounddevice is missing.")
            return False

        try:
            hostapis = self._sd.query_hostapis()
            devices = self._sd.query_devices()
            device_index = find_dualsense_output_device(devices, hostapis, self._platform)
            if device_index is None:
                self._warn_once(
                    "endpoint",
                    "No four-channel DualSense audio endpoint found. Connect the controller over USB.",
                )
                return False

            self._device_index = device_index
            self._stream = self._sd.OutputStream(
                device=device_index,
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype="float32",
                blocksize=self.blocksize,
                callback=self._audio_callback,
                latency="low",
            )
            self._running = True
            self._stream.start()
            log.info("USB body haptics started on audio device %d", device_index)
            return True
        except Exception as exc:
            self._running = False
            stream, self._stream = self._stream, None
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            self._warn_once("start", "USB body haptics failed to start: %s", exc)
            return False

    def set_frame(self, frame: HapticFrame) -> None:
        with self._frame_lock:
            self._frame = frame

    def stop(self) -> None:
        self.set_frame(SILENT_FRAME)
        self._running = False
        stream, self._stream = self._stream, None
        if stream is None:
            return
        try:
            stream.stop()
        except Exception:
            pass
        try:
            stream.close()
        except Exception:
            pass
        if self._renderer is not None:
            self._renderer.reset()

    def _audio_callback(self, outdata, frames, time_info, status) -> None:
        del time_info
        if status:
            now = time.monotonic()
            if now - self._last_status_log >= 1.0:
                self._last_status_log = now
                log.debug("USB body haptics audio status: %s", status)

        if (
            not self._running
            or self._np is None
            or self._renderer is None
            or outdata.shape[1] < 4
        ):
            outdata.fill(0.0)
            return

        with self._frame_lock:
            frame = self._frame

        pcm = self._renderer.render(frame, frames)

        outdata.fill(0.0)
        outdata[:, 2] = pcm[:, 0]
        outdata[:, 3] = pcm[:, 1]
