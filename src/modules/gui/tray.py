"""System-tray helper: hide GUI to tray, restore on click, quit from menu.

Uses pystray + Pillow. The tray thread is daemon, lives for the app lifetime.
All Tk interactions are published to the GUI's main-thread callback queue.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from typing import Callable, Optional

import tkinter as tk

from modules.about import APP_NAME
from modules.config import paths

log = logging.getLogger("fhds")

# The standalone ELF contains xorg, not gi/AppIndicator. XEmbed is not reliable
# on Wayland, so this artifact must retain the window there.
TRAY_BACKEND_SUPPORTED = True
if sys.platform == "linux":
    wayland = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland")
    if getattr(sys, "frozen", False):
        TRAY_BACKEND_SUPPORTED = not wayland
        os.environ["PYSTRAY_BACKEND"] = "xorg"
    elif wayland and not os.environ.get("PYSTRAY_BACKEND"):
        os.environ["PYSTRAY_BACKEND"] = "appindicator"


class TrayController:
    def __init__(self, root: tk.Tk, on_show: Callable[[], None], on_quit: Callable[[], None],
                 *, post_ui: Callable[[Callable[[], None]], None]):
        self._root = root
        self._on_show = on_show
        self._on_quit = on_quit
        self._post_ui = post_ui
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._started = False

    def start(self) -> bool:
        """Start the tray icon. Returns True if running, False if unavailable."""
        if not TRAY_BACKEND_SUPPORTED:
            log.warning("System tray unavailable in the standalone Wayland build; keeping the window visible")
            return False
        if self._started:
            return True
        try:
            import pystray
            from PIL import Image
        except Exception as e:
            log.warning("System tray unavailable: %s", e)
            return False
        png = paths.ICON_PNG
        try:
            with Image.open(str(png)) as source:
                image = source.copy()
        except Exception:
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))

        def _show(_icon=None, _item=None):
            self._post_ui(self._on_show)

        def _quit(_icon=None, _item=None):
            # The UI may cancel its unsaved-profile prompt. Keep the icon alive
            # until the confirmed shutdown calls stop().
            self._post_ui(self._on_quit)

        menu = pystray.Menu(
            pystray.MenuItem("Show", _show, default=True),
            pystray.MenuItem("Quit", _quit),
        )
        self._icon = pystray.Icon("fh-dualsense-enhanced", image, APP_NAME, menu)
        self._thread = threading.Thread(target=self._icon.run, name="fhds-tray", daemon=True)
        self._thread.start()
        self._started = True
        log.info("System tray started (backend: %s)", os.environ.get("PYSTRAY_BACKEND", "auto"))
        return True

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
        self._icon = None
        self._started = False
