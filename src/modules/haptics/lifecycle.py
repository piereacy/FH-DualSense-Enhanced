from __future__ import annotations

from .audio import UsbAudioHaptics
from .frame import SILENT_FRAME


class UsbAudioLifecycle:
    def __init__(self, audio: UsbAudioHaptics | None = None):
        self.audio = audio or UsbAudioHaptics()

    def sync(self, controller, settings) -> bool:
        eligible = (
            bool(getattr(settings, "enable_body_haptics", False))
            and controller is not None
            and not bool(getattr(controller, "is_dsx", False))
            and getattr(controller, "transport", None) == "usb"
        )
        if eligible:
            if self.audio.running:
                return True
            return bool(self.audio.start())
        self._silence_and_stop()
        return False

    def _silence_and_stop(self) -> None:
        if not self.audio.running:
            return
        self.audio.set_frame(SILENT_FRAME)
        self.audio.stop()

    def close(self) -> None:
        self._silence_and_stop()
