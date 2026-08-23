"""DualSense motion-sensor calibration loaded from feature report 0x05."""
from __future__ import annotations

import math
import struct
import zlib
from dataclasses import dataclass


CALIBRATION_REPORT_ID = 0x05
CALIBRATION_REPORT_SIZE = 41
GYRO_RES_PER_DEGREE_S = 1024.0
GYRO_RAW_RES_PER_DEGREE_S = 16.0
ACCEL_RES_PER_G = 8192.0
_FEATURE_CRC_OFFSET = 37
_FEATURE_CRC_SEED = zlib.crc32(b"\xA3")


@dataclass(frozen=True, slots=True)
class MotionAxisCalibration:
    bias: float
    scale: float

    def apply(self, raw: int) -> float:
        return (float(raw) - self.bias) * self.scale


@dataclass(frozen=True, slots=True)
class DualSenseMotionCalibration:
    gyro: tuple[MotionAxisCalibration, MotionAxisCalibration, MotionAxisCalibration]
    accel: tuple[MotionAxisCalibration, MotionAxisCalibration, MotionAxisCalibration]
    hardware: bool = False


DEFAULT_MOTION_CALIBRATION = DualSenseMotionCalibration(
    gyro=(
        MotionAxisCalibration(0.0, 1.0 / GYRO_RAW_RES_PER_DEGREE_S),
        MotionAxisCalibration(0.0, 1.0 / GYRO_RAW_RES_PER_DEGREE_S),
        MotionAxisCalibration(0.0, 1.0 / GYRO_RAW_RES_PER_DEGREE_S),
    ),
    accel=(
        MotionAxisCalibration(0.0, 1.0 / ACCEL_RES_PER_G),
        MotionAxisCalibration(0.0, 1.0 / ACCEL_RES_PER_G),
        MotionAxisCalibration(0.0, 1.0 / ACCEL_RES_PER_G),
    ),
)


def parse_motion_calibration(report) -> DualSenseMotionCalibration:
    """Validate Sony feature report 0x05 and return degrees/s plus g scaling.

    Invalid clone/broken calibration falls back atomically to the documented
    DualSense nominal resolutions instead of partially poisoning one axis.
    """
    data = bytes(report)
    if len(data) < 35 or data[0] != CALIBRATION_REPORT_ID:
        return DEFAULT_MOTION_CALIBRATION
    if len(data) >= CALIBRATION_REPORT_SIZE:
        expected_crc = struct.unpack_from("<I", data, _FEATURE_CRC_OFFSET)[0]
        actual_crc = zlib.crc32(
            memoryview(data)[:_FEATURE_CRC_OFFSET],
            _FEATURE_CRC_SEED,
        )
        if expected_crc != actual_crc:
            return DEFAULT_MOTION_CALIBRATION
    values = struct.unpack_from("<17h", data, 1)
    gyro_bias = values[0:3]
    gyro_pairs = ((values[3], values[4]), (values[5], values[6]), (values[7], values[8]))
    speed_2x = values[9] + values[10]

    gyro: list[MotionAxisCalibration] = []
    for bias, (plus, minus) in zip(gyro_bias, gyro_pairs, strict=True):
        denominator = plus - minus
        if denominator == 0:
            return DEFAULT_MOTION_CALIBRATION
        scale = speed_2x / denominator
        nominal = 1.0 / GYRO_RAW_RES_PER_DEGREE_S
        if abs(bias) > 1024 or not 0.5 * nominal <= abs(scale) <= 1.5 * nominal:
            return DEFAULT_MOTION_CALIBRATION
        gyro.append(MotionAxisCalibration(float(bias), float(scale)))

    accel: list[MotionAxisCalibration] = []
    for plus, minus in ((values[11], values[12]), (values[13], values[14]), (values[15], values[16])):
        range_2g = plus - minus
        if range_2g == 0:
            return DEFAULT_MOTION_CALIBRATION
        bias = plus - range_2g / 2.0
        scale = 2.0 / range_2g
        if abs(bias) > 1024 or not 0.5 / ACCEL_RES_PER_G <= abs(scale) <= 1.5 / ACCEL_RES_PER_G:
            return DEFAULT_MOTION_CALIBRATION
        accel.append(MotionAxisCalibration(bias, scale))

    if not all(
        math.isfinite(value)
        for item in (*gyro, *accel)
        for value in (item.bias, item.scale)
    ):
        return DEFAULT_MOTION_CALIBRATION
    return DualSenseMotionCalibration(tuple(gyro), tuple(accel), hardware=True)


def read_motion_calibration(device) -> DualSenseMotionCalibration:
    try:
        report = device.get_feature_report(
            CALIBRATION_REPORT_ID,
            CALIBRATION_REPORT_SIZE,
        )
    except Exception:
        # Motion is optional for the X360 bridge. An unusual HID backend or
        # clone must not make an otherwise usable controller fail to connect.
        return DEFAULT_MOTION_CALIBRATION
    return parse_motion_calibration(report)
