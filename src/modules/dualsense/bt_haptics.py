from __future__ import annotations

import struct
import zlib

from .output_state import ControllerVisualState, NO_VISUAL_CONTROL

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
_STATE_VALID_FLAG1 = 1
_STATE_VALID_FLAG2 = 38
_STATE_LIGHTBAR_SETUP = 41
_STATE_PLAYER_LEDS = 43
_STATE_LIGHTBAR_R = 44
_STATE_LIGHTBAR_G = 45
_STATE_LIGHTBAR_B = 46


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


class BluetoothPcmQuantizer:
    """Stateful int8 quantizer with first-order error feedback.

    Low-amplitude road detail often falls between int8 steps. Feeding part of
    the previous rounding error into the next sample preserves its average
    energy without changing packet size or sample rate.
    """

    def __init__(self, *, numpy_module, feedback: float = 0.75):
        self._np = numpy_module
        self.feedback = max(0.0, min(0.95, float(feedback)))
        self._error = self._np.zeros(2, dtype=self._np.float64)

    def reset(self):
        self._error[:] = 0.0

    def quantize(self, pcm) -> bytes:
        if getattr(pcm, "shape", None) != (BT_HAPTICS_FRAMES, 2):
            raise ValueError("Bluetooth haptics requires exactly 32 stereo frames")
        output = self._np.empty((BT_HAPTICS_FRAMES, 2), dtype=self._np.int8)
        for index in range(BT_HAPTICS_FRAMES):
            scaled = self._np.clip(pcm[index] * 128.0 + self._error, -128.0, 127.0)
            rounded = self._np.rint(scaled)
            output[index] = rounded.astype(self._np.int8)
            self._error = (scaled - rounded) * self.feedback
        return output.tobytes(order="C")


def _state_with_triggers(left, right, visual=None) -> bytearray:
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
    visual = (visual or NO_VISUAL_CONTROL).normalized()
    if visual.lightbar is not None:
        state[_STATE_VALID_FLAG1] |= 0x04
        state[_STATE_VALID_FLAG2] |= 0x02
        state[_STATE_LIGHTBAR_SETUP] = 0x02
        state[_STATE_LIGHTBAR_R] = visual.lightbar[0]
        state[_STATE_LIGHTBAR_G] = visual.lightbar[1]
        state[_STATE_LIGHTBAR_B] = visual.lightbar[2]
    if visual.player_leds is not None:
        state[_STATE_VALID_FLAG1] |= 0x10
        state[_STATE_PLAYER_LEDS] = visual.player_leds | 0x20
    return state


class BluetoothHapticsPacketBuilder:
    """Build physical DualSense Bluetooth report 0x36 packets."""

    def __init__(self):
        self._report_sequence = 0
        self._packet_sequence = 0

    def reset(self) -> None:
        self._report_sequence = 0
        self._packet_sequence = 0

    def build(
        self,
        samples: bytes,
        *,
        left,
        right,
        visual: ControllerVisualState | None = None,
    ) -> bytearray:
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
        packet[_STATE_OFFSET:_STATE_OFFSET + _STATE_SIZE] = _state_with_triggers(
            left, right, visual
        )

        packet[76] = 0x92
        packet[77] = BT_HAPTICS_SAMPLE_BYTES
        packet[78:142] = samples
        # No controller-speaker block is advertised. Bytes 142..393 remain zero.

        crc = zlib.crc32(memoryview(packet)[:394], _BT_OUTPUT_CRC_SEED)
        struct.pack_into("<I", packet, 394, crc)
        return packet
