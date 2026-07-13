from __future__ import annotations

import logging
from collections.abc import Callable

from .audio import UsbAudioHaptics
from .frame import CompatibleRumble, HapticFrame, SILENT_FRAME, to_compatible_rumble

log = logging.getLogger("fhds.haptics")


class HapticManager:
    def __init__(
        self,
        controller,
        settings,
        audio_factory: Callable[[], UsbAudioHaptics] = UsbAudioHaptics,
    ):
        self._controller = controller
        self._settings = settings
        self._audio_factory = audio_factory
        self._audio = None
        self._mode: str | None = None
        self._last_transport: str | None = None
        self._bluetooth_rumble_owned = False
        self._usb_start_failed = False
        self._closed = False
        self._warned: set[str] = set()

    @property
    def mode(self) -> str | None:
        return self._mode

    def _warn_once(self, key: str, message: str, *args) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        log.warning(message, *args)

    def _stop_audio(self) -> None:
        if self._audio is None or not self._audio.running:
            return
        try:
            self._audio.set_frame(SILENT_FRAME)
            self._audio.stop()
        except Exception as exc:
            self._warn_once("audio-stop", "USB body haptics failed to stop cleanly: %s", exc)

    def _route_usb(self, frame: HapticFrame) -> None:
        if self._usb_start_failed:
            return
        try:
            if self._audio is None:
                self._audio = self._audio_factory()
            if not self._audio.running and not self._audio.start():
                self._usb_start_failed = True
                self._mode = None
                return
            self._audio.set_frame(frame)
            self._mode = "usb"
        except Exception as exc:
            self._usb_start_failed = True
            self._warn_once("audio-route", "USB body haptics backend failed: %s", exc)
            self._stop_audio()
            self._mode = None

    def route(self, frame: HapticFrame) -> CompatibleRumble | None:
        if self._closed:
            return None
        if not getattr(self._settings, "enable_body_haptics", False):
            release_bluetooth = (
                self._bluetooth_rumble_owned
                and not getattr(self._controller, "is_dsx", False)
                and getattr(self._controller, "transport", None) == "bluetooth"
            )
            self._bluetooth_rumble_owned = False
            self._stop_audio()
            self._mode = None
            self._last_transport = None
            self._usb_start_failed = False
            return CompatibleRumble() if release_bluetooth else None
        if getattr(self._controller, "is_dsx", False):
            self._bluetooth_rumble_owned = False
            self._stop_audio()
            self._mode = None
            self._last_transport = None
            self._usb_start_failed = False
            self._warn_once("dsx", "Body haptics are unavailable while the DSX backend is active.")
            return None

        transport = getattr(self._controller, "transport", None)
        if transport != self._last_transport:
            self._last_transport = transport
            self._usb_start_failed = False
        if transport != "bluetooth":
            self._bluetooth_rumble_owned = False
        if transport == "usb":
            self._route_usb(frame)
            return None
        if transport == "bluetooth":
            self._stop_audio()
            self._mode = "bluetooth"
            self._bluetooth_rumble_owned = True
            return to_compatible_rumble(frame)

        self._stop_audio()
        self._mode = None
        return None

    def silence(self) -> CompatibleRumble | None:
        return self.route(SILENT_FRAME)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._bluetooth_rumble_owned = False
        self._stop_audio()
        self._mode = None
