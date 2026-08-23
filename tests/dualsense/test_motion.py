import struct
import zlib

import pytest

from modules.dualsense.motion import (
    DEFAULT_MOTION_CALIBRATION,
    parse_motion_calibration,
    read_motion_calibration,
)


def _calibration_report():
    report = bytearray(41)
    report[0] = 0x05
    values = (
        16,
        -16,
        8,
        1648,
        -1616,
        1616,
        -1648,
        1640,
        -1624,
        102,
        102,
        8202,
        -8182,
        8192,
        -8192,
        8180,
        -8204,
    )
    struct.pack_into("<17h", report, 1, *values)
    crc = zlib.crc32(memoryview(report)[:37], zlib.crc32(b"\xA3"))
    struct.pack_into("<I", report, 37, crc)
    return report


def test_parses_dualsense_hardware_motion_calibration():
    calibration = parse_motion_calibration(_calibration_report())

    assert calibration.hardware is True
    assert calibration.gyro[0].apply(1648) == pytest.approx(102.0)
    assert calibration.gyro[0].apply(16) == pytest.approx(0.0)
    assert calibration.accel[0].apply(8202) == pytest.approx(1.0)


def test_invalid_crc_or_denominator_falls_back_atomically():
    bad_crc = _calibration_report()
    bad_crc[10] ^= 1
    assert parse_motion_calibration(bad_crc) is DEFAULT_MOTION_CALIBRATION

    short_broken = bytearray(_calibration_report()[:35])
    short_broken[7:11] = bytes(4)
    assert parse_motion_calibration(short_broken) is DEFAULT_MOTION_CALIBRATION


def test_feature_report_failure_does_not_break_controller_connection():
    class UnsupportedFeatureDevice:
        def get_feature_report(self, _report_id, _size):
            raise RuntimeError("feature reports unsupported")

    assert (
        read_motion_calibration(UnsupportedFeatureDevice())
        is DEFAULT_MOTION_CALIBRATION
    )
