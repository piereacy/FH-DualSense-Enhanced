"""FH DualSense building blocks — DualSense HID, UDP listener, settings."""
import logging
import os

from . import dsx, dualsense, forzahorizon as forzahorizon, loop as loop
from .haptics.windows_endpoint import is_dualsense_usb_audio_endpoint_ready
from .runtime_logging import install_runtime_file_handler


def make_backend(s, enable_startup_pulse):
    """Build the trigger writer the settings ask for: DualSense (HID) or DSXClient
    (UDP to DualSenseX). Both share the set/open/close/connected surface, so callers
    treat them interchangeably. Callers pass the pulse flag explicitly (the UIs
    suppress it on a restart)."""
    if s.use_dsx:
        return dsx.DSXClient(
            host=s.dsx_host,
            port=s.dsx_port,
            startup_pulse_force=s.startup_pulse_force,
            enable_startup_pulse=enable_startup_pulse,
        )

    def usb_handover_ready() -> bool:
        if not bool(getattr(s, "enable_body_haptics", False)):
            return True
        return is_dualsense_usb_audio_endpoint_ready()

    return dualsense.DualSense(
        startup_pulse_force=s.startup_pulse_force,
        enable_startup_pulse=enable_startup_pulse,
        reconnect_interval_s=s.reconnect_interval_s,
        enable_reconnect=s.enable_reconnect,
        controller_lock_serial=s.controller_lock_serial,
        usb_handover_ready=usb_handover_ready,
    )


# MARK: Console logging setup (--headless mode only, TUI wires its own handler)
def setup_logging(debug: bool = False) -> None:
    if os.name == "nt":
        os.system("")  # enable ANSI escapes on Windows CMD

    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="\033[92m%(asctime)s %(message)s\033[0m",
        force=True,
    )
    install_runtime_file_handler()
