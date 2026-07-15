import struct
import zlib

import numpy as np
import pytest

from modules.dualsense.adaptive_trigger import rigid, vibrate
from modules.dualsense.bt_haptics import (
    BT_HAPTICS_REPORT_ID,
    BT_HAPTICS_REPORT_SIZE,
    BluetoothHapticsPacketBuilder,
    quantize_haptics,
)


def test_quantize_haptics_interleaves_signed_left_and_right_samples():
    pcm = np.zeros((32, 2), dtype=np.float32)
    pcm[:3] = ((-1.0, 1.0), (-0.5, 0.5), (0.0, 0.0))

    payload = quantize_haptics(pcm, numpy_module=np)

    assert payload[:6] == bytes((128, 127, 192, 64, 0, 0))


def test_quantize_haptics_requires_32_stereo_frames():
    with pytest.raises(ValueError, match="32 stereo frames"):
        quantize_haptics(np.zeros((31, 2), dtype=np.float32), numpy_module=np)


def test_bt_haptics_report_has_expected_blocks_trigger_state_and_crc():
    builder = BluetoothHapticsPacketBuilder()
    samples = bytes(range(64))
    left = rigid(31)
    right = vibrate(22, 9)

    report = builder.build(samples, left=left, right=right)

    assert len(report) == BT_HAPTICS_REPORT_SIZE
    assert report[0] == BT_HAPTICS_REPORT_ID
    assert report[1] == 0
    assert report[2:5] == bytes((0x91, 7, 0xFE))
    assert report[5:10] == bytes((64, 64, 64, 64, 64))
    assert report[10] == 0
    assert report[11:13] == bytes((0x90, 63))
    assert report[13] == 0x0C
    assert report[23] == right[0]
    assert report[24:26] == bytes(right[1][:2])
    assert report[34] == left[0]
    assert report[35:36] == bytes(left[1][:1])
    assert report[76:78] == bytes((0x92, 64))
    assert report[78:142] == samples
    assert report[142:394] == bytes(252)

    seed = zlib.crc32(b"\xA2")
    expected_crc = zlib.crc32(report[:394], seed)
    assert struct.unpack_from("<I", report, 394)[0] == expected_crc


def test_bt_haptics_report_sequences_wrap_independently():
    builder = BluetoothHapticsPacketBuilder()
    samples = bytes(64)

    reports = [builder.build(samples, left=(0, ()), right=(0, ())) for _ in range(257)]

    assert reports[0][1] == 0x00
    assert reports[1][1] == 0x10
    assert reports[15][1] == 0xF0
    assert reports[16][1] == 0x00
    assert reports[255][10] == 255
    assert reports[256][10] == 0


def test_bt_haptics_report_rejects_wrong_sample_size():
    builder = BluetoothHapticsPacketBuilder()

    with pytest.raises(ValueError, match="64 bytes"):
        builder.build(bytes(63), left=(0, ()), right=(0, ()))
