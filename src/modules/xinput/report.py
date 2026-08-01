"""Pure DualSense-to-XUSB report mapping."""
from __future__ import annotations

import ctypes
from enum import IntFlag

from ..dualsense.input_state import (
    DPad,
    DualSenseButton,
    DualSenseInputState,
    TouchpadRegion,
)
from .mapping import DEFAULT_BUTTON_MAPPING, XInputButtonMapping


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


_BUTTON_SOURCES = {
    DualSenseButton.CROSS: "cross",
    DualSenseButton.CIRCLE: "circle",
    DualSenseButton.SQUARE: "square",
    DualSenseButton.TRIANGLE: "triangle",
    DualSenseButton.L1: "l1",
    DualSenseButton.R1: "r1",
    DualSenseButton.CREATE: "create",
    DualSenseButton.OPTIONS: "options",
    DualSenseButton.L3: "l3",
    DualSenseButton.R3: "r3",
    DualSenseButton.PS: "ps",
}

_DPAD_SOURCES = {
    DPad.NORTH: ("dpad_up",),
    DPad.NORTH_EAST: ("dpad_up", "dpad_right"),
    DPad.EAST: ("dpad_right",),
    DPad.SOUTH_EAST: ("dpad_down", "dpad_right"),
    DPad.SOUTH: ("dpad_down",),
    DPad.SOUTH_WEST: ("dpad_down", "dpad_left"),
    DPad.WEST: ("dpad_left",),
    DPad.NORTH_WEST: ("dpad_up", "dpad_left"),
    DPad.NEUTRAL: (),
}

_TARGET_BUTTONS = {
    "off": XUSBButton(0),
    "a": XUSBButton.A,
    "b": XUSBButton.B,
    "x": XUSBButton.X,
    "y": XUSBButton.Y,
    "left_shoulder": XUSBButton.LEFT_SHOULDER,
    "right_shoulder": XUSBButton.RIGHT_SHOULDER,
    "back": XUSBButton.BACK,
    "start": XUSBButton.START,
    "left_thumb": XUSBButton.LEFT_THUMB,
    "right_thumb": XUSBButton.RIGHT_THUMB,
    "guide": XUSBButton.GUIDE,
    "dpad_up": XUSBButton.DPAD_UP,
    "dpad_down": XUSBButton.DPAD_DOWN,
    "dpad_left": XUSBButton.DPAD_LEFT,
    "dpad_right": XUSBButton.DPAD_RIGHT,
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


def map_dualsense_to_xusb(
    state: DualSenseInputState,
    mapping: XInputButtonMapping = DEFAULT_BUTTON_MAPPING,
) -> XUSBReport:
    buttons = XUSBButton(0)
    for source in _DPAD_SOURCES[state.dpad]:
        buttons |= _TARGET_BUTTONS[mapping.target_for(source)]
    for button in state.buttons:
        if button is DualSenseButton.TOUCHPAD:
            continue
        buttons |= _TARGET_BUTTONS[mapping.target_for(_BUTTON_SOURCES[button])]
    if DualSenseButton.TOUCHPAD in state.buttons:
        regions = state.touchpad_regions or frozenset({TouchpadRegion.LEFT})
        if TouchpadRegion.LEFT in regions:
            buttons |= _TARGET_BUTTONS[mapping.target_for("touchpad_left")]
        if TouchpadRegion.RIGHT in regions:
            buttons |= _TARGET_BUTTONS[mapping.target_for("touchpad_right")]
    return XUSBReport(
        wButtons=int(buttons),
        bLeftTrigger=state.left_trigger,
        bRightTrigger=state.right_trigger,
        sThumbLX=_axis_x(state.left_x),
        sThumbLY=_axis_y(state.left_y),
        sThumbRX=_axis_x(state.right_x),
        sThumbRY=_axis_y(state.right_y),
    )
