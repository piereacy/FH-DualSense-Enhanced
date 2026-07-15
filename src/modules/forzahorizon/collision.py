from __future__ import annotations

import math
from dataclasses import dataclass


def _number(value) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) else 0.0


def _clamp01(value) -> float:
    return max(0.0, min(1.0, _number(value)))


@dataclass(frozen=True, slots=True)
class CollisionSignal:
    intensity: float
    direction: str
    source: str
    jerk: float
    smashable: float


class CollisionDetector:
    """One event detector shared by trigger and grip renderers in the main loop."""

    def __init__(self):
        self.reset()

    def reset(self):
        self._prev_accel: tuple[float, float] | None = None
        self._armed = True
        self._cooldown_until = 0.0

    def update(self, telemetry, settings, now: float) -> CollisionSignal | None:
        if not telemetry.get("on", False):
            self.reset()
            return None
        accel_x = _number(telemetry.get("accel_x"))
        accel_z = _number(telemetry.get("accel_z"))
        jerk = 0.0
        if self._prev_accel is not None:
            jerk = math.hypot(
                accel_x - self._prev_accel[0],
                accel_z - self._prev_accel[1],
            )
        self._prev_accel = (accel_x, accel_z)

        threshold = max(
            0.0, _number(getattr(settings, "collision_haptics_jerk_threshold", 3.0))
        )
        jerk_active = jerk > threshold
        jerk_intensity = _clamp01((jerk - threshold) / 27.0) if jerk_active else 0.0
        smashable = max(0.0, _number(telemetry.get("smashable_vel_diff")))
        smash_active = smashable > 3.0
        smash_intensity = _clamp01(smashable / 15.0) if smash_active else 0.0

        if not jerk_active and not smash_active and now >= self._cooldown_until:
            self._armed = True
        intensity = max(jerk_intensity, smash_intensity)
        if not self._armed or intensity <= 0.0:
            return None

        self._armed = False
        self._cooldown_until = now + max(
            0.0,
            _number(getattr(settings, "collision_haptics_cooldown_ms", 250.0)) / 1000.0,
        )
        if accel_x > 5.0:
            direction = "left"
        elif accel_x < -5.0:
            direction = "right"
        else:
            direction = "center"
        source = "both" if jerk_active and smash_active else (
            "jerk" if jerk_active else "smashable"
        )
        return CollisionSignal(
            intensity=intensity,
            direction=direction,
            source=source,
            jerk=jerk,
            smashable=smashable,
        )
