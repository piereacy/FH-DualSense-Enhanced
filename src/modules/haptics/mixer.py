from __future__ import annotations

import math
from collections.abc import Mapping

from modules.forzahorizon.effects import (
    BURNOUT_ROT_THRESHOLD,
    DRIVEN_WHEELS,
    LOW_SPEED_KMH,
)

from .frame import HapticFrame, SILENT_FRAME, clamp01


_WHEELS = ("fl", "fr", "rl", "rr")
_ROLLING_ENTER_KMH = 0.5
_ROLLING_EXIT_KMH = 0.2
_ENGINE_ACCEL_ACTIVITY = 1.0
_ENGINE_RPM_ACTIVITY_MIN = 100.0
_ENGINE_RPM_ACTIVITY_RATIO = 0.05


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
        self._shift_until = 0.0
        self._redline_started_at: float | None = None
        self._redline_until = 0.0

    def _update_rolling(self, speed_kmh: float) -> bool:
        if self._rolling:
            self._rolling = speed_kmh > _ROLLING_EXIT_KMH
        else:
            self._rolling = speed_kmh >= _ROLLING_ENTER_KMH
        return self._rolling

    def update(self, telemetry: Mapping[str, object], settings, now: float) -> HapticFrame:
        if not getattr(settings, "enable_body_haptics", False) or not telemetry.get("on", False):
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

        left_low = 0.0
        left_high = 0.0
        right_low = 0.0
        right_high = 0.0

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

        redline_enabled = bool(getattr(settings, "enable_rev_limiter", False))
        engine_scale = _setting(settings, "engine_haptics_intensity", 1.0)
        accel_deadzone = max(1.0, _setting(settings, "accel_deadzone", 0.0))
        redline_ratio = rpm / max_rpm if max_rpm > 0.0 else 0.0
        above_redline = (
            redline_enabled
            and engine_scale > 0.0
            and accel_raw >= accel_deadzone
            and redline_ratio >= _setting(settings, "rev_limit_ratio", 0.93)
        )
        hold_seconds = _setting(settings, "rev_limit_hold_ms", 120.0) / 1000.0
        if not redline_enabled or engine_scale <= 0.0:
            self._redline_started_at = None
            self._redline_until = 0.0
        elif above_redline:
            if self._redline_started_at is None or now >= self._redline_until:
                self._redline_started_at = now
            self._redline_until = now + hold_seconds
        elif now >= self._redline_until:
            self._redline_started_at = None

        redline_amplitude = 0.0
        redline_latched = redline_enabled and engine_scale > 0.0 and (
            above_redline or now < self._redline_until
        )
        if redline_latched and self._redline_started_at is not None:
            pulse_hz = max(1.0, _setting(settings, "rev_limit_freq", 10.0))
            period = 1.0 / pulse_hz
            phase = (now - self._redline_started_at) % period
            if phase < period * 0.5:
                redline_amplitude = clamp01(
                    _setting(settings, "rev_limit_amp", 96.0) / 255.0
                ) * engine_scale

        left_high += redline_amplitude
        right_high += redline_amplitude

        for wheel in _WHEELS:
            excitation = contact_excitation[wheel]
            if excitation <= 0.0:
                continue
            side = "left" if wheel in ("fl", "rl") else "right"
            surface_low, surface_high = _surface_components(
                telemetry.get(f"surface_rumble_{wheel}")
            )
            if side == "left":
                left_low += surface_low * road_scale * excitation
                left_high += surface_high * road_scale * excitation
            else:
                right_low += surface_low * road_scale * excitation
                right_high += surface_high * road_scale * excitation

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
        left_high += 0.35 * road_scale * strip_left
        right_high += 0.35 * road_scale * strip_right

        if rolling:
            speed_mps = speed_kmh / 3.6
            if speed_mps > 3.0:
                asphalt = min(1.0, (speed_mps - 3.0) / 80.0) * 0.12 * road_scale
                left_high += asphalt
                right_high += asphalt

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
        left_low += puddle_left * 0.6 * road_scale
        left_high += puddle_left * 0.3 * road_scale
        right_low += puddle_right * 0.6 * road_scale
        right_high += puddle_right * 0.3 * road_scale

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
            left_low += slip_left * 0.5 * slip_scale
            right_low += slip_right * 0.5 * slip_scale
        else:
            slip_left = combined_slip_left
            slip_right = combined_slip_right
            left_low += max(0.0, slip_left - slip_threshold) * 0.5 * slip_scale
            right_low += max(0.0, slip_right - slip_threshold) * 0.5 * slip_scale

        suspension = tuple(
            _number(telemetry.get(f"suspension_travel_meters_{wheel}"))
            for wheel in _WHEELS
        )
        if self._prev_suspension is not None:
            threshold = _setting(settings, "suspension_haptics_delta_threshold", 0.015)
            drops = tuple(current - previous
                          for current, previous in zip(suspension, self._prev_suspension))
            if drops[0] < -threshold or drops[2] < -threshold:
                left_low += impact_scale
            if drops[1] < -threshold or drops[3] < -threshold:
                right_low += impact_scale
        self._prev_suspension = suspension

        accel_x = _number(telemetry.get("accel_x"))
        accel_z = _number(telemetry.get("accel_z"))
        jerk_intensity = 0.0
        if self._prev_accel is not None:
            jerk = math.hypot(accel_x - self._prev_accel[0], accel_z - self._prev_accel[1])
            jerk_threshold = _setting(settings, "collision_haptics_jerk_threshold", 3.0)
            if jerk > jerk_threshold:
                jerk_intensity = clamp01((jerk - jerk_threshold) / 27.0)
        self._prev_accel = (accel_x, accel_z)

        smashable = max(0.0, _number(telemetry.get("smashable_vel_diff")))
        smash_intensity = clamp01(smashable / 15.0) if smashable > 3.0 else 0.0
        collision_intensity = max(jerk_intensity, smash_intensity)
        if collision_intensity > 0.0:
            duration = _setting(settings, "collision_haptics_duration_ms", 150.0) / 1000.0
            self._collision_started = now
            self._collision_until = now + duration
            scaled = collision_intensity * impact_scale
            if accel_x > 5.0:
                self._collision_left, self._collision_right = scaled, scaled * 0.2
            elif accel_x < -5.0:
                self._collision_left, self._collision_right = scaled * 0.2, scaled
            else:
                self._collision_left = self._collision_right = scaled

        if now < self._collision_until:
            duration = max(1e-6, self._collision_until - self._collision_started)
            envelope = clamp01((self._collision_until - now) / duration)
            left_low += self._collision_left * envelope
            right_low += self._collision_right * envelope

        gear = int(_number(telemetry.get("gear")))
        if (self._prev_gear is not None and self._prev_gear > 0 and gear > 0
                and gear != self._prev_gear and speed_kmh > 3.0):
            self._shift_until = now + _setting(settings, "gear_shift_duration_ms", 100.0) / 1000.0
        self._prev_gear = gear
        if now < self._shift_until:
            left_low += 0.8 * impact_scale
            right_low += 0.8 * impact_scale

        brake = _number(telemetry.get("brake"))
        brake_threshold = max(1.0, _setting(settings, "abs_brake_threshold", 100.0))
        abs_min_speed = _setting(settings, "abs_min_speed_kmh", 15.0)
        abs_slip_threshold = _setting(settings, "abs_combined_slip_threshold", 1.0)
        if (brake >= brake_threshold
                and speed_kmh >= abs_min_speed
                and max(combined_slip_left, combined_slip_right) > abs_slip_threshold
                and int(now * 15.0) % 2 == 0):
            left_low += 0.5 * slip_scale
            right_low += 0.5 * slip_scale

        return HapticFrame(
            left_low=clamp01(left_low * master),
            left_high=clamp01(left_high * master),
            right_low=clamp01(right_low * master),
            right_high=clamp01(right_high * master),
            engine_hz=max(0.0, engine_hz),
            engine_amplitude=clamp01(engine_amplitude * master),
        )
