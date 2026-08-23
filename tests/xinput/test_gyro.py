from dataclasses import replace

import pytest

from modules.config.settings import Settings
from modules.dualsense.input_state import DPad, DualSenseButton, DualSenseInputState
from modules.xinput.gyro import (
    DEFAULT_GYRO_MAPPING,
    DEFAULT_CONFIGURED_GYRO_MAPPING,
    GYRO_SETTING_FIELDS,
    GyroActivation,
    GyroHorizontalAxis,
    GyroMode,
    GyroOutputStick,
    GyroToJoystickProcessor,
    XInputGyroMapping,
    active_gyro_from_settings,
    configured_gyro_from_settings,
    gyro_activation_is_active,
    normalize_gyro_settings,
    reset_gyro_settings,
)


def _state(**changes):
    values = {
        "left_x": 128,
        "left_y": 128,
        "right_x": 128,
        "right_y": 128,
        "left_trigger": 0,
        "right_trigger": 0,
        "dpad": DPad.NEUTRAL,
        "buttons": frozenset(),
        "accel_y": 8192,
    }
    values.update(changes)
    return DualSenseInputState(**values)


def test_settings_normalize_strict_enums_and_finite_ranges():
    settings = Settings(
        xinput_gyro_mode="future",
        xinput_gyro_output_stick="RIGHT",
        xinput_gyro_sensitivity_dps=float("inf"),
        xinput_gyro_deflection_angle=-10.0,
        xinput_gyro_deadzone_dps=99.0,
    )

    mapping = configured_gyro_from_settings(settings)
    assert mapping.mode is GyroMode.DEFLECTION
    assert mapping.output_stick is GyroOutputStick.RIGHT
    assert mapping.sensitivity_dps == 180.0
    assert mapping.deflection_angle == 5.0
    assert mapping.deadzone_dps == 30.0

    assert normalize_gyro_settings(settings) is True
    assert settings.xinput_gyro_mode == "deflection"
    assert settings.xinput_gyro_output_stick == "right"
    assert normalize_gyro_settings(settings) is False
    assert GYRO_SETTING_FIELDS


def test_enum_instances_are_accepted_by_programmatic_settings_callers():
    settings = Settings(
        xinput_gyro_mode=GyroMode.CAMERA,
        xinput_gyro_output_stick=GyroOutputStick.RIGHT,
        xinput_gyro_activation=GyroActivation.L2,
        xinput_gyro_horizontal_axis=GyroHorizontalAxis.YAW,
    )

    mapping = configured_gyro_from_settings(settings)

    assert mapping.mode is GyroMode.CAMERA
    assert mapping.output_stick is GyroOutputStick.RIGHT
    assert mapping.activation is GyroActivation.L2
    assert mapping.horizontal_axis is GyroHorizontalAxis.YAW


def test_gyro_requires_mapping_master_and_its_own_child_switch():
    settings = Settings(
        enable_custom_xinput_mapping=False,
        enable_xinput_gyro=True,
        xinput_gyro_mode="camera",
    )

    assert active_gyro_from_settings(settings) == DEFAULT_GYRO_MAPPING

    settings.enable_custom_xinput_mapping = True
    settings.enable_xinput_gyro = False
    assert active_gyro_from_settings(settings) == DEFAULT_GYRO_MAPPING

    settings.enable_xinput_gyro = True
    assert active_gyro_from_settings(settings).mode is GyroMode.CAMERA


def test_reset_motion_mapping_is_idempotent():
    settings = Settings(
        enable_xinput_gyro=True,
        xinput_gyro_mode="camera",
        xinput_gyro_vertical_enabled=True,
    )
    assert reset_gyro_settings(settings) is True
    assert settings.enable_xinput_gyro is False
    assert configured_gyro_from_settings(settings) == DEFAULT_CONFIGURED_GYRO_MAPPING
    assert reset_gyro_settings(settings) is False


@pytest.mark.parametrize(
    ("activation", "state", "expected"),
    (
        (GyroActivation.ALWAYS, _state(), True),
        (GyroActivation.L2, _state(left_trigger=7), False),
        (GyroActivation.L2, _state(left_trigger=8), True),
        (GyroActivation.R2, _state(right_trigger=8), True),
        (GyroActivation.L1, _state(buttons=frozenset({DualSenseButton.L1})), True),
        (GyroActivation.R1, _state(buttons=frozenset({DualSenseButton.R1})), True),
        (GyroActivation.TOUCHPAD, _state(touchpad_touched=True), True),
    ),
)
def test_activation_modes(activation, state, expected):
    mapping = replace(DEFAULT_GYRO_MAPPING, activation=activation)
    assert gyro_activation_is_active(state, mapping) is expected


def test_camera_mode_uses_sensor_rate_deadzone_sensitivity_and_timestamp():
    mapping = XInputGyroMapping(
        mode=GyroMode.CAMERA,
        horizontal_axis=GyroHorizontalAxis.YAW,
        sensitivity_dps=100.0,
        deadzone_dps=0.0,
        smoothing_ms=0.0,
        vertical_enabled=True,
    )
    processor = GyroToJoystickProcessor(mapping)

    output = processor.update(
        _state(gyro_x=800, gyro_y=1600, sensor_timestamp=12_000),
        10.0,
    )

    assert output == pytest.approx((-1.0, 0.5))


def test_camera_mode_supports_roll_and_combined_horizontal_spaces():
    roll = XInputGyroMapping(
        mode=GyroMode.CAMERA,
        horizontal_axis=GyroHorizontalAxis.ROLL,
        sensitivity_dps=100.0,
        deadzone_dps=0.0,
        smoothing_ms=0.0,
    )
    processor = GyroToJoystickProcessor(roll)
    assert processor.update(_state(gyro_z=800), 1.0)[0] == pytest.approx(-0.5)

    processor.set_mapping(replace(roll, horizontal_axis=GyroHorizontalAxis.YAW_ROLL))
    assert processor.update(_state(gyro_y=800, gyro_z=800), 2.0)[0] == pytest.approx(
        -1.0 / 2**0.5
    )


def test_deflection_mode_recenters_on_activation_and_integrates_sensor_time():
    mapping = XInputGyroMapping(
        mode=GyroMode.DEFLECTION,
        horizontal_axis=GyroHorizontalAxis.ROLL,
        deflection_angle=30.0,
        deadzone_dps=0.0,
        smoothing_ms=0.0,
    )
    processor = GyroToJoystickProcessor(mapping)

    assert processor.update(_state(sensor_timestamp=3_000), 1.0) == (0.0, 0.0)
    output = processor.update(
        _state(gyro_z=1600, sensor_timestamp=93_000),
        1.03,
    )
    assert output[0] == pytest.approx(-0.1, abs=0.01)

    processor.set_mapping(replace(mapping, activation=GyroActivation.L2))
    assert processor.update(_state(left_trigger=0), 2.0) == (0.0, 0.0)
    assert processor.update(_state(left_trigger=8, gyro_z=1600), 2.1) == (0.0, 0.0)


def test_deflection_gravity_correction_does_not_follow_linear_acceleration_spikes():
    mapping = XInputGyroMapping(
        mode=GyroMode.DEFLECTION,
        horizontal_axis=GyroHorizontalAxis.ROLL,
        deadzone_dps=0.0,
        smoothing_ms=0.0,
    )
    processor = GyroToJoystickProcessor(mapping)
    processor.update(_state(), 1.0)
    processor.update(_state(gyro_z=1600, sensor_timestamp=300_000), 1.1)
    before = processor._angles[2]

    processor.update(_state(accel_x=32767, accel_y=32767, accel_z=32767), 1.2)
    assert processor._angles[2] == pytest.approx(before)


def test_inversion_and_smoothing_are_applied_after_conversion():
    mapping = XInputGyroMapping(
        mode=GyroMode.CAMERA,
        horizontal_axis=GyroHorizontalAxis.YAW,
        sensitivity_dps=100.0,
        deadzone_dps=0.0,
        smoothing_ms=100.0,
        invert_horizontal=True,
    )
    processor = GyroToJoystickProcessor(mapping)

    output = processor.update(_state(gyro_y=1600), 1.0)
    assert 0.0 < output[0] < 1.0
