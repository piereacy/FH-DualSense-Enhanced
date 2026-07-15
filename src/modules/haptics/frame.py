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
    compatible_low_frequency: float | None = None
    compatible_high_frequency: float | None = None


@dataclass(frozen=True, slots=True)
class CompatibleRumble:
    low_frequency: float = 0.0
    high_frequency: float = 0.0


SILENT_FRAME = HapticFrame()


def to_compatible_rumble(frame: HapticFrame) -> CompatibleRumble:
    fallback_low = max(frame.left_low, frame.right_low) + 0.5 * frame.engine_amplitude
    fallback_high = max(frame.left_high, frame.right_high)
    return CompatibleRumble(
        low_frequency=clamp01(
            fallback_low
            if frame.compatible_low_frequency is None
            else frame.compatible_low_frequency
        ),
        high_frequency=clamp01(
            fallback_high
            if frame.compatible_high_frequency is None
            else frame.compatible_high_frequency
        ),
    )
