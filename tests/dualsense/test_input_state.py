import struct
import zlib

import pytest

from modules.dualsense.input_state import (
    BLUETOOTH_INPUT_REPORT_MIN_SIZE,
    USB_INPUT_REPORT_MIN_SIZE,
    BatteryStatus,
    DPad,
    DualSenseButton,
    InputReportError,
    InputTransport,
    parse_input_report,
)


def _report(transport, *, dpad=DPad.NEUTRAL, buttons0=0, buttons1=0, buttons2=0):
    bluetooth = transport is InputTransport.BLUETOOTH
    report = bytearray(
        BLUETOOTH_INPUT_REPORT_MIN_SIZE if bluetooth else USB_INPUT_REPORT_MIN_SIZE
    )
    report[0] = 0x31 if bluetooth else 0x01
    base = 2 if bluetooth else 1
    report[base:base + 6] = bytes((1, 2, 3, 4, 5, 6))
    report[base + 7] = int(dpad) | buttons0
    report[base + 8] = buttons1
    report[base + 9] = buttons2
    if bluetooth:
        crc = zlib.crc32(memoryview(report)[:74], zlib.crc32(b"\xA1"))
        struct.pack_into("<I", report, 74, crc)
    return report


@pytest.mark.parametrize("transport", list(InputTransport))
def test_parses_common_axes_triggers_and_transport_layout(transport):
    state = parse_input_report(_report(transport), transport)

    assert (state.left_x, state.left_y) == (1, 2)
    assert (state.right_x, state.right_y) == (3, 4)
    assert (state.left_trigger, state.right_trigger) == (5, 6)
    assert state.dpad is DPad.NEUTRAL
    assert state.buttons == frozenset()


@pytest.mark.parametrize("transport", list(InputTransport))
@pytest.mark.parametrize("dpad", list(DPad))
def test_parses_all_dpad_states(transport, dpad):
    assert parse_input_report(_report(transport, dpad=dpad), transport).dpad is dpad


@pytest.mark.parametrize("transport", list(InputTransport))
def test_parses_all_supported_digital_buttons(transport):
    state = parse_input_report(
        _report(
            transport,
            buttons0=0xF0,
            buttons1=0xF3,
            buttons2=0x07,
        ),
        transport,
    )

    assert state.buttons == frozenset(DualSenseButton)


@pytest.mark.parametrize("transport", list(InputTransport))
def test_ignores_digital_trigger_and_unsupported_mute_bits(transport):
    state = parse_input_report(
        _report(transport, buttons1=0x0C, buttons2=0x04),
        transport,
    )

    assert state.buttons == frozenset()


@pytest.mark.parametrize("transport", list(InputTransport))
def test_rejects_wrong_report_id(transport):
    report = _report(transport)
    report[0] ^= 0xFF
    if transport is InputTransport.BLUETOOTH:
        crc = zlib.crc32(memoryview(report)[:74], zlib.crc32(b"\xA1"))
        struct.pack_into("<I", report, 74, crc)

    with pytest.raises(InputReportError, match="report id"):
        parse_input_report(report, transport)


@pytest.mark.parametrize("transport", list(InputTransport))
def test_rejects_truncated_report(transport):
    report = _report(transport)

    with pytest.raises(InputReportError, match="truncated"):
        parse_input_report(report[:-1], transport)


@pytest.mark.parametrize("transport", list(InputTransport))
def test_rejects_invalid_dpad_value(transport):
    report = _report(transport)
    base = 2 if transport is InputTransport.BLUETOOTH else 1
    report[base + 7] = 0x09
    if transport is InputTransport.BLUETOOTH:
        crc = zlib.crc32(memoryview(report)[:74], zlib.crc32(b"\xA1"))
        struct.pack_into("<I", report, 74, crc)

    with pytest.raises(InputReportError, match="d-pad"):
        parse_input_report(report, transport)


def test_rejects_unknown_transport():
    with pytest.raises(InputReportError, match="transport"):
        parse_input_report(bytes(64), "serial")


@pytest.mark.parametrize(
    ("charging", "level", "expected_level", "expected_status"),
    [
        (0x0, 0, 0, BatteryStatus.DISCHARGING),
        (0x0, 7, 7, BatteryStatus.DISCHARGING),
        (0x1, 4, 4, BatteryStatus.CHARGING),
        (0x2, 0, 10, BatteryStatus.FULL),
        (0xA, 5, None, BatteryStatus.NOT_CHARGING),
        (0xF, 5, None, BatteryStatus.UNKNOWN),
    ],
)
@pytest.mark.parametrize("transport", list(InputTransport))
def test_parses_battery_bucket_and_charging_state(
    transport, charging, level, expected_level, expected_status
):
    report = _report(transport)
    base = 2 if transport is InputTransport.BLUETOOTH else 1
    report[base + 52] = (charging << 4) | level
    if transport is InputTransport.BLUETOOTH:
        crc = zlib.crc32(memoryview(report)[:74], zlib.crc32(b"\xA1"))
        struct.pack_into("<I", report, 74, crc)

    state = parse_input_report(report, transport)

    assert state.battery_level == expected_level
    assert state.battery_status is expected_status


def test_rejects_bluetooth_report_with_bad_crc():
    report = _report(InputTransport.BLUETOOTH)
    report[10] ^= 0x80

    with pytest.raises(InputReportError, match="CRC32"):
        parse_input_report(report, InputTransport.BLUETOOTH)


@pytest.mark.parametrize("transport", list(InputTransport))
def test_rejects_oversized_report(transport):
    report = _report(transport) + b"\x00"

    with pytest.raises(InputReportError, match="report size"):
        parse_input_report(report, transport)
