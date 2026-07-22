"""Estimate a car's usable rev limit from Forza telemetry.

Forza Data Out exposes dashboard ``max_rpm`` but no explicit rev-limiter flag.
The detector therefore starts with a conservative per-range prediction, then
learns from repeated same-gear power cuts.  Raw telemetry remains untouched;
consumers opt into ``effective_redline_rpm`` added by the main loop.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import median


log = logging.getLogger("fhds.redline")

_THROTTLE_ARM = 200.0
_THROTTLE_CONFIRM = 160.0
_CLUTCH_MAX = 32.0
_MIN_SPEED_KMH = 10.0
_GEAR_STABLE_S = 0.35
_RECENT_WINDOW_S = 0.30
_CUT_CONFIRM_S = 0.12
_CUT_HOLD_S = 0.15
_MIN_EVENT_GAP_S = 0.20
_MIN_POWER_W = 5_000.0
_MAX_SLIP_FOR_LEARNING = 1.5
_CANDIDATES_REQUIRED = 3


def _number(value, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def predict_redline_rpm(max_rpm: float) -> float:
    """Return an empirical fallback when the real fuel cut is not learned yet."""
    max_rpm = max(0.0, _number(max_rpm))
    if max_rpm <= 0.0:
        return 0.0
    ratio = 0.85 + (max_rpm - 5_000.0) * (0.972 - 0.85) / 5_500.0
    ratio = max(0.80, min(0.98, ratio))
    return max_rpm * ratio


@dataclass(frozen=True, slots=True)
class RedlineState:
    effective_rpm: float
    limiter_active: bool
    learned: bool
    confidence: float


@dataclass(frozen=True, slots=True)
class _Sample:
    at: float
    rpm: float
    power: float
    torque: float


@dataclass(frozen=True, slots=True)
class _PendingCut:
    at: float
    gear: int
    rpm: float


class RedlineDetector:
    """Learn a stable rev limit without confusing shifts with fuel cut."""

    def __init__(self) -> None:
        self._identity: tuple[int, int, int] | None = None
        self._learned_rpm: float | None = None
        self._confidence = 0.0
        self._candidates: deque[float] = deque(maxlen=12)
        self._observed_peak = 0.0
        self._gear: int | None = None
        self._gear_since = 0.0
        self._recent: deque[_Sample] = deque(maxlen=24)
        self._armed = False
        self._cut_latched = False
        self._pending: _PendingCut | None = None
        self._last_event_at = -math.inf
        self._limiter_until = 0.0

    def reset_transients(self) -> None:
        """Drop an in-flight event while retaining this car's learned limit."""
        self._gear = None
        self._gear_since = 0.0
        self._recent.clear()
        self._armed = False
        self._cut_latched = False
        self._pending = None
        self._limiter_until = 0.0

    def _reset_learning(self) -> None:
        self._learned_rpm = None
        self._confidence = 0.0
        self._candidates.clear()
        self._observed_peak = 0.0
        self._last_event_at = -math.inf
        self.reset_transients()

    @staticmethod
    def _identity_for(telemetry: Mapping[str, object], max_rpm: float) -> tuple[int, int, int]:
        ordinal = int(_number(telemetry.get("car_ordinal"), -1.0))
        performance_index = int(_number(
            telemetry.get("car_performance_index"), -1.0
        ))
        return (
            ordinal if ordinal > 0 else 0,
            performance_index if performance_index > 0 else 0,
            int(round(max_rpm / 50.0)),
        )

    def _effective_rpm(self, max_rpm: float) -> float:
        predicted = predict_redline_rpm(max_rpm)
        if self._learned_rpm is None:
            # Before learning, do not leave the fallback below RPM the engine
            # has already sustained. This also softens a poor range estimate.
            observed_floor = min(max_rpm, self._observed_peak * 1.003)
            return min(max_rpm, max(predicted, observed_floor))
        if self._observed_peak > self._learned_rpm * 1.03:
            # A confidently observed overshoot means an old or false-low lock
            # must not keep warning permanently below the engine's real range.
            return min(max_rpm, self._observed_peak * 1.003)
        return min(max_rpm, self._learned_rpm)

    @staticmethod
    def _slip(telemetry: Mapping[str, object]) -> float:
        return max(
            abs(_number(telemetry.get(f"{prefix}_{wheel}")))
            for prefix in ("tire_slip_ratio", "tire_combined_slip")
            for wheel in ("fl", "fr", "rl", "rr")
        )

    def _discard_pending_if_invalid(
        self,
        *,
        gear: int,
        accel: float,
        clutch: float,
        speed: float,
        rpm: float,
        slip: float,
    ) -> None:
        pending = self._pending
        if pending is None:
            return
        if (
            gear != pending.gear
            or accel < _THROTTLE_CONFIRM
            or clutch > _CLUTCH_MAX
            or speed < _MIN_SPEED_KMH
            or rpm < pending.rpm * 0.92
            or slip > _MAX_SLIP_FOR_LEARNING
        ):
            self._pending = None

    def _record_candidate(
        self,
        candidate: float,
        predicted: float,
        max_rpm: float,
        idle_rpm: float,
    ) -> None:
        minimum = max(idle_rpm * 2.0, predicted * 0.80)
        if not minimum <= candidate <= max_rpm * 1.01:
            return

        self._candidates.append(candidate)
        tolerance = max(100.0, min(260.0, predicted * 0.025))
        cluster = [
            value for value in self._candidates
            if abs(value - candidate) <= tolerance
        ]
        if len(cluster) < _CANDIDATES_REQUIRED:
            self._confidence = max(
                self._confidence,
                len(cluster) / (_CANDIDATES_REQUIRED + 2.0),
            )
            return

        estimate = float(median(cluster))
        previous = self._learned_rpm
        if previous is None or abs(estimate - previous) > tolerance * 1.5:
            self._learned_rpm = estimate
        else:
            self._learned_rpm = previous * 0.80 + estimate * 0.20
        self._confidence = min(1.0, len(cluster) / 5.0)

        if previous is None or abs(self._learned_rpm - previous) > tolerance:
            log.info(
                "Dynamic redline learned rpm=%.0f samples=%d confidence=%.2f",
                self._learned_rpm,
                len(cluster),
                self._confidence,
            )
        else:
            log.debug(
                "Dynamic redline refined rpm=%.0f samples=%d confidence=%.2f",
                self._learned_rpm,
                len(cluster),
                self._confidence,
            )

    def update(self, telemetry: Mapping[str, object], now: float) -> RedlineState:
        now = _number(now)
        max_rpm = max(0.0, _number(telemetry.get("max_rpm")))
        rpm = max(0.0, _number(telemetry.get("rpm")))
        idle_rpm = max(0.0, _number(telemetry.get("idle_rpm")))

        if max_rpm <= 0.0:
            self.reset_transients()
            return RedlineState(0.0, False, False, 0.0)

        identity = self._identity_for(telemetry, max_rpm)
        has_vehicle_identity = identity[0] > 0 or identity[1] > 0
        identity_is_actionable = (
            self._identity is None
            or has_vehicle_identity
            or (
                self._identity[0] == 0
                and self._identity[1] == 0
                and identity[2] != self._identity[2]
            )
        )
        # Menu packets can temporarily zero ordinal and PI. Ignore that loss
        # instead of erasing a valid learned limit between driving sessions.
        if identity_is_actionable and identity != self._identity:
            self._identity = identity
            self._reset_learning()

        if idle_rpm < rpm <= max_rpm * 1.02:
            self._observed_peak = max(self._observed_peak, rpm)

        predicted = predict_redline_rpm(max_rpm)
        effective = self._effective_rpm(max_rpm)
        if not bool(telemetry.get("on", False)):
            self.reset_transients()
            return RedlineState(
                effective,
                False,
                self._learned_rpm is not None,
                self._confidence,
            )

        gear = int(_number(telemetry.get("gear")))
        accel = max(0.0, _number(telemetry.get("accel")))
        clutch = max(0.0, _number(telemetry.get("clutch")))
        speed = max(0.0, _number(telemetry.get("speed")))
        power = _number(telemetry.get("power"))
        torque = _number(telemetry.get("torque"))
        slip = self._slip(telemetry)

        if gear != self._gear:
            self._gear = gear
            self._gear_since = now
            self._recent.clear()
            self._armed = False
            self._cut_latched = False
            self._pending = None

        valid_gear = gear > 0
        if not valid_gear:
            self.reset_transients()
            return RedlineState(
                effective,
                False,
                self._learned_rpm is not None,
                self._confidence,
            )

        self._discard_pending_if_invalid(
            gear=gear,
            accel=accel,
            clutch=clutch,
            speed=speed,
            rpm=rpm,
            slip=slip,
        )
        if self._pending is not None and now - self._pending.at >= _CUT_CONFIRM_S:
            pending = self._pending
            self._pending = None
            self._record_candidate(pending.rpm, predicted, max_rpm, idle_rpm)
            self._last_event_at = now
            self._limiter_until = now + _CUT_HOLD_S

        self._recent.append(_Sample(now, rpm, power, torque))
        while self._recent and now - self._recent[0].at > _RECENT_WINDOW_S:
            self._recent.popleft()

        gear_stable = now - self._gear_since >= _GEAR_STABLE_S
        arm_ready = (
            gear_stable
            and accel >= _THROTTLE_ARM
            and clutch <= _CLUTCH_MAX
            and speed >= _MIN_SPEED_KMH
            and rpm >= effective * 0.78
            and power >= _MIN_POWER_W
            and slip <= _MAX_SLIP_FOR_LEARNING
        )
        if not self._armed:
            self._armed = arm_ready
        elif (
            accel < _THROTTLE_CONFIRM
            or clutch > _CLUTCH_MAX
            or speed < _MIN_SPEED_KMH
            or slip > _MAX_SLIP_FOR_LEARNING
        ):
            self._armed = False
            self._cut_latched = False

        if self._armed and len(self._recent) >= 2:
            peak_power = max(sample.power for sample in self._recent)
            peak_torque = max(abs(sample.torque) for sample in self._recent)
            peak_rpm = max(sample.rpm for sample in self._recent)
            power_collapsed = (
                peak_power >= _MIN_POWER_W
                and power <= max(1_500.0, peak_power * 0.12)
            )
            torque_collapsed = (
                peak_torque > 0.0
                and abs(torque) <= max(20.0, peak_torque * 0.18)
            )
            rpm_drop = peak_rpm - rpm >= max(60.0, effective * 0.006)
            exact_cut = peak_power >= _MIN_POWER_W and power <= 0.0
            near_limit = peak_rpm >= effective * 0.82
            event_gap = now - self._last_event_at >= _MIN_EVENT_GAP_S

            if (
                self._pending is None
                and not self._cut_latched
                and near_limit
                and event_gap
                and (exact_cut or (power_collapsed and (torque_collapsed or rpm_drop)))
            ):
                self._pending = _PendingCut(now, gear, peak_rpm)
                self._cut_latched = True

            recovery_level = max(2_000.0, peak_power * 0.35)
            if self._cut_latched and power >= recovery_level:
                self._cut_latched = False

        effective = self._effective_rpm(max_rpm)
        return RedlineState(
            effective_rpm=effective,
            limiter_active=now < self._limiter_until,
            learned=self._learned_rpm is not None,
            confidence=self._confidence,
        )
