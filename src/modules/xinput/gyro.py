"""Steam Input-style DualSense motion conversion for the X360 bridge."""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from ..dualsense.input_state import DualSenseButton, DualSenseInputState


class GyroMode(str, Enum):
    OFF = "off"
    CAMERA = "camera"
    DEFLECTION = "deflection"


class GyroOutputStick(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class GyroActivation(str, Enum):
    ALWAYS = "always"
    L2 = "l2"
    R2 = "r2"
    L1 = "l1"
    R1 = "r1"
    TOUCHPAD = "touchpad"


class GyroHorizontalAxis(str, Enum):
    YAW = "yaw"
    ROLL = "roll"
    YAW_ROLL = "yaw_roll"


@dataclass(frozen=True, slots=True)
class GyroOption:
    key: str
    label: str


GYRO_MODE_OPTIONS = (
    GyroOption(GyroMode.CAMERA.value, "Gyro to Joystick (Camera)"),
    GyroOption(GyroMode.DEFLECTION.value, "Gyro to Joystick (Deflection)"),
)
GYRO_OUTPUT_OPTIONS = (
    GyroOption(GyroOutputStick.LEFT.value, "Left joystick"),
    GyroOption(GyroOutputStick.RIGHT.value, "Right joystick"),
)
GYRO_ACTIVATION_OPTIONS = (
    GyroOption(GyroActivation.ALWAYS.value, "Always on"),
    GyroOption(GyroActivation.L2.value, "L2 soft pull"),
    GyroOption(GyroActivation.R2.value, "R2 soft pull"),
    GyroOption(GyroActivation.L1.value, "L1"),
    GyroOption(GyroActivation.R1.value, "R1"),
    GyroOption(GyroActivation.TOUCHPAD.value, "Touchpad touch"),
)
GYRO_HORIZONTAL_OPTIONS = (
    GyroOption(GyroHorizontalAxis.YAW.value, "Yaw"),
    GyroOption(GyroHorizontalAxis.ROLL.value, "Roll"),
    GyroOption(GyroHorizontalAxis.YAW_ROLL.value, "Yaw + roll"),
)

GYRO_SETTING_FIELDS = frozenset(
    {
        "enable_xinput_gyro",
        "xinput_gyro_mode",
        "xinput_gyro_output_stick",
        "xinput_gyro_activation",
        "xinput_gyro_horizontal_axis",
        "xinput_gyro_sensitivity_dps",
        "xinput_gyro_deflection_angle",
        "xinput_gyro_deadzone_dps",
        "xinput_gyro_smoothing_ms",
        "xinput_gyro_vertical_enabled",
        "xinput_gyro_invert_horizontal",
        "xinput_gyro_invert_vertical",
    }
)


@dataclass(frozen=True, slots=True)
class XInputGyroMapping:
    mode: GyroMode = GyroMode.OFF
    output_stick: GyroOutputStick = GyroOutputStick.LEFT
    activation: GyroActivation = GyroActivation.ALWAYS
    horizontal_axis: GyroHorizontalAxis = GyroHorizontalAxis.ROLL
    sensitivity_dps: float = 180.0
    deflection_angle: float = 30.0
    deadzone_dps: float = 2.0
    smoothing_ms: float = 15.0
    vertical_enabled: bool = False
    invert_horizontal: bool = False
    invert_vertical: bool = False


DEFAULT_GYRO_MAPPING = XInputGyroMapping()
DEFAULT_CONFIGURED_GYRO_MAPPING = XInputGyroMapping(mode=GyroMode.DEFLECTION)


def _enum_value(enum_type, value: object, default):
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value).strip().casefold())
    except ValueError:
        return default


def _finite_range(value: object, default: float, minimum: float, maximum: float) -> float:
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(normalized):
        return default
    return max(minimum, min(maximum, normalized))


def configured_gyro_from_settings(settings) -> XInputGyroMapping:
    mode = _enum_value(
        GyroMode,
        getattr(
            settings,
            "xinput_gyro_mode",
            DEFAULT_CONFIGURED_GYRO_MAPPING.mode,
        ),
        DEFAULT_CONFIGURED_GYRO_MAPPING.mode,
    )
    if mode is GyroMode.OFF:
        mode = DEFAULT_CONFIGURED_GYRO_MAPPING.mode
    return XInputGyroMapping(
        mode=mode,
        output_stick=_enum_value(
            GyroOutputStick,
            getattr(settings, "xinput_gyro_output_stick", GyroOutputStick.LEFT),
            GyroOutputStick.LEFT,
        ),
        activation=_enum_value(
            GyroActivation,
            getattr(settings, "xinput_gyro_activation", GyroActivation.ALWAYS),
            GyroActivation.ALWAYS,
        ),
        horizontal_axis=_enum_value(
            GyroHorizontalAxis,
            getattr(settings, "xinput_gyro_horizontal_axis", GyroHorizontalAxis.ROLL),
            GyroHorizontalAxis.ROLL,
        ),
        sensitivity_dps=_finite_range(
            getattr(settings, "xinput_gyro_sensitivity_dps", 180.0),
            180.0,
            30.0,
            720.0,
        ),
        deflection_angle=_finite_range(
            getattr(settings, "xinput_gyro_deflection_angle", 30.0),
            30.0,
            5.0,
            90.0,
        ),
        deadzone_dps=_finite_range(
            getattr(settings, "xinput_gyro_deadzone_dps", 2.0),
            2.0,
            0.0,
            30.0,
        ),
        smoothing_ms=_finite_range(
            getattr(settings, "xinput_gyro_smoothing_ms", 15.0),
            15.0,
            0.0,
            200.0,
        ),
        vertical_enabled=bool(
            getattr(settings, "xinput_gyro_vertical_enabled", False)
        ),
        invert_horizontal=bool(
            getattr(settings, "xinput_gyro_invert_horizontal", False)
        ),
        invert_vertical=bool(
            getattr(settings, "xinput_gyro_invert_vertical", False)
        ),
    )


def active_gyro_from_settings(settings) -> XInputGyroMapping:
    """Apply gyro only when both the mapping master and gyro child are enabled."""
    if not bool(getattr(settings, "enable_custom_xinput_mapping", False)):
        return DEFAULT_GYRO_MAPPING
    if not bool(getattr(settings, "enable_xinput_gyro", False)):
        return DEFAULT_GYRO_MAPPING
    return configured_gyro_from_settings(settings)


def normalize_gyro_settings(settings) -> bool:
    normalized = configured_gyro_from_settings(settings)
    values = {
        "enable_xinput_gyro": bool(
            getattr(settings, "enable_xinput_gyro", False)
        ),
        "xinput_gyro_mode": normalized.mode.value,
        "xinput_gyro_output_stick": normalized.output_stick.value,
        "xinput_gyro_activation": normalized.activation.value,
        "xinput_gyro_horizontal_axis": normalized.horizontal_axis.value,
        "xinput_gyro_sensitivity_dps": normalized.sensitivity_dps,
        "xinput_gyro_deflection_angle": normalized.deflection_angle,
        "xinput_gyro_deadzone_dps": normalized.deadzone_dps,
        "xinput_gyro_smoothing_ms": normalized.smoothing_ms,
        "xinput_gyro_vertical_enabled": normalized.vertical_enabled,
        "xinput_gyro_invert_horizontal": normalized.invert_horizontal,
        "xinput_gyro_invert_vertical": normalized.invert_vertical,
    }
    changed = False
    for field, value in values.items():
        if getattr(settings, field, None) != value:
            setattr(settings, field, value)
            changed = True
    return changed


def reset_gyro_settings(settings) -> bool:
    defaults = {
        "enable_xinput_gyro": False,
        "xinput_gyro_mode": DEFAULT_CONFIGURED_GYRO_MAPPING.mode.value,
        "xinput_gyro_output_stick": DEFAULT_CONFIGURED_GYRO_MAPPING.output_stick.value,
        "xinput_gyro_activation": DEFAULT_CONFIGURED_GYRO_MAPPING.activation.value,
        "xinput_gyro_horizontal_axis": (
            DEFAULT_CONFIGURED_GYRO_MAPPING.horizontal_axis.value
        ),
        "xinput_gyro_sensitivity_dps": (
            DEFAULT_CONFIGURED_GYRO_MAPPING.sensitivity_dps
        ),
        "xinput_gyro_deflection_angle": (
            DEFAULT_CONFIGURED_GYRO_MAPPING.deflection_angle
        ),
        "xinput_gyro_deadzone_dps": DEFAULT_CONFIGURED_GYRO_MAPPING.deadzone_dps,
        "xinput_gyro_smoothing_ms": DEFAULT_CONFIGURED_GYRO_MAPPING.smoothing_ms,
        "xinput_gyro_vertical_enabled": (
            DEFAULT_CONFIGURED_GYRO_MAPPING.vertical_enabled
        ),
        "xinput_gyro_invert_horizontal": (
            DEFAULT_CONFIGURED_GYRO_MAPPING.invert_horizontal
        ),
        "xinput_gyro_invert_vertical": (
            DEFAULT_CONFIGURED_GYRO_MAPPING.invert_vertical
        ),
    }
    changed = False
    for field, value in defaults.items():
        if getattr(settings, field, None) != value:
            setattr(settings, field, value)
            changed = True
    return changed


def gyro_activation_is_active(
    state: DualSenseInputState,
    mapping: XInputGyroMapping,
) -> bool:
    if state.motion_suppressed:
        return False
    activation = mapping.activation
    if activation is GyroActivation.ALWAYS:
        return True
    if activation is GyroActivation.L2:
        return state.left_trigger >= 8
    if activation is GyroActivation.R2:
        return state.right_trigger >= 8
    if activation is GyroActivation.L1:
        return DualSenseButton.L1 in state.buttons
    if activation is GyroActivation.R1:
        return DualSenseButton.R1 in state.buttons
    return state.touchpad_touched


def gyro_input_is_active(
    state: DualSenseInputState,
    mapping: XInputGyroMapping,
) -> bool:
    if mapping.mode is GyroMode.OFF or not gyro_activation_is_active(state, mapping):
        return False
    threshold = max(5.0, mapping.deadzone_dps)
    return any(abs(rate) >= threshold for rate in state.gyro_degrees_per_second)


def _remove_deadzone(value: float, deadzone: float) -> float:
    magnitude = abs(value)
    if magnitude <= deadzone:
        return 0.0
    return math.copysign(magnitude - deadzone, value)


def _clamp_unit(value: float) -> float:
    return max(-1.0, min(1.0, value))


def _vector_normalize(vector: tuple[float, float, float]) -> tuple[float, float, float] | None:
    magnitude = math.sqrt(sum(component * component for component in vector))
    if not 0.75 <= magnitude <= 1.25:
        return None
    return tuple(component / magnitude for component in vector)


def _relative_gravity_rotation(
    reference: tuple[float, float, float],
    current: tuple[float, float, float],
) -> tuple[float, float, float]:
    cross = (
        reference[1] * current[2] - reference[2] * current[1],
        reference[2] * current[0] - reference[0] * current[2],
        reference[0] * current[1] - reference[1] * current[0],
    )
    sine = math.sqrt(sum(component * component for component in cross))
    cosine = max(-1.0, min(1.0, sum(a * b for a, b in zip(reference, current, strict=True))))
    if sine <= 1e-9:
        return (0.0, 0.0, 0.0)
    scale = -math.degrees(math.atan2(sine, cosine)) / sine
    return tuple(component * scale for component in cross)


class GyroToJoystickProcessor:
    """Convert calibrated IMU samples into additive normalized stick axes."""

    def __init__(self, mapping: XInputGyroMapping = DEFAULT_GYRO_MAPPING):
        self.mapping = mapping
        self.reset()

    def set_mapping(self, mapping: XInputGyroMapping) -> None:
        if mapping != self.mapping:
            self.mapping = mapping
            self.reset()

    def reset(self) -> None:
        self._last_timestamp: int | None = None
        self._last_received_at: float | None = None
        self._active = False
        self._filtered = (0.0, 0.0)
        self._angles = [0.0, 0.0, 0.0]
        self._gravity_reference: tuple[float, float, float] | None = None

    def update(
        self,
        state: DualSenseInputState,
        received_at: float,
    ) -> tuple[float, float]:
        mapping = self.mapping
        if mapping.mode is GyroMode.OFF or not gyro_activation_is_active(state, mapping):
            self.reset()
            return (0.0, 0.0)

        dt = self._sample_delta(state.sensor_timestamp, received_at)
        rates = state.gyro_degrees_per_second
        if not self._active:
            self._active = True
            self._gravity_reference = _vector_normalize(
                tuple(-value for value in state.acceleration_g)
            )
            if mapping.mode is GyroMode.DEFLECTION:
                return (0.0, 0.0)

        if mapping.mode is GyroMode.CAMERA:
            horizontal = self._horizontal_rate(rates)
            vertical = rates[0] if mapping.vertical_enabled else 0.0
            horizontal = _remove_deadzone(horizontal, mapping.deadzone_dps)
            vertical = _remove_deadzone(vertical, mapping.deadzone_dps)
            denominator = max(1.0, mapping.sensitivity_dps - mapping.deadzone_dps)
            output = (horizontal / denominator, vertical / denominator)
        else:
            corrected_rates = tuple(
                _remove_deadzone(rate, mapping.deadzone_dps) for rate in rates
            )
            for index, rate in enumerate(corrected_rates):
                self._angles[index] += rate * dt
            self._correct_angles_from_gravity(state, dt)
            horizontal = self._horizontal_angle()
            vertical = self._angles[0] if mapping.vertical_enabled else 0.0
            output = (
                horizontal / mapping.deflection_angle,
                vertical / mapping.deflection_angle,
            )

        horizontal, vertical = self._smooth(output, dt)
        # DualSense positive yaw/roll is leftward in the player-facing camera
        # convention, while positive pitch already points upward.
        horizontal = -horizontal
        if mapping.invert_horizontal:
            horizontal = -horizontal
        if mapping.invert_vertical:
            vertical = -vertical
        return (_clamp_unit(horizontal), _clamp_unit(vertical))

    def _sample_delta(self, sensor_timestamp: int, received_at: float) -> float:
        dt = 0.004
        if self._last_timestamp is not None and sensor_timestamp:
            ticks = (sensor_timestamp - self._last_timestamp) & 0xFFFFFFFF
            sensor_dt = ticks / 3_000_000.0
            if 0.0001 <= sensor_dt <= 0.05:
                dt = sensor_dt
        elif self._last_received_at is not None:
            host_dt = received_at - self._last_received_at
            if 0.0001 <= host_dt <= 0.05:
                dt = host_dt
        self._last_timestamp = sensor_timestamp
        self._last_received_at = received_at
        return dt

    def _horizontal_rate(self, rates: tuple[float, float, float]) -> float:
        axis = self.mapping.horizontal_axis
        if axis is GyroHorizontalAxis.YAW:
            return rates[1]
        if axis is GyroHorizontalAxis.ROLL:
            return rates[2]
        return (rates[1] + rates[2]) / math.sqrt(2.0)

    def _horizontal_angle(self) -> float:
        axis = self.mapping.horizontal_axis
        if axis is GyroHorizontalAxis.YAW:
            return self._angles[1]
        if axis is GyroHorizontalAxis.ROLL:
            return self._angles[2]
        return (self._angles[1] + self._angles[2]) / math.sqrt(2.0)

    def _correct_angles_from_gravity(
        self,
        state: DualSenseInputState,
        dt: float,
    ) -> None:
        reference = self._gravity_reference
        current = _vector_normalize(
            tuple(-value for value in state.acceleration_g)
        )
        if current is None:
            return
        if reference is None:
            # Initial acceleration may be unusable during movement or startup.
            # Establish the reference once a trustworthy gravity sample arrives.
            self._gravity_reference = current
            return
        estimate = _relative_gravity_rotation(reference, current)
        correction = 1.0 - math.exp(-dt / 1.5)
        for index in range(3):
            observability = 1.0 - reference[index] * reference[index]
            blend = correction * observability
            self._angles[index] += (estimate[index] - self._angles[index]) * blend

    def _smooth(self, output: tuple[float, float], dt: float) -> tuple[float, float]:
        smoothing_s = self.mapping.smoothing_ms / 1000.0
        if smoothing_s <= 0.0:
            self._filtered = output
            return output
        retention = math.exp(-dt / smoothing_s)
        self._filtered = tuple(
            previous * retention + current * (1.0 - retention)
            for previous, current in zip(self._filtered, output, strict=True)
        )
        return self._filtered
