from __future__ import annotations

import math
from dataclasses import dataclass


def clamp01(value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


@dataclass(frozen=True, slots=True)
class HapticFrame:
    left_low: float = 0.0
    left_high: float = 0.0
    right_low: float = 0.0
    right_high: float = 0.0
    engine_hz: float = 0.0
    engine_amplitude: float = 0.0


@dataclass(frozen=True, slots=True)
class CompatibleRumble:
    low_frequency: float = 0.0
    high_frequency: float = 0.0


SILENT_FRAME = HapticFrame()


def to_compatible_rumble(frame: HapticFrame) -> CompatibleRumble:
    return CompatibleRumble(
        low_frequency=clamp01(max(frame.left_low, frame.right_low) + 0.5 * frame.engine_amplitude),
        high_frequency=clamp01(max(frame.left_high, frame.right_high)),
    )
