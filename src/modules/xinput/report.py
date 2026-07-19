"""Pure DualSense-to-XUSB report mapping."""
from __future__ import annotations

import ctypes
from enum import IntFlag

from ..dualsense.input_state import DPad, DualSenseButton, DualSenseInputState


class XUSBButton(IntFlag):
    DPAD_UP = 0x0001
    DPAD_DOWN = 0x0002
    DPAD_LEFT = 0x0004
    DPAD_RIGHT = 0x0008
    START = 0x0010
    BACK = 0x0020
    LEFT_THUMB = 0x0040
    RIGHT_THUMB = 0x0080
    LEFT_SHOULDER = 0x0100
    RIGHT_SHOULDER = 0x0200
    GUIDE = 0x0400
    A = 0x1000
    B = 0x2000
    X = 0x4000
    Y = 0x8000


class XUSBReport(ctypes.LittleEndianStructure):
    """Binary-compatible ViGEm ``XUSB_REPORT`` (12 bytes)."""

    _pack_ = 1
    _fields_ = (
        ("wButtons", ctypes.c_uint16),
        ("bLeftTrigger", ctypes.c_uint8),
        ("bRightTrigger", ctypes.c_uint8),
        ("sThumbLX", ctypes.c_int16),
        ("sThumbLY", ctypes.c_int16),
        ("sThumbRX", ctypes.c_int16),
        ("sThumbRY", ctypes.c_int16),
    )


_BUTTON_MAP = {
    DualSenseButton.CROSS: XUSBButton.A,
    DualSenseButton.CIRCLE: XUSBButton.B,
    DualSenseButton.SQUARE: XUSBButton.X,
    DualSenseButton.TRIANGLE: XUSBButton.Y,
    DualSenseButton.L1: XUSBButton.LEFT_SHOULDER,
    DualSenseButton.R1: XUSBButton.RIGHT_SHOULDER,
    DualSenseButton.CREATE: XUSBButton.BACK,
    DualSenseButton.OPTIONS: XUSBButton.START,
    DualSenseButton.L3: XUSBButton.LEFT_THUMB,
    DualSenseButton.R3: XUSBButton.RIGHT_THUMB,
    DualSenseButton.PS: XUSBButton.GUIDE,
}

_DPAD_MAP = {
    DPad.NORTH: XUSBButton.DPAD_UP,
    DPad.NORTH_EAST: XUSBButton.DPAD_UP | XUSBButton.DPAD_RIGHT,
    DPad.EAST: XUSBButton.DPAD_RIGHT,
    DPad.SOUTH_EAST: XUSBButton.DPAD_DOWN | XUSBButton.DPAD_RIGHT,
    DPad.SOUTH: XUSBButton.DPAD_DOWN,
    DPad.SOUTH_WEST: XUSBButton.DPAD_DOWN | XUSBButton.DPAD_LEFT,
    DPad.WEST: XUSBButton.DPAD_LEFT,
    DPad.NORTH_WEST: XUSBButton.DPAD_UP | XUSBButton.DPAD_LEFT,
    DPad.NEUTRAL: XUSBButton(0),
}


def _axis_x(raw: int) -> int:
    """Map 0..255 to full signed XInput range with raw 128 exactly neutral."""
    if raw <= 128:
        return round((raw - 128) * 32768 / 128)
    return round((raw - 128) * 32767 / 127)


def _axis_y(raw: int) -> int:
    """Map top to positive and bottom to negative, preserving center/endpoints."""
    if raw <= 128:
        return round((128 - raw) * 32767 / 128)
    return round((128 - raw) * 32768 / 127)


def map_dualsense_to_xusb(state: DualSenseInputState) -> XUSBReport:
    buttons = _DPAD_MAP[state.dpad]
    for button in state.buttons:
        buttons |= _BUTTON_MAP[button]
    return XUSBReport(
        wButtons=int(buttons),
        bLeftTrigger=state.left_trigger,
        bRightTrigger=state.right_trigger,
        sThumbLX=_axis_x(state.left_x),
        sThumbLY=_axis_y(state.left_y),
        sThumbRX=_axis_x(state.right_x),
        sThumbRY=_axis_y(state.right_y),
    )
