from __future__ import annotations

import math
import logging
from collections.abc import Mapping
from dataclasses import dataclass

from modules.forzahorizon.effects import (
    BURNOUT_ROT_THRESHOLD,
    DRIVEN_WHEELS,
    LOW_SPEED_KMH,
)

from .frame import HapticFrame, SILENT_FRAME, clamp01


log = logging.getLogger("fhds.haptics")

_WHEELS = ("fl", "fr", "rl", "rr")
_ROLLING_ENTER_KMH = 0.5
_ROLLING_EXIT_KMH = 0.2
_ENGINE_ACCEL_ACTIVITY = 1.0
_ENGINE_RPM_ACTIVITY_MIN = 100.0
_ENGINE_RPM_ACTIVITY_RATIO = 0.05


@dataclass(slots=True)
class _Channels:
    left_low: float = 0.0
    left_high: float = 0.0
    right_low: float = 0.0
    right_high: float = 0.0

    def add(self, other: _Channels) -> None:
        self.left_low += other.left_low
        self.left_high += other.left_high
        self.right_low += other.right_low
        self.right_high += other.right_high

    def scaled(self, factor: float) -> _Channels:
        return _Channels(
            left_low=self.left_low * factor,
            left_high=self.left_high * factor,
            right_low=self.right_low * factor,
            right_high=self.right_high * factor,
        )


def _number(value, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _setting(settings, name: str, default: float) -> float:
    return max(0.0, _number(getattr(settings, name, default), default))


def _surface_components(value: float) -> tuple[float, float]:
    value = max(0.0, _number(value))
    high = value * 0.75
    if value > 0.30:
        low = value * 0.45
    elif value > 0.10:
        low = value * 0.20
    else:
        low = 0.0
    return low, high


def _collision_envelope(
    elapsed: float, duration: float, rebound_ratio: float
) -> tuple[float, float]:
    """Return low/high event energy for a main hit, gap, and rebound."""
    progress = clamp01(elapsed / max(1e-6, duration))
    rebound_ratio = clamp01(rebound_ratio)
    if progress < 0.30:
        local = progress / 0.30
        low = 1.0 - 0.35 * local
        high = 0.40 * (1.0 - local)
        return low, high
    if progress < (65.0 / 150.0):
        return 0.0, 0.0
    if progress < 0.80:
        local = (progress - 65.0 / 150.0) / (0.80 - 65.0 / 150.0)
        low = rebound_ratio * (1.0 - 0.40 * local)
        return low, low * 0.15
    local = (progress - 0.80) / 0.20
    low = rebound_ratio * 0.60 * (1.0 - local)
    return low, low * 0.10


class HapticMixer:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._rolling = False
        self._prev_accel: tuple[float, float] | None = None
        self._prev_suspension: tuple[float, float, float, float] | None = None
        self._prev_gear: int | None = None
        self._collision_started = 0.0
        self._collision_until = 0.0
        self._collision_left = 0.0
        self._collision_right = 0.0
        self._collision_armed = True
        self._collision_cooldown_until = 0.0
        self._shift_until = 0.0
        self._redline_started_at: float | None = None
        self._redline_active = False

    def _update_rolling(self, speed_kmh: float) -> bool:
        if self._rolling:
            self._rolling = speed_kmh > _ROLLING_EXIT_KMH
        else:
            self._rolling = speed_kmh >= _ROLLING_ENTER_KMH
        return self._rolling

    def update(self, telemetry: Mapping[str, object], settings, now: float) -> HapticFrame:
        if not getattr(settings, "enable_body_haptics", False) or not telemetry.get("on", False):
            if self._redline_active:
                reason = "body-toggle" if not getattr(
                    settings, "enable_body_haptics", False
                ) else "telemetry-off"
                log.info("Grip redline exited reason=%s", reason)
            self.reset()
            return SILENT_FRAME

        speed_kmh = max(0.0, _number(telemetry.get("speed")))
        rolling = self._update_rolling(speed_kmh)
        accel_raw = max(0.0, _number(telemetry.get("accel")))
        spin_strength = {wheel: 0.0 for wheel in _WHEELS}
        if speed_kmh < LOW_SPEED_KMH and accel_raw >= max(
            1.0, _setting(settings, "accel_deadzone", 50.0)
        ):
            drive_train = int(_number(telemetry.get("drive_train"), -1.0))
            driven = DRIVEN_WHEELS.get(drive_train, _WHEELS)
            full_scale = BURNOUT_ROT_THRESHOLD * 4.0
            for wheel in driven:
                rotation = abs(_number(telemetry.get(f"wheel_rotation_speed_{wheel}")))
                spin_strength[wheel] = clamp01(
                    (rotation - BURNOUT_ROT_THRESHOLD)
                    / (full_scale - BURNOUT_ROT_THRESHOLD)
                )

        contact_excitation = {
            wheel: 1.0 if rolling else spin_strength[wheel]
            for wheel in _WHEELS
        }

        now = _number(now)
        master = _setting(settings, "body_haptics_intensity", 1.0)
        road_scale = _setting(settings, "road_haptics_intensity", 1.0)
        impact_scale = _setting(settings, "impact_haptics_intensity", 1.0)
        slip_scale = _setting(settings, "slip_haptics_intensity", 1.0)

        continuous = _Channels()
        transient = _Channels()
        redline_event = _Channels()
        collision_event = _Channels()

        rpm = _number(telemetry.get("rpm"))
        idle_rpm = _number(telemetry.get("idle_rpm"))
        max_rpm = _number(telemetry.get("max_rpm"))
        rpm_margin = max(_ENGINE_RPM_ACTIVITY_MIN, idle_rpm * _ENGINE_RPM_ACTIVITY_RATIO)
        engine_active = (
            rolling
            or accel_raw > _ENGINE_ACCEL_ACTIVITY
            or rpm > idle_rpm + rpm_margin
        )

        if engine_active and max_rpm > idle_rpm:
            rpm_ratio = clamp01((rpm - idle_rpm) / (max_rpm - idle_rpm))
            engine_hz = 40.0 + rpm_ratio * 80.0
            throttle = clamp01(accel_raw / 255.0)
            engine_amplitude = (
                0.08 + throttle * 0.25 + rpm_ratio * 0.1
            ) * _setting(settings, "engine_haptics_intensity", 1.0)
        else:
            rpm_ratio = 0.0
            engine_hz = 0.0
            engine_amplitude = 0.0

        redline_enabled = bool(
            getattr(settings, "enable_grip_redline_haptics", False)
        )
        redline_left = bool(getattr(settings, "grip_redline_left", True))
        redline_right = bool(getattr(settings, "grip_redline_right", False))
        engine_scale = _setting(settings, "engine_haptics_intensity", 1.0)
        accel_deadzone = max(1.0, _setting(settings, "accel_deadzone", 0.0))
        redline_ratio = rpm / max_rpm if max_rpm > 0.0 else 0.0
        enter_ratio = clamp01(_setting(settings, "grip_redline_ratio", 0.93))
        release_ratio = min(
            enter_ratio,
            clamp01(_setting(settings, "grip_redline_release_ratio", 0.90)),
        )
        throttle_active = accel_raw >= accel_deadzone
        redline_available = (
            redline_enabled
            and (redline_left or redline_right)
            and engine_scale > 0.0
            and master > 0.0
        )

        exit_reason = None
        if not redline_available:
            if not redline_enabled or not (redline_left or redline_right):
                exit_reason = "toggle"
            elif engine_scale <= 0.0:
                exit_reason = "engine-intensity"
            else:
                exit_reason = "body-intensity"
            self._redline_active = False
        elif not throttle_active:
            exit_reason = "throttle"
            self._redline_active = False
        elif self._redline_active:
            if redline_ratio < release_ratio:
                exit_reason = "ratio"
                self._redline_active = False
        elif max_rpm > 0.0 and redline_ratio >= enter_ratio:
            self._redline_active = True
            self._redline_started_at = now
            sides = "both" if redline_left and redline_right else (
                "left" if redline_left else "right"
            )
            log.info(
                "Grip redline entered rpm=%.0f max_rpm=%.0f ratio=%.3f "
                "accel=%.0f sides=%s",
                rpm,
                max_rpm,
                redline_ratio,
                accel_raw,
                sides,
            )

        if not self._redline_active:
            if self._redline_started_at is not None and exit_reason is not None:
                log.info(
                    "Grip redline exited reason=%s rpm=%.0f max_rpm=%.0f ratio=%.3f",
                    exit_reason,
                    rpm,
                    max_rpm,
                    redline_ratio,
                )
            self._redline_started_at = None

        redline_amplitude = 0.0
        if self._redline_active and self._redline_started_at is not None:
            pulse_hz = max(1.0, _setting(settings, "grip_redline_freq", 10.0))
            period = 1.0 / pulse_hz
            phase = (now - self._redline_started_at) % period
            if phase < period * 0.5:
                redline_amplitude = (
                    _setting(settings, "grip_redline_amp", 192.0)
                    / 255.0
                    * _setting(settings, "grip_redline_gain", 1.5)
                    * engine_scale
                )
                redline_low = redline_amplitude * clamp01(
                    _setting(settings, "grip_redline_low_ratio", 0.25)
                )
                if redline_left:
                    redline_event.left_low = redline_low
                    redline_event.left_high = redline_amplitude
                if redline_right:
                    redline_event.right_low = redline_low
                    redline_event.right_high = redline_amplitude

        for wheel in _WHEELS:
            excitation = contact_excitation[wheel]
            if excitation <= 0.0:
                continue
            side = "left" if wheel in ("fl", "rl") else "right"
            surface_low, surface_high = _surface_components(
                telemetry.get(f"surface_rumble_{wheel}")
            )
            if side == "left":
                continuous.left_low += surface_low * road_scale * excitation
                continuous.left_high += surface_high * road_scale * excitation
            else:
                continuous.right_low += surface_low * road_scale * excitation
                continuous.right_high += surface_high * road_scale * excitation

        strip_left = max(
            contact_excitation[wheel]
            if _number(telemetry.get(f"wheel_on_rumble_strip_{wheel}")) != 0.0
            else 0.0
            for wheel in ("fl", "rl")
        )
        strip_right = max(
            contact_excitation[wheel]
            if _number(telemetry.get(f"wheel_on_rumble_strip_{wheel}")) != 0.0
            else 0.0
            for wheel in ("fr", "rr")
        )
        continuous.left_high += 0.35 * road_scale * strip_left
        continuous.right_high += 0.35 * road_scale * strip_right

        if rolling:
            speed_mps = speed_kmh / 3.6
            if speed_mps > 3.0:
                asphalt = min(1.0, (speed_mps - 3.0) / 80.0) * 0.12 * road_scale
                continuous.left_high += asphalt
                continuous.right_high += asphalt

        puddle_left = clamp01(max(
            _number(telemetry.get(f"wheel_in_puddle_{wheel}"))
            * contact_excitation[wheel]
            for wheel in ("fl", "rl")
        ))
        puddle_right = clamp01(max(
            _number(telemetry.get(f"wheel_in_puddle_{wheel}"))
            * contact_excitation[wheel]
            for wheel in ("fr", "rr")
        ))
        continuous.left_low += puddle_left * 0.6 * road_scale
        continuous.left_high += puddle_left * 0.3 * road_scale
        continuous.right_low += puddle_right * 0.6 * road_scale
        continuous.right_high += puddle_right * 0.3 * road_scale

        combined_slips = {
            wheel: abs(_number(telemetry.get(f"tire_combined_slip_{wheel}")))
            for wheel in _WHEELS
        }
        combined_slip_left = max(combined_slips["fl"], combined_slips["rl"])
        combined_slip_right = max(combined_slips["fr"], combined_slips["rr"])
        slip_threshold = _setting(settings, "slip_haptics_threshold", 0.8)
        if speed_kmh < LOW_SPEED_KMH:
            slip_left = max(spin_strength["fl"], spin_strength["rl"])
            slip_right = max(spin_strength["fr"], spin_strength["rr"])
            continuous.left_low += slip_left * 0.5 * slip_scale
            continuous.right_low += slip_right * 0.5 * slip_scale
        else:
            slip_left = combined_slip_left
            slip_right = combined_slip_right
            continuous.left_low += (
                max(0.0, slip_left - slip_threshold) * 0.5 * slip_scale
            )
            continuous.right_low += (
                max(0.0, slip_right - slip_threshold) * 0.5 * slip_scale
            )

        suspension = tuple(
            _number(telemetry.get(f"suspension_travel_meters_{wheel}"))
            for wheel in _WHEELS
        )
        if self._prev_suspension is not None:
            threshold = _setting(settings, "suspension_haptics_delta_threshold", 0.015)
            drops = tuple(current - previous
                          for current, previous in zip(suspension, self._prev_suspension))
            if drops[0] < -threshold or drops[2] < -threshold:
                transient.left_low += impact_scale
            if drops[1] < -threshold or drops[3] < -threshold:
                transient.right_low += impact_scale
        self._prev_suspension = suspension

        accel_x = _number(telemetry.get("accel_x"))
        accel_z = _number(telemetry.get("accel_z"))
        jerk = 0.0
        jerk_intensity = 0.0
        if self._prev_accel is not None:
            jerk = math.hypot(accel_x - self._prev_accel[0], accel_z - self._prev_accel[1])
            jerk_threshold = _setting(settings, "collision_haptics_jerk_threshold", 3.0)
            if jerk > jerk_threshold:
                jerk_intensity = clamp01((jerk - jerk_threshold) / 27.0)
        else:
            jerk_threshold = _setting(settings, "collision_haptics_jerk_threshold", 3.0)
        self._prev_accel = (accel_x, accel_z)

        smashable = max(0.0, _number(telemetry.get("smashable_vel_diff")))
        smash_intensity = clamp01(smashable / 15.0) if smashable > 3.0 else 0.0
        jerk_active = jerk > jerk_threshold
        smash_active = smashable > 3.0
        if (
            not jerk_active
            and not smash_active
            and now >= self._collision_cooldown_until
        ):
            self._collision_armed = True

        collision_intensity = max(jerk_intensity, smash_intensity)
        if self._collision_armed and collision_intensity > 0.0:
            duration = _setting(settings, "collision_haptics_duration_ms", 150.0) / 1000.0
            self._collision_started = now
            self._collision_until = now + duration
            self._collision_cooldown_until = now + (
                _setting(settings, "collision_haptics_cooldown_ms", 250.0) / 1000.0
            )
            self._collision_armed = False
            scaled = collision_intensity * impact_scale
            weak_side = clamp01(
                _setting(settings, "collision_haptics_weak_side_ratio", 0.35)
            )
            if accel_x > 5.0:
                direction = "left"
                self._collision_left, self._collision_right = scaled, scaled * weak_side
            elif accel_x < -5.0:
                direction = "right"
                self._collision_left, self._collision_right = scaled * weak_side, scaled
            else:
                direction = "center"
                self._collision_left = self._collision_right = scaled

            source = "both" if jerk_active and smash_active else (
                "jerk" if jerk_active else "smashable"
            )
            log.info(
                "Collision armed source=%s jerk=%.3f smashable=%.3f "
                "intensity=%.3f direction=%s",
                source,
                jerk,
                smashable,
                collision_intensity,
                direction,
            )

        collision_active = now < self._collision_until
        if collision_active:
            duration = max(1e-6, self._collision_until - self._collision_started)
            low_envelope, high_envelope = _collision_envelope(
                now - self._collision_started,
                duration,
                _setting(settings, "collision_haptics_rebound_ratio", 0.45),
            )
            collision_event.left_low = self._collision_left * low_envelope
            collision_event.left_high = self._collision_left * high_envelope
            collision_event.right_low = self._collision_right * low_envelope
            collision_event.right_high = self._collision_right * high_envelope

        gear = int(_number(telemetry.get("gear")))
        grip_shift_enabled = bool(
            getattr(settings, "enable_grip_gear_shift_haptics", False)
        )
        if not grip_shift_enabled:
            self._shift_until = 0.0
        elif (self._prev_gear is not None and self._prev_gear > 0 and gear > 0
              and gear != self._prev_gear and speed_kmh > 3.0):
            self._shift_until = now + (
                _setting(settings, "grip_gear_shift_duration_ms", 100.0) / 1000.0
            )
        self._prev_gear = gear
        if grip_shift_enabled and now < self._shift_until:
            grip_shift = _setting(settings, "grip_gear_shift_strength", 0.8)
            transient.left_low += grip_shift * impact_scale
            transient.right_low += grip_shift * impact_scale

        brake = _number(telemetry.get("brake"))
        brake_threshold = max(1.0, _setting(settings, "abs_brake_threshold", 100.0))
        abs_min_speed = _setting(settings, "abs_min_speed_kmh", 15.0)
        abs_slip_threshold = _setting(settings, "abs_combined_slip_threshold", 1.0)
        if (brake >= brake_threshold
                and speed_kmh >= abs_min_speed
                and max(combined_slip_left, combined_slip_right) > abs_slip_threshold
                and int(now * 15.0) % 2 == 0):
            transient.left_low += 0.5 * slip_scale
            transient.right_low += 0.5 * slip_scale

        continuous_duck = (
            clamp01(_setting(settings, "grip_redline_background_duck", 0.30))
            if self._redline_active else 1.0
        )
        background = continuous.scaled(continuous_duck)
        background.add(transient)
        engine_amplitude *= continuous_duck

        non_collision = background.scaled(1.0)
        non_collision.add(redline_event)
        collision_duck = (
            clamp01(_setting(settings, "collision_background_duck", 0.20))
            if collision_active else 1.0
        )
        mixed = non_collision.scaled(collision_duck)
        mixed.add(collision_event)
        compatible_background = background.scaled(collision_duck)
        engine_amplitude *= collision_duck
        engine_amplitude = clamp01(engine_amplitude * master)

        compatible_low = None
        compatible_high = None
        if redline_amplitude > 0.0 or collision_active:
            compatible_low = clamp01(
                max(
                    compatible_background.left_low,
                    compatible_background.right_low,
                ) * master
                + 0.5 * engine_amplitude
                + (
                    redline_amplitude * collision_duck * master
                    if redline_left else 0.0
                )
                + max(collision_event.left_low, collision_event.left_high) * master
            )
            compatible_high = clamp01(
                max(
                    compatible_background.left_high,
                    compatible_background.right_high,
                ) * master
                + (
                    redline_amplitude * collision_duck * master
                    if redline_right else 0.0
                )
                + max(collision_event.right_low, collision_event.right_high) * master
            )

        return HapticFrame(
            left_low=clamp01(mixed.left_low * master),
            left_high=clamp01(mixed.left_high * master),
            right_low=clamp01(mixed.right_low * master),
            right_high=clamp01(mixed.right_high * master),
            engine_hz=max(0.0, engine_hz),
            engine_amplitude=engine_amplitude,
            compatible_low_frequency=compatible_low,
            compatible_high_frequency=compatible_high,
        )
