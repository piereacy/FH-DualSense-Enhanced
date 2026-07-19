import ctypes

import pytest

from modules.dualsense.input_state import DPad, DualSenseButton, DualSenseInputState
from modules.xinput.report import XUSBButton, XUSBReport, map_dualsense_to_xusb


def _state(**changes):
    values = {
        "left_x": 128,
        "left_y": 128,
        "right_x": 128,
        "right_y": 128,
        "left_trigger": 0,
        "right_trigger": 0,
        "dpad": DPad.NEUTRAL,
        "buttons": frozenset(),
    }
    values.update(changes)
    return DualSenseInputState(**values)


def test_xusb_report_has_official_twelve_byte_layout():
    assert ctypes.sizeof(XUSBReport) == 12
    assert XUSBReport.wButtons.offset == 0
    assert XUSBReport.bLeftTrigger.offset == 2
    assert XUSBReport.bRightTrigger.offset == 3
    assert XUSBReport.sThumbLX.offset == 4
    assert XUSBReport.sThumbRY.offset == 10


def test_neutral_state_maps_to_zero_report():
    report = map_dualsense_to_xusb(_state())

    assert bytes(report) == bytes(12)


@pytest.mark.parametrize(
    ("button", "expected"),
    [
        (DualSenseButton.CROSS, XUSBButton.A),
        (DualSenseButton.CIRCLE, XUSBButton.B),
        (DualSenseButton.SQUARE, XUSBButton.X),
        (DualSenseButton.TRIANGLE, XUSBButton.Y),
        (DualSenseButton.L1, XUSBButton.LEFT_SHOULDER),
        (DualSenseButton.R1, XUSBButton.RIGHT_SHOULDER),
        (DualSenseButton.CREATE, XUSBButton.BACK),
        (DualSenseButton.OPTIONS, XUSBButton.START),
        (DualSenseButton.L3, XUSBButton.LEFT_THUMB),
        (DualSenseButton.R3, XUSBButton.RIGHT_THUMB),
        (DualSenseButton.PS, XUSBButton.GUIDE),
    ],
)
def test_maps_each_digital_button(button, expected):
    report = map_dualsense_to_xusb(_state(buttons=frozenset({button})))

    assert report.wButtons == expected


@pytest.mark.parametrize(
    ("dpad", "expected"),
    [
        (DPad.NORTH, XUSBButton.DPAD_UP),
        (DPad.NORTH_EAST, XUSBButton.DPAD_UP | XUSBButton.DPAD_RIGHT),
        (DPad.EAST, XUSBButton.DPAD_RIGHT),
        (DPad.SOUTH_EAST, XUSBButton.DPAD_DOWN | XUSBButton.DPAD_RIGHT),
        (DPad.SOUTH, XUSBButton.DPAD_DOWN),
        (DPad.SOUTH_WEST, XUSBButton.DPAD_DOWN | XUSBButton.DPAD_LEFT),
        (DPad.WEST, XUSBButton.DPAD_LEFT),
        (DPad.NORTH_WEST, XUSBButton.DPAD_UP | XUSBButton.DPAD_LEFT),
        (DPad.NEUTRAL, XUSBButton(0)),
    ],
)
def test_maps_each_dpad_state(dpad, expected):
    assert map_dualsense_to_xusb(_state(dpad=dpad)).wButtons == expected


def test_maps_triggers_without_curve_or_deadzone():
    report = map_dualsense_to_xusb(_state(left_trigger=1, right_trigger=255))

    assert report.bLeftTrigger == 1
    assert report.bRightTrigger == 255


@pytest.mark.parametrize(
    ("field", "raw", "expected"),
    [
        ("left_x", 0, -32768),
        ("left_x", 128, 0),
        ("left_x", 255, 32767),
        ("right_x", 0, -32768),
        ("right_x", 128, 0),
        ("right_x", 255, 32767),
        ("left_y", 0, 32767),
        ("left_y", 128, 0),
        ("left_y", 255, -32768),
        ("right_y", 0, 32767),
        ("right_y", 128, 0),
        ("right_y", 255, -32768),
    ],
)
def test_maps_stick_centers_and_full_endpoints(field, raw, expected):
    report = map_dualsense_to_xusb(_state(**{field: raw}))

    xusb_field = {
        "left_x": "sThumbLX",
        "left_y": "sThumbLY",
        "right_x": "sThumbRX",
        "right_y": "sThumbRY",
    }[field]
    assert getattr(report, xusb_field) == expected
