"""Pure DualSense USB/Bluetooth input report parsing.

The physical HID handle remains owned by :mod:`modules.dualsense.main`.  This
module only validates and decodes an already-read report; it performs no I/O.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from enum import Enum, IntEnum


USB_INPUT_REPORT_ID = 0x01
USB_INPUT_REPORT_MIN_SIZE = 64
BLUETOOTH_INPUT_REPORT_ID = 0x31
BLUETOOTH_INPUT_REPORT_MIN_SIZE = 78
_BLUETOOTH_CRC_OFFSET = 74
_BLUETOOTH_INPUT_CRC_SEED = zlib.crc32(b"\xA1")


class InputReportError(ValueError):
    """Raised when a physical DualSense input report cannot be trusted."""


class InputTransport(str, Enum):
    USB = "usb"
    BLUETOOTH = "bluetooth"


class BatteryStatus(str, Enum):
    DISCHARGING = "discharging"
    CHARGING = "charging"
    FULL = "full"
    NOT_CHARGING = "not_charging"
    UNKNOWN = "unknown"


class DPad(IntEnum):
    NORTH = 0
    NORTH_EAST = 1
    EAST = 2
    SOUTH_EAST = 3
    SOUTH = 4
    SOUTH_WEST = 5
    WEST = 6
    NORTH_WEST = 7
    NEUTRAL = 8


class DualSenseButton(str, Enum):
    SQUARE = "square"
    CROSS = "cross"
    CIRCLE = "circle"
    TRIANGLE = "triangle"
    L1 = "l1"
    R1 = "r1"
    CREATE = "create"
    OPTIONS = "options"
    L3 = "l3"
    R3 = "r3"
    PS = "ps"


@dataclass(frozen=True, slots=True)
class DualSenseInputState:
    left_x: int
    left_y: int
    right_x: int
    right_y: int
    left_trigger: int
    right_trigger: int
    dpad: DPad
    buttons: frozenset[DualSenseButton]
    battery_level: int | None = None
    battery_status: BatteryStatus = BatteryStatus.UNKNOWN


_FACE_BUTTONS = (
    (0x10, DualSenseButton.SQUARE),
    (0x20, DualSenseButton.CROSS),
    (0x40, DualSenseButton.CIRCLE),
    (0x80, DualSenseButton.TRIANGLE),
)
_SECONDARY_BUTTONS = (
    (0x01, DualSenseButton.L1),
    (0x02, DualSenseButton.R1),
    (0x10, DualSenseButton.CREATE),
    (0x20, DualSenseButton.OPTIONS),
    (0x40, DualSenseButton.L3),
    (0x80, DualSenseButton.R3),
)


def parse_input_report(
    report: bytes | bytearray | memoryview | list[int],
    transport: InputTransport | str,
) -> DualSenseInputState:
    """Validate and decode one full DualSense input report.

    USB and Bluetooth use the same common state layout after different report
    headers.  Full transport sizes are required so a truncated HID read can
    never become a partially valid controller state.
    """
    try:
        selected_transport = InputTransport(transport)
    except ValueError as exc:
        raise InputReportError(f"unsupported DualSense transport: {transport!r}") from exc

    data = bytes(report)
    if selected_transport is InputTransport.USB:
        expected_id = USB_INPUT_REPORT_ID
        expected_size = USB_INPUT_REPORT_MIN_SIZE
        base = 1
    else:
        expected_id = BLUETOOTH_INPUT_REPORT_ID
        expected_size = BLUETOOTH_INPUT_REPORT_MIN_SIZE
        base = 2

    if len(data) < expected_size:
        raise InputReportError(
            f"{selected_transport.value} report is truncated: "
            f"expected {expected_size} bytes, got {len(data)}"
        )
    if len(data) > expected_size:
        raise InputReportError(
            f"unexpected {selected_transport.value} report size: "
            f"expected {expected_size} bytes, got {len(data)}"
        )
    if data[0] != expected_id:
        raise InputReportError(
            f"unexpected {selected_transport.value} report id "
            f"0x{data[0]:02x}; expected 0x{expected_id:02x}"
        )
    if selected_transport is InputTransport.BLUETOOTH:
        expected_crc = struct.unpack_from("<I", data, _BLUETOOTH_CRC_OFFSET)[0]
        actual_crc = zlib.crc32(
            memoryview(data)[:_BLUETOOTH_CRC_OFFSET],
            _BLUETOOTH_INPUT_CRC_SEED,
        )
        if actual_crc != expected_crc:
            raise InputReportError("Bluetooth input report CRC32 does not match")

    buttons0 = data[base + 7]
    buttons1 = data[base + 8]
    buttons2 = data[base + 9]
    try:
        dpad = DPad(buttons0 & 0x0F)
    except ValueError as exc:
        raise InputReportError(f"invalid DualSense d-pad value: {buttons0 & 0x0F}") from exc

    pressed: set[DualSenseButton] = set()
    for mask, button in _FACE_BUTTONS:
        if buttons0 & mask:
            pressed.add(button)
    for mask, button in _SECONDARY_BUTTONS:
        if buttons1 & mask:
            pressed.add(button)
    if buttons2 & 0x01:
        pressed.add(DualSenseButton.PS)

    status0 = data[base + 52]
    raw_level = status0 & 0x0F
    charging = (status0 >> 4) & 0x0F
    if charging == 0x0:
        battery_level = min(raw_level, 10)
        battery_status = BatteryStatus.DISCHARGING
    elif charging == 0x1:
        battery_level = min(raw_level, 10)
        battery_status = BatteryStatus.CHARGING
    elif charging == 0x2:
        battery_level = 10
        battery_status = BatteryStatus.FULL
    elif charging in (0xA, 0xB):
        battery_level = None
        battery_status = BatteryStatus.NOT_CHARGING
    else:
        battery_level = None
        battery_status = BatteryStatus.UNKNOWN

    return DualSenseInputState(
        left_x=data[base],
        left_y=data[base + 1],
        right_x=data[base + 2],
        right_y=data[base + 3],
        left_trigger=data[base + 4],
        right_trigger=data[base + 5],
        dpad=dpad,
        buttons=frozenset(pressed),
        battery_level=battery_level,
        battery_status=battery_status,
    )
