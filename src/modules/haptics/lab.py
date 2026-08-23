"""Bounded, game-independent feedback previews for the Haptics Lab.

The lab publishes immutable requests only. The existing telemetry loop remains
the sole owner of controller and body-haptics output, so a preview cannot start
XInput, Raw Input, HidHide, or a second HID reader.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass

from modules.dualsense.adaptive_trigger import (
    feedback_slope,
    off,
    vibrate,
    vibrate_zones,
)

from .frame import HapticFrame, SILENT_FRAME, clamp01

LAB_MIN_INTENSITY = 0.10
LAB_MAX_INTENSITY = 0.65
LAB_MIN_DURATION_S = 0.25
LAB_MAX_DURATION_S = 3.0
LAB_DEFAULT_INTENSITY = 0.35
LAB_DEFAULT_DURATION_S = 1.5


@dataclass(frozen=True, slots=True)
class HapticsLabScene:
    key: str
    label: str
    description: str
    body_haptics: bool = True
    adaptive_triggers: bool = False


HAPTICS_LAB_SCENES = (
    HapticsLabScene(
        "engine",
        "Engine sweep",
        "A low engine tone that rises through a short RPM sweep.",
    ),
    HapticsLabScene(
        "road",
        "Road texture",
        "A steady fine texture on both grips.",
    ),
    HapticsLabScene(
        "water",
        "Water and puddles",
        "A softer uneven texture for wet surfaces and puddles.",
    ),
    HapticsLabScene(
        "tire_slip",
        "Tire slip",
        "A fast high-frequency warning on both grips.",
    ),
    HapticsLabScene(
        "suspension",
        "Suspension travel",
        "A rounded low-frequency suspension movement.",
    ),
    HapticsLabScene(
        "collision_left",
        "Collision - left",
        "A decaying impact isolated to the left grip.",
    ),
    HapticsLabScene(
        "collision_right",
        "Collision - right",
        "A decaying impact isolated to the right grip.",
    ),
    HapticsLabScene(
        "upshift",
        "Upshift",
        "A short, firm shift thump on both grips.",
    ),
    HapticsLabScene(
        "downshift",
        "Downshift",
        "A heavier double-stage shift thump on both grips.",
    ),
    HapticsLabScene(
        "redline",
        "Redline pulse",
        "A rhythmic warning pulse on the left grip.",
    ),
    HapticsLabScene(
        "abs",
        "ABS preview",
        "A brake-trigger buzz with matching grip feedback.",
        adaptive_triggers=True,
    ),
    HapticsLabScene(
        "traction",
        "Traction control preview",
        "A throttle-trigger buzz with right-grip slip feedback.",
        adaptive_triggers=True,
    ),
    HapticsLabScene(
        "brake_resistance",
        "Brake resistance",
        "A bounded progressive resistance curve on L2.",
        body_haptics=False,
        adaptive_triggers=True,
    ),
    HapticsLabScene(
        "throttle_resistance",
        "Throttle resistance",
        "A bounded progressive resistance curve on R2.",
        body_haptics=False,
        adaptive_triggers=True,
    ),
)

HAPTICS_LAB_SCENE_BY_KEY = {scene.key: scene for scene in HAPTICS_LAB_SCENES}


def scene_supported_by_backend(scene: HapticsLabScene, *, is_dsx: bool) -> bool:
    """Return whether a scene has at least one output supported by the backend."""
    return not is_dsx or scene.adaptive_triggers


@dataclass(frozen=True, slots=True)
class HapticsLabOutput:
    frame: HapticFrame = SILENT_FRAME
    left_trigger: tuple = (0x05, ())
    right_trigger: tuple = (0x05, ())


@dataclass(frozen=True, slots=True)
class HapticsLabSnapshot:
    active: bool = False
    scene: str = ""
    intensity: float = LAB_DEFAULT_INTENSITY
    duration_s: float = LAB_DEFAULT_DURATION_S
    remaining_s: float = 0.0
    revision: int = 0
    stop_reason: str = ""


def _bounded_intensity(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return LAB_DEFAULT_INTENSITY
    if not math.isfinite(number):
        return LAB_DEFAULT_INTENSITY
    return max(LAB_MIN_INTENSITY, min(LAB_MAX_INTENSITY, number))


def _bounded_duration(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return LAB_DEFAULT_DURATION_S
    if not math.isfinite(number):
        return LAB_DEFAULT_DURATION_S
    return max(LAB_MIN_DURATION_S, min(LAB_MAX_DURATION_S, number))


def _pulse(elapsed_s: float, frequency_hz: float, duty: float = 0.5) -> float:
    phase = (max(0.0, elapsed_s) * max(0.1, frequency_hz)) % 1.0
    return 1.0 if phase < max(0.05, min(0.95, duty)) else 0.0


def _frame(**values: float | None) -> HapticFrame:
    normalized = {}
    for name, value in values.items():
        if value is None:
            normalized[name] = None
        elif name == "engine_hz":
            frequency = float(value)
            normalized[name] = frequency if math.isfinite(frequency) and frequency > 0.0 else 0.0
        else:
            normalized[name] = clamp01(value)
    return HapticFrame(**normalized)


def render_haptics_lab_scene(
    scene_key: str,
    *,
    elapsed_s: float,
    duration_s: float,
    intensity: float,
) -> HapticsLabOutput:
    """Render one bounded preview sample without touching hardware."""
    if scene_key not in HAPTICS_LAB_SCENE_BY_KEY:
        raise ValueError(f"Unknown Haptics Lab scene: {scene_key}")
    strength = _bounded_intensity(intensity)
    duration = _bounded_duration(duration_s)
    elapsed = max(0.0, min(duration, float(elapsed_s)))
    progress = elapsed / duration if duration else 1.0
    left = off()
    right = off()
    frame = SILENT_FRAME

    if scene_key == "engine":
        frame = _frame(
            engine_hz=45.0 + 70.0 * progress,
            engine_amplitude=0.78 * strength,
            compatible_low_frequency=0.55 * strength,
            compatible_high_frequency=0.10 * strength,
        )
    elif scene_key == "road":
        frame = _frame(
            left_low=0.18 * strength,
            left_high=0.72 * strength,
            right_low=0.18 * strength,
            right_high=0.72 * strength,
        )
    elif scene_key == "water":
        wave = 0.55 + 0.45 * math.sin(elapsed * math.tau * 3.0) ** 2
        frame = _frame(
            left_low=0.30 * strength * wave,
            left_high=0.42 * strength * wave,
            right_low=0.24 * strength * (1.1 - 0.3 * wave),
            right_high=0.38 * strength * (1.1 - 0.3 * wave),
        )
    elif scene_key == "tire_slip":
        frame = _frame(
            left_high=0.90 * strength,
            right_high=0.90 * strength,
            compatible_high_frequency=0.90 * strength,
        )
    elif scene_key == "suspension":
        envelope = 0.35 + 0.65 * math.sin(elapsed * math.tau * 4.0) ** 2
        frame = _frame(
            left_low=0.82 * strength * envelope,
            right_low=0.82 * strength * envelope,
        )
    elif scene_key in {"collision_left", "collision_right"}:
        envelope = math.exp(-5.0 * progress)
        values = {
            "left_low": 0.0,
            "left_high": 0.0,
            "right_low": 0.0,
            "right_high": 0.0,
        }
        side = "left" if scene_key.endswith("left") else "right"
        values[f"{side}_low"] = strength * envelope
        values[f"{side}_high"] = 0.55 * strength * envelope
        frame = _frame(**values)
    elif scene_key == "upshift":
        envelope = math.exp(-9.0 * progress)
        frame = _frame(
            left_low=0.92 * strength * envelope,
            right_low=0.92 * strength * envelope,
        )
    elif scene_key == "downshift":
        stage = max(
            math.exp(-12.0 * progress),
            0.62 * math.exp(-18.0 * abs(progress - 0.35)),
        )
        frame = _frame(
            left_low=strength * stage,
            right_low=strength * stage,
            left_high=0.25 * strength * stage,
            right_high=0.25 * strength * stage,
        )
    elif scene_key == "redline":
        beat = _pulse(elapsed, 10.0, 0.68)
        frame = _frame(
            left_low=0.72 * strength * beat,
            left_high=0.35 * strength * beat,
            compatible_low_frequency=0.72 * strength * beat,
        )
    elif scene_key == "abs":
        frame = _frame(
            left_high=0.62 * strength,
            right_high=0.28 * strength,
        )
        left = vibrate_zones(
            max(1, round(8 * strength)),
            25,
            2,
        )
    elif scene_key == "traction":
        frame = _frame(
            right_high=0.78 * strength,
            compatible_high_frequency=0.65 * strength,
        )
        right = vibrate(32, round(255 * strength))
    elif scene_key == "brake_resistance":
        left = feedback_slope(2, 8, 1, max(2, round(8 * strength)))
    elif scene_key == "throttle_resistance":
        right = feedback_slope(1, 9, 1, max(2, round(8 * strength)))

    return HapticsLabOutput(frame=frame, left_trigger=left, right_trigger=right)


class HapticsLab:
    """Thread-safe preview request state consumed by the telemetry loop."""

    def __init__(self, *, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._scene = ""
        self._intensity = LAB_DEFAULT_INTENSITY
        self._duration_s = LAB_DEFAULT_DURATION_S
        self._started_at: float | None = None
        self._revision = 0
        self._stop_reason = ""

    def start(
        self,
        scene: str,
        *,
        intensity: float = LAB_DEFAULT_INTENSITY,
        duration_s: float = LAB_DEFAULT_DURATION_S,
        now: float | None = None,
    ) -> HapticsLabSnapshot:
        if scene not in HAPTICS_LAB_SCENE_BY_KEY:
            raise ValueError(f"Unknown Haptics Lab scene: {scene}")
        timestamp = self._clock() if now is None else float(now)
        with self._lock:
            self._scene = scene
            self._intensity = _bounded_intensity(intensity)
            self._duration_s = _bounded_duration(duration_s)
            self._started_at = timestamp
            self._revision += 1
            self._stop_reason = ""
            return self._snapshot_locked(timestamp)

    def stop(self, reason: str = "user", *, now: float | None = None) -> HapticsLabSnapshot:
        timestamp = self._clock() if now is None else float(now)
        with self._lock:
            if self._started_at is None:
                if not self._stop_reason:
                    self._stop_reason = str(reason)
                    self._revision += 1
                return self._snapshot_locked(timestamp)
            self._revision += 1
            self._started_at = None
            self._scene = ""
            self._stop_reason = str(reason)
            return self._snapshot_locked(timestamp)

    def preempt_for_telemetry(self, *, now: float | None = None) -> HapticsLabSnapshot:
        timestamp = self._clock() if now is None else float(now)
        with self._lock:
            if self._started_at is not None:
                self._started_at = None
                self._scene = ""
                self._revision += 1
                self._stop_reason = "game_telemetry"
            return self._snapshot_locked(timestamp)

    def snapshot(self, *, now: float | None = None) -> HapticsLabSnapshot:
        timestamp = self._clock() if now is None else float(now)
        with self._lock:
            self._expire_locked(timestamp)
            return self._snapshot_locked(timestamp)

    def sample(self, *, now: float | None = None) -> HapticsLabOutput | None:
        timestamp = self._clock() if now is None else float(now)
        with self._lock:
            self._expire_locked(timestamp)
            if self._started_at is None or not self._scene:
                return None
            scene = self._scene
            elapsed = max(0.0, timestamp - self._started_at)
            intensity = self._intensity
            duration = self._duration_s
        return render_haptics_lab_scene(
            scene,
            elapsed_s=elapsed,
            duration_s=duration,
            intensity=intensity,
        )

    def _expire_locked(self, timestamp: float) -> None:
        if self._started_at is None:
            return
        if timestamp - self._started_at < self._duration_s:
            return
        self._started_at = None
        self._scene = ""
        self._revision += 1
        self._stop_reason = "completed"

    def _snapshot_locked(self, timestamp: float) -> HapticsLabSnapshot:
        active = self._started_at is not None and bool(self._scene)
        remaining = (
            max(0.0, self._duration_s - (timestamp - self._started_at))
            if active and self._started_at is not None
            else 0.0
        )
        return HapticsLabSnapshot(
            active=active,
            scene=self._scene,
            intensity=self._intensity,
            duration_s=self._duration_s,
            remaining_s=remaining,
            revision=self._revision,
            stop_reason=self._stop_reason,
        )
