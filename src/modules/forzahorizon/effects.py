"""Forza Horizon-aware adaptive trigger logic.

  TriggerAnimations - every trigger effect (ABS, gear shift, traction, resistance...).
                      Owns timing state for effects that span frames.
  Controller        - builds L2 / R2 and produces a frame for each per tick.
"""
import math
import time

from modules.dualsense.adaptive_trigger import (
    RAW_MAX, off, rigid, vibrate, vibrate_zones, rigid_zones,
)

# Below this car speed (km/h) I trust raw wheel rotation instead of slip_ratio
# (slip_ratio degenerates near zero speed). Above it, slip_ratio is canonical.
LOW_SPEED_KMH = 5.0
# Wheel angular speed (rad/s) above which I count as spinning at standstill.
# ~30 rad/s = ~3 wheel revs/sec, clearly spun-up regardless of tire size.
BURNOUT_ROT_THRESHOLD = 30.0

# Forza drive_train enum -> wheels that receive engine torque.
DRIVEN_WHEELS = {0: ("fl", "fr"), 1: ("rl", "rr"), 2: ("fl", "fr", "rl", "rr")}
ALL_WHEELS = ("fl", "fr", "rl", "rr")
_TRACTION_UNSET = object()


class _AsymmetricEwma:
    """Elapsed-time EWMA with a fast attack and a slower release."""

    def __init__(self):
        self.value = 0.0
        self._last_at = None

    def reset(self):
        self.value = 0.0
        self._last_at = None

    def update(self, target, now, attack_ms, release_ms):
        target = max(0.0, min(1.0, float(target)))
        if self._last_at is None:
            self._last_at = now
            return self.value
        dt = max(0.0, now - self._last_at)
        self._last_at = now
        tau_ms = attack_ms if target > self.value else release_ms
        tau = max(0.001, float(tau_ms) / 1000.0)
        alpha = 1.0 - math.exp(-dt / tau)
        self.value += (target - self.value) * alpha
        self.value = max(0.0, min(1.0, self.value))
        return self.value


def _amp_to_strength(amp_byte):
    return max(1, min(8, (max(0, int(amp_byte)) // 32) + 1))

def _clamp01(value):
    return max(0.0, min(1.0, float(value)))

def _normalize(value, threshold, full_scale):
    span = max(1e-6, float(full_scale) - float(threshold))
    return _clamp01((float(value) - float(threshold)) / span)

def _lerp(low, high, ratio):
    return float(low) + (float(high) - float(low)) * _clamp01(ratio)

def _max_slip(t, prefix, wheels=("fl", "fr", "rl", "rr")):
    return max(abs(t[f"{prefix}_{w}"]) for w in wheels)

def _ramp(value, deadzone, baseline, max_force, curve, ceiling):
    """deadzone..ceiling -> baseline..max_force, curve = exponent."""
    if value < deadzone:
        return baseline
    r = min(1.0, (value - deadzone) / max(ceiling - deadzone, 1))
    return baseline + (max_force - baseline) * (r ** curve)

def _wall_state(value, engaged, engage_at, release_at):
    """Hysteresis: enter wall at >= engage_at, leave at < release_at."""
    return value >= release_at if engaged else value >= engage_at

def build_wall(zones):
    """Static firmware wall - top `zones` (1-9) maxed. Built once at startup."""
    n = max(1, min(9, int(zones)))
    return rigid_zones([0] * (10 - n) + [8] * n)

def build_brake_walls(static_at, force, wall_zones):
    """End wall (top `wall_zones`) plus a static wall from brake byte `static_at` down.

    From `static_at` to the bottom of travel every zone holds `force` (a 0-255 byte
    mapped to strength) so the resistance never lightens again past the threshold; the
    top `wall_zones` stay maxed as the end wall. Firmware-held, so a fast stab can't
    skip it."""
    n = max(1, min(9, int(wall_zones)))
    strength = _amp_to_strength(force)
    start = min(9, int(static_at) * 10 // 256)
    zones = [strength if i >= start else 0 for i in range(10)]
    for i in range(10 - n, 10):
        zones[i] = 8
    return rigid_zones(zones)


# --- Animations -----------------------------------------------------------

class TriggerAnimations:
    """Every trigger effect lives here. Methods return an HID frame or None."""

    def __init__(self):
        self._prev_gear = None
        self._shift_until = 0.0
        self._rev_until = 0.0
        self._wheelspin_active = False
        self._wheelspin_ewma = _AsymmetricEwma()
        self._abs_until = 0.0
        self._abs_level = 0.0

    def reset_transients(self):
        self._prev_gear = None
        self._shift_until = 0.0
        self._rev_until = 0.0
        self._wheelspin_active = False
        self._wheelspin_ewma.reset()
        self._abs_until = 0.0
        self._abs_level = 0.0

    def arm_shift(self, t, s, now):
        gear = t["gear"]
        if self._prev_gear is not None and gear != self._prev_gear:
            self._shift_until = now + s.gear_shift_duration_ms / 1000.0
        self._prev_gear = gear

    def shift_burst(self, s, now, pedal, wall_engage_at):
        if now >= self._shift_until:
            return None
        # Wall 0hz for kickback, else normal vibrate.
        if pedal >= (wall_engage_at + RAW_MAX) // 2:
            return vibrate_zones(_amp_to_strength(s.gear_shift_amp), 0, s.wall_zones)
        return vibrate(s.gear_shift_freq, s.gear_shift_amp)

    def rev_buzz(self, t, s, now):
        """Return the R2 trigger rev-limiter vibration while throttle is held."""
        throttle_active = t["accel"] >= max(1, s.accel_deadzone)
        if not s.enable_rev_limiter or not throttle_active:
            self._rev_until = 0.0
            return None

        handbrake_full_throttle = (
            t["accel"] >= RAW_MAX * 0.8
            and t["handbrake"] > 16
            and t["speed"] < 1
        )
        if handbrake_full_throttle:
            return vibrate(s.rev_limit_freq, s.rev_limit_amp)

        max_rpm = t["max_rpm"]
        rpm_ratio = t["rpm"] / max_rpm if max_rpm > 0 else 0.0
        if rpm_ratio > s.rev_limit_ratio:
            self._rev_until = now + max(0.0, s.rev_limit_hold_ms) / 1000.0
        if now < self._rev_until:
            return vibrate(s.rev_limit_freq, s.rev_limit_amp)
        return None

    def idle_buzz(self, t, s, now):
        # Software-oscillated idle: alternate vibrate amp every half-period for a chug feel.
        if not s.enable_idle_buzz:
            return None
        if t["speed"] >= s.idle_max_speed_kmh:
            return None
        if not (1 <= t["accel"] <= s.idle_accel_max):
            return None
        loud = (now / s.idle_period_s) % 1.0 < 0.5
        amp = s.idle_amp_high if loud else s.idle_amp_low
        return vibrate(s.idle_freq, amp)

    def _reset_traction(self):
        self._wheelspin_active = False
        self._wheelspin_ewma.reset()

    def _traction_effect(self, t, s, now, wheels, use_rotation_at_low_speed):
        if not s.enable_wheelspin_buzz:
            self._reset_traction()
            return None
        if t["speed"] < LOW_SPEED_KMH and not use_rotation_at_low_speed:
            self._reset_traction()
            return None
        sensitivity = max(0.1, float(s.wheelspin_sensitivity))
        if t["speed"] < LOW_SPEED_KMH:
            samples = {
                wheel: abs(t[f"wheel_rotation_speed_{wheel}"])
                for wheel in wheels
            }
            threshold = max(0.0, s.wheelspin_burnout_rotation_threshold) / sensitivity
            full_scale = max(threshold + 1e-6, s.wheelspin_burnout_rotation_full_scale)
        else:
            samples = {
                wheel: abs(t[f"tire_slip_ratio_{wheel}"])
                for wheel in wheels
            }
            threshold = max(0.0, s.wheelspin_slip_threshold) / sensitivity
            full_scale = max(threshold + 1e-6, s.wheelspin_slip_full_scale)

        dominant_wheel, signal = max(samples.items(), key=lambda item: item[1])
        hysteresis = _clamp01(s.wheelspin_hysteresis)
        release_at = threshold * (1.0 - hysteresis)
        self._wheelspin_active = _wall_state(
            signal, self._wheelspin_active, threshold, release_at
        )
        target = _normalize(signal, threshold, full_scale) if self._wheelspin_active else 0.0
        level = self._wheelspin_ewma.update(
            target,
            now,
            s.wheelspin_attack_ms,
            s.wheelspin_release_ms,
        )
        if level < 0.005:
            return None

        # Keep distinct road-material signatures without letting material create
        # energy by itself. The wheel with the strongest driven slip chooses it.
        puddle = t[f"wheel_in_puddle_{dominant_wheel}"] > 0
        rumble = abs(t[f"surface_rumble_{dominant_wheel}"])
        if puddle:
            freq_min, freq_max, amp_scale = (
                s.wheelspin_water_freq_min,
                s.wheelspin_water_freq_max,
                0.5,
            )
        elif rumble > 0.30:
            freq_min, freq_max, amp_scale = (
                s.wheelspin_gravel_freq_min,
                s.wheelspin_gravel_freq_max,
                2.0,
            )
        elif rumble > 0.10:
            freq_min, freq_max, amp_scale = (
                s.wheelspin_dirt_freq_min,
                s.wheelspin_dirt_freq_max,
                1.5,
            )
        else:
            freq_min, freq_max, amp_scale = (
                s.wheelspin_tarmac_freq_min,
                s.wheelspin_tarmac_freq_max,
                1.0,
            )

        # HorizonHaptics-inspired G adjustment, deliberately kept subordinate
        # to slip: one longitudinal G gives 0.8x amplitude at the default 0.25.
        acceleration = math.sqrt(0.25 * t["accel_x"] ** 2 + t["accel_z"] ** 2)
        g_force = acceleration / 9.80665
        g_damping = max(
            0.7,
            1.0 / (1.0 + max(0.0, s.wheelspin_g_damping) * g_force),
        )
        output_level = 0.15 + 0.85 * level if self._wheelspin_active else level
        frequency = _lerp(freq_min, freq_max, level)
        amplitude = s.wheelspin_amp * output_level * amp_scale * g_damping
        return vibrate(frequency, amplitude)

    def traction_buzz(self, t, s, now):
        """Return (pedal route, one shared longitudinal-grip effect).

        Forza's pedal telemetry is the source of truth. Braking-only feedback
        routes to L2; any active accelerator routes it to R2. At speed, braking
        observes every tire while accelerator-only observes driven tires. Near
        standstill, raw rotation is valid only when the accelerator is active.
        """
        brake_active = t["brake"] >= max(1, s.brake_deadzone)
        accel_active = t["accel"] >= max(1, s.accel_deadzone)
        if not brake_active and not accel_active:
            self._reset_traction()
            return None, None

        route = "r2" if accel_active else "l2"
        driven = DRIVEN_WHEELS.get(t["drive_train"], ALL_WHEELS)
        if t["speed"] < LOW_SPEED_KMH:
            wheels = driven
            use_rotation = accel_active
        else:
            wheels = ALL_WHEELS if brake_active else driven
            use_rotation = False
        return route, self._traction_effect(
            t, s, now, wheels, use_rotation_at_low_speed=use_rotation
        )

    def wheelspin_buzz(self, t, s, now):
        """R2-compatible entry point retained for existing profiles/tests."""
        if t["accel"] < max(1, s.accel_deadzone):
            self._reset_traction()
            return None
        wheels = DRIVEN_WHEELS.get(t["drive_train"], ALL_WHEELS)
        return self._traction_effect(
            t, s, now, wheels, use_rotation_at_low_speed=True
        )

    def abs_pulse(self, t, s, now):
        if (not s.enable_abs
                or t["brake"] < max(1, s.abs_brake_threshold)
                or t["speed"] < s.abs_min_speed_kmh):
            self._abs_until = 0.0
            self._abs_level = 0.0
            return None

        sensitivity = max(0.1, float(s.abs_sensitivity))
        ratio_threshold = max(0.0, s.abs_slip_ratio_threshold) / sensitivity
        combined_threshold = max(0.0, s.abs_combined_slip_threshold) / sensitivity
        ratio_slip = _max_slip(t, "tire_slip_ratio")
        combined_slip = _max_slip(t, "tire_combined_slip")
        ratio_active = ratio_slip >= ratio_threshold
        combined_active = combined_slip >= combined_threshold

        if ratio_active or combined_active:
            ratio_level = (
                _normalize(ratio_slip, ratio_threshold, s.abs_slip_full_scale)
                if ratio_active else 0.0
            )
            combined_level = (
                _normalize(combined_slip, combined_threshold, s.abs_slip_full_scale)
                * _clamp01(s.abs_combined_slip_weight)
                if combined_active else 0.0
            )
            self._abs_level = max(ratio_level, combined_level)
            self._abs_until = now + max(0.0, s.abs_hold_ms) / 1000.0
        elif now >= self._abs_until:
            self._abs_level = 0.0
            return None

        frequency = _lerp(s.abs_freq_min, s.abs_freq, self._abs_level)
        amplitude = _lerp(s.abs_amp_min, s.abs_amp, self._abs_level)
        return vibrate_zones(
            _amp_to_strength(amplitude), frequency, s.abs_wall_zones
        )

    def brake_resistance(self, t, s):
        handbrake = s.enable_handbrake_bonus and t["handbrake"]
        if not s.enable_brake_resistance:
            return rigid(s.handbrake_bonus) if handbrake else off()
        force = _ramp(t["brake"], s.brake_deadzone, s.brake_baseline_force,
                      s.brake_max_force, s.brake_curve, s.brake_wall_engage_at)
        if handbrake:
            force += s.handbrake_bonus
        return rigid(force)

    def throttle_ramp(self, t, s):
        if not s.enable_throttle_resistance:
            return off()
        return rigid(_ramp(t["accel"], s.accel_deadzone, s.throttle_baseline_force,
                           s.throttle_max_force, s.throttle_curve, s.throttle_wall_engage_at))


# --- Controller -----------------------------------------------------------

class Controller:
    """Produces (L2, R2) frames per tick.

    Each chain returns the FIRST non-empty effect; later items are masked.
    Order is hand-tuned so the "loudest" / most informative effect wins.

    L2 priority (top wins):
        1. Gear shift thump    - one-shot burst on every shift, brief
        2. ABS pulse           - tire lockup buzz under hard braking
        3. Traction feedback   - braking tire longitudinal grip
        4. Firmware end wall   - hard wall near 100% travel (hysteresis)
        5. Static brake wall   - optional fixed wall at brake_static_wall_at
        6. Brake resistance    - default rigid ramp 0..max_force

    R2 priority (top wins):
        1. Gear shift thump    - one-shot burst on every shift, brief
        2. Idle buzz           - stationary with light throttle
        3. Traction feedback   - accelerator/both-pedal longitudinal grip
        4. Rev limiter buzz    - high RPM while throttle remains active
        5. Firmware end wall   - hard wall near 100% travel (hysteresis)
        6. Throttle resistance - default rigid ramp 0..max_force
    """

    def __init__(self, settings):
        self.anim = TriggerAnimations()
        self.wall = build_wall(settings.wall_zones)
        self._l2_in_wall = False
        self._r2_in_wall = False

    def update(self, t, s):
        if not t["on"]:
            self.anim.reset_transients()
            self._l2_in_wall = False
            self._r2_in_wall = False
            return off(), off()
        now = time.monotonic()
        if s.enable_gear_shift or s.enable_gear_shift_brake:
            self.anim.arm_shift(t, s, now)
        route, traction = self.anim.traction_buzz(t, s, now)
        return (
            self.L2(t, s, now, traction if route == "l2" else None),
            self.R2(t, s, now, traction if route == "r2" else None),
        )

    def L2(self, t, s, now, traction=_TRACTION_UNSET):
        brake = t["brake"]

        if traction is _TRACTION_UNSET:
            route, effect = self.anim.traction_buzz(t, s, now)
            traction = effect if route == "l2" else None

        # 1. Gear shift thump - brief burst on shift, masks everything below
        if s.enable_gear_shift_brake:
            shift = self.anim.shift_burst(s, now, brake, s.brake_wall_engage_at)
            if shift:
                return shift

        # 2. ABS pulse - tire lockup under hard braking
        pulse = self.anim.abs_pulse(t, s, now)
        if pulse:
            return pulse

        # 3. Generic braking traction feedback
        if traction is not None:
            return traction

        # 4. Firmware end wall - hard wall near 100% travel (latched via hysteresis)
        self._l2_in_wall = _wall_state(brake, self._l2_in_wall,
                                       s.brake_wall_engage_at, s.brake_wall_release_at)
        if self._l2_in_wall:
            return self.wall

        # 5. Static brake wall - optional fixed wall mid-travel; replaces ramp
        if s.enable_brake_static_wall:
            return build_brake_walls(s.brake_static_wall_at, s.brake_static_wall_force, s.wall_zones)

        # 6. Brake resistance - default rigid ramp
        return self.anim.brake_resistance(t, s)

    def R2(self, t, s, now, traction=_TRACTION_UNSET):
        accel = t["accel"]

        if traction is _TRACTION_UNSET:
            route, effect = self.anim.traction_buzz(t, s, now)
            traction = effect if route == "r2" else None

        # 1. Gear shift thump - brief burst on shift, masks everything below
        if s.enable_gear_shift:
            shift = self.anim.shift_burst(s, now, accel, s.throttle_wall_engage_at)
            if shift:
                return shift

        # 2. Idle buzz - stationary with light throttle
        idle = self.anim.idle_buzz(t, s, now)
        if idle is not None:
            return idle

        # 3. Generic accelerator/both-pedal traction feedback
        if traction is not None:
            return traction

        # 4. Rev limiter buzz - engine state stays below tire-state feedback
        rev = self.anim.rev_buzz(t, s, now)
        if rev is not None:
            return rev

        # 5. Firmware end wall - hard wall near 100% travel (latched via hysteresis)
        self._r2_in_wall = _wall_state(accel, self._r2_in_wall,
                                       s.throttle_wall_engage_at, s.throttle_wall_release_at)
        if self._r2_in_wall:
            return self.wall

        # 6. Throttle resistance - default rigid ramp
        return self.anim.throttle_ramp(t, s)
