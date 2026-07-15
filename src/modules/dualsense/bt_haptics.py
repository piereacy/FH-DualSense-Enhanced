from __future__ import annotations

import struct
import zlib

# Bluetooth audio-haptics framing is based on hurryman2212/vds 0.3.0-rc7
# and cross-checked against awalol/DS5Dongle. Both repository LICENSE files
# identify the referenced revisions as MIT; see docs/THIRD_PARTY_NOTICES.md.
BT_HAPTICS_REPORT_ID = 0x36
BT_HAPTICS_REPORT_SIZE = 398
BT_HAPTICS_SAMPLE_BYTES = 64
BT_HAPTICS_FRAMES = 32
BT_HAPTICS_SAMPLE_RATE = 3000

_BT_OUTPUT_CRC_SEED = zlib.crc32(b"\xA2")
_STATE_SIZE = 63
_STATE_OFFSET = 13
_STATE_FLAG0 = 0
_RIGHT_TRIGGER_OFFSET = 10
_LEFT_TRIGGER_OFFSET = 21
_TRIGGER_FLAGS = 0x04 | 0x08


def quantize_haptics(pcm, *, numpy_module) -> bytes:
    """Convert exactly 32 stereo float PCM frames into interleaved int8 bytes."""
    if getattr(pcm, "shape", None) != (BT_HAPTICS_FRAMES, 2):
        raise ValueError("Bluetooth haptics requires exactly 32 stereo frames")
    quantized = numpy_module.clip(
        numpy_module.rint(pcm * 128.0),
        -128,
        127,
    ).astype(numpy_module.int8)
    return quantized.tobytes(order="C")


def _state_with_triggers(left, right) -> bytearray:
    state = bytearray(_STATE_SIZE)
    state[_STATE_FLAG0] = _TRIGGER_FLAGS
    for offset, trigger in (
        (_RIGHT_TRIGGER_OFFSET, right),
        (_LEFT_TRIGGER_OFFSET, left),
    ):
        mode, params = trigger
        state[offset] = int(mode) & 0xFF
        values = bytes(int(value) & 0xFF for value in tuple(params)[:10])
        state[offset + 1:offset + 1 + len(values)] = values
    return state


class BluetoothHapticsPacketBuilder:
    """Build physical DualSense Bluetooth report 0x36 packets."""

    def __init__(self):
        self._report_sequence = 0
        self._packet_sequence = 0

    def reset(self) -> None:
        self._report_sequence = 0
        self._packet_sequence = 0

    def build(self, samples: bytes, *, left, right) -> bytearray:
        samples = bytes(samples)
        if len(samples) != BT_HAPTICS_SAMPLE_BYTES:
            raise ValueError("Bluetooth haptics payload must be exactly 64 bytes")

        packet = bytearray(BT_HAPTICS_REPORT_SIZE)
        packet[0] = BT_HAPTICS_REPORT_ID
        packet[1] = self._report_sequence << 4
        self._report_sequence = (self._report_sequence + 1) & 0x0F
        packet[2] = 0x91
        packet[3] = 7
        packet[4] = 0xFE
        packet[5:10] = bytes((64, 64, 64, 64, 64))
        packet[10] = self._packet_sequence
        self._packet_sequence = (self._packet_sequence + 1) & 0xFF

        packet[11] = 0x90
        packet[12] = _STATE_SIZE
        packet[_STATE_OFFSET:_STATE_OFFSET + _STATE_SIZE] = _state_with_triggers(left, right)

        packet[76] = 0x92
        packet[77] = BT_HAPTICS_SAMPLE_BYTES
        packet[78:142] = samples
        # No controller-speaker block is advertised. Bytes 142..393 remain zero.

        crc = zlib.crc32(memoryview(packet)[:394], _BT_OUTPUT_CRC_SEED)
        struct.pack_into("<I", packet, 394, crc)
        return packet
