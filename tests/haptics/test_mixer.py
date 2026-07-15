import math

import pytest

from modules.config.settings import Settings
from modules.haptics.frame import SILENT_FRAME, to_compatible_rumble
from modules.haptics.mixer import HapticMixer


@pytest.fixture
def settings():
    value = Settings()
    value.enable_body_haptics = True
    value.enable_grip_redline_haptics = True
    value.body_haptics_intensity = 1.0
    value.engine_haptics_intensity = 1.0
    value.road_haptics_intensity = 1.0
    value.impact_haptics_intensity = 1.0
    value.slip_haptics_intensity = 1.0
    value.accel_deadzone = 50
    value.abs_min_speed_kmh = 15.0
    return value


def _telemetry(**overrides):
    value = {
        "on": True,
        "max_rpm": 9000.0,
        "idle_rpm": 1000.0,
        "rpm": 1000.0,
        "accel_x": 0.0,
        "accel_z": 0.0,
        "surface_rumble_fl": 0.0,
        "surface_rumble_fr": 0.0,
        "surface_rumble_rl": 0.0,
        "surface_rumble_rr": 0.0,
        "wheel_on_rumble_strip_fl": 0,
        "wheel_on_rumble_strip_fr": 0,
        "wheel_on_rumble_strip_rl": 0,
        "wheel_on_rumble_strip_rr": 0,
        "wheel_in_puddle_fl": 0,
        "wheel_in_puddle_fr": 0,
        "wheel_in_puddle_rl": 0,
        "wheel_in_puddle_rr": 0,
        "tire_combined_slip_fl": 0.0,
        "tire_combined_slip_fr": 0.0,
        "tire_combined_slip_rl": 0.0,
        "tire_combined_slip_rr": 0.0,
        "wheel_rotation_speed_fl": 0.0,
        "wheel_rotation_speed_fr": 0.0,
        "wheel_rotation_speed_rl": 0.0,
        "wheel_rotation_speed_rr": 0.0,
        "drive_train": 2,
        "suspension_travel_meters_fl": 0.0,
        "suspension_travel_meters_fr": 0.0,
        "suspension_travel_meters_rl": 0.0,
        "suspension_travel_meters_rr": 0.0,
        "smashable_vel_diff": 0.0,
        "speed": 50.0,
        "accel": 0,
        "brake": 0,
        "gear": 1,
    }
    value.update(overrides)
    return value


def _stationary_material_frame(settings, rotation, accel=None, **material):
    settings.slip_haptics_intensity = 0.0
    return HapticMixer().update(
        _telemetry(
            speed=0.0,
            rpm=1000.0,
            drive_train=1,
            accel=settings.accel_deadzone if accel is None else accel,
            wheel_rotation_speed_rr=rotation,
            **material,
        ),
        settings,
        now=1.0,
    )


def test_disabled_or_menu_telemetry_is_silent(settings):
    mixer = HapticMixer()
    settings.enable_body_haptics = False
    assert mixer.update(_telemetry(), settings, now=1.0) == SILENT_FRAME

    settings.enable_body_haptics = True
    assert mixer.update(_telemetry(on=False), settings, now=2.0) == SILENT_FRAME


def test_engine_maps_idle_to_redline_frequency(settings):
    mixer = HapticMixer()
    idle = mixer.update(_telemetry(), settings, now=1.0)
    redline = mixer.update(_telemetry(rpm=9000.0, accel=255), settings, now=2.0)

    assert idle.engine_hz == 40.0
    assert redline.engine_hz == 120.0
    assert redline.engine_amplitude > idle.engine_amplitude


def _redline_frame(settings, mixer, now, **telemetry):
    settings.road_haptics_intensity = 0.0
    settings.impact_haptics_intensity = 0.0
    settings.slip_haptics_intensity = 0.0
    values = {"rpm": 9000.0, "accel": 255}
    values.update(telemetry)
    return mixer.update(
        _telemetry(**values),
        settings,
        now=now,
    )


def test_redline_grip_warning_starts_immediately_on_left_by_default(settings):
    mixer = HapticMixer()

    frame = _redline_frame(settings, mixer, now=1.0)

    base = settings.grip_redline_amp / 255.0
    event = min(1.0, 1.0 - (1.0 - base) ** settings.grip_redline_gain
                + settings.grip_redline_attack_strength * 0.25)
    assert frame.left_high == pytest.approx(event)
    assert frame.left_low == pytest.approx(min(
        1.0,
        event * settings.grip_redline_low_ratio
        + settings.grip_redline_attack_strength * 0.55,
    ))
    assert frame.right_high == 0.0
    assert frame.right_low == 0.0
    assert frame.engine_amplitude > 0.0


@pytest.mark.parametrize(
    ("left", "right", "expected_left", "expected_right"),
    [
        (True, False, True, False),
        (False, True, False, True),
        (True, True, True, True),
        (False, False, False, False),
    ],
    ids=("left-only", "right-only", "both", "neither"),
)
def test_redline_grip_warning_routes_to_selected_sides(
    settings, left, right, expected_left, expected_right
):
    settings.grip_redline_left = left
    settings.grip_redline_right = right

    frame = _redline_frame(settings, HapticMixer(), now=1.0)

    assert (frame.left_high > 0.0) is expected_left
    assert (frame.right_high > 0.0) is expected_right
    if expected_left and expected_right:
        assert frame.left_high == pytest.approx(frame.right_high)


def test_redline_grip_warning_uses_configurable_fuel_cut_pulse_width(settings):
    mixer = HapticMixer()
    settings.grip_redline_attack_strength = 0.0

    onset = _redline_frame(settings, mixer, now=1.0)
    still_on = _redline_frame(settings, mixer, now=1.069)
    off_half = _redline_frame(settings, mixer, now=1.070)
    next_cycle = _redline_frame(settings, mixer, now=1.100)

    assert onset.left_high > 0.0
    assert still_on.left_high == pytest.approx(onset.left_high)
    assert off_half.left_high == 0.0
    assert next_cycle.left_high == pytest.approx(onset.left_high)


def test_redline_grip_gain_uses_perceptual_curve_without_early_saturation(settings):
    settings.body_haptics_intensity = 0.5
    settings.engine_haptics_intensity = 0.5
    settings.grip_redline_amp = 100
    settings.grip_redline_attack_strength = 0.0
    settings.grip_redline_gain = 1.0
    baseline = _redline_frame(settings, HapticMixer(), now=1.0)

    settings.grip_redline_gain = 1.5
    boosted = _redline_frame(settings, HapticMixer(), now=1.0)

    base = settings.grip_redline_amp / 255.0
    expected = (1.0 - (1.0 - base) ** 1.5) * 0.5 * 0.5
    assert boosted.left_high == pytest.approx(expected)
    assert boosted.left_high > baseline.left_high
    assert boosted.left_high < baseline.left_high * 1.5
    assert boosted.left_low > baseline.left_low


def test_redline_grip_gain_is_safely_clamped_at_final_output(settings):
    settings.grip_redline_amp = 255
    settings.grip_redline_gain = 2.0

    frame = _redline_frame(settings, HapticMixer(), now=1.0)

    assert frame.left_high == 1.0
    assert frame.left_low <= 1.0


def test_redline_grip_warning_uses_rpm_hysteresis_while_throttle_is_held(settings):
    mixer = HapticMixer()
    _redline_frame(settings, mixer, now=1.0)

    held = _redline_frame(
        settings,
        mixer,
        now=1.10,
        rpm=(settings.grip_redline_release_ratio + 0.01) * 9000.0,
    )
    expired = _redline_frame(
        settings,
        mixer,
        now=1.20,
        rpm=(settings.grip_redline_release_ratio - 0.001) * 9000.0,
    )

    assert held.left_high > 0.0
    assert expired.left_high == 0.0
    assert expired.right_high == 0.0


def test_redline_grip_warning_clears_immediately_when_throttle_is_released(settings):
    mixer = HapticMixer()
    assert _redline_frame(settings, mixer, now=1.0).left_high > 0.0

    frame = _redline_frame(settings, mixer, now=1.01, accel=0)

    assert frame.left_low == 0.0
    assert frame.left_high == 0.0
    assert mixer._redline_active is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: setattr(value, "enable_grip_redline_haptics", False),
        lambda value: setattr(value, "engine_haptics_intensity", 0.0),
        lambda value: setattr(value, "body_haptics_intensity", 0.0),
    ],
    ids=("redline-disabled", "engine-haptics-muted", "body-haptics-muted"),
)
def test_redline_grip_warning_obeys_all_haptics_gates(settings, mutate):
    mutate(settings)

    frame = _redline_frame(settings, HapticMixer(), now=1.0)

    assert frame.left_high == 0.0
    assert frame.right_high == 0.0


def test_disabling_redline_warning_clears_an_existing_hold(settings):
    mixer = HapticMixer()
    assert _redline_frame(settings, mixer, now=1.0).left_high > 0.0

    settings.enable_grip_redline_haptics = False
    frame = _redline_frame(settings, mixer, now=1.01, rpm=1000.0)

    assert frame.left_high == 0.0
    assert frame.right_high == 0.0
    assert mixer._redline_active is False


def test_redline_grip_warning_requires_accelerator_and_rpm_threshold(settings):
    mixer = HapticMixer()
    settings.road_haptics_intensity = 0.0

    no_accel = mixer.update(
        _telemetry(rpm=9000.0, accel=settings.accel_deadzone - 1),
        settings,
        now=1.0,
    )
    below_redline = mixer.update(
        _telemetry(
            rpm=settings.grip_redline_ratio * 9000.0 - 1.0,
            accel=255,
        ),
        settings,
        now=2.0,
    )

    assert no_accel.left_high == no_accel.right_high == 0.0
    assert below_redline.left_high == below_redline.right_high == 0.0


def test_redline_ducks_continuous_background_but_not_transients(settings):
    reference = Settings()
    reference.enable_body_haptics = True
    reference.body_haptics_intensity = 1.0
    reference.engine_haptics_intensity = 1.0
    reference.road_haptics_intensity = 1.0
    reference.impact_haptics_intensity = 1.0
    reference.slip_haptics_intensity = 0.0
    reference.accel_deadzone = settings.accel_deadzone
    reference.enable_grip_redline_haptics = False
    telemetry = _telemetry(
        rpm=9000.0,
        accel=255,
        surface_rumble_rr=0.4,
    )

    baseline = HapticMixer().update(telemetry, reference, now=1.0)
    active = HapticMixer().update(telemetry, settings, now=1.0)

    assert active.right_low == pytest.approx(
        baseline.right_low * settings.grip_redline_background_duck
    )
    assert active.right_high == pytest.approx(
        baseline.right_high * settings.grip_redline_background_duck
    )
    assert active.engine_amplitude == pytest.approx(
        baseline.engine_amplitude * settings.grip_redline_background_duck
    )

    reference_mixer = HapticMixer()
    active_mixer = HapticMixer()
    reference_mixer.update(_telemetry(gear=2, rpm=9000.0, accel=255), reference, 2.0)
    active_mixer.update(_telemetry(gear=2, rpm=9000.0, accel=255), settings, 2.0)
    reference_shift = reference_mixer.update(
        _telemetry(gear=3, rpm=9000.0, accel=255), reference, 2.01
    )
    active_shift = active_mixer.update(
        _telemetry(gear=3, rpm=9000.0, accel=255), settings, 2.01
    )

    assert active_shift.right_low == pytest.approx(reference_shift.right_low)


def test_redline_logs_only_state_edges(settings, caplog):
    mixer = HapticMixer()

    with caplog.at_level("INFO", logger="fhds.haptics"):
        _redline_frame(settings, mixer, now=1.0)
        _redline_frame(settings, mixer, now=1.01)
        _redline_frame(settings, mixer, now=1.02, accel=0)

    entered = [record for record in caplog.records if "Grip redline entered" in record.message]
    exited = [record for record in caplog.records if "Grip redline exited" in record.message]
    assert len(entered) == 1
    assert len(exited) == 1
    assert "sides=left" in entered[0].message
    assert "reason=throttle" in exited[0].message


@pytest.mark.parametrize(
    ("left", "right", "motor"),
    [(True, False, "low"), (False, True, "high")],
    ids=("left-motor", "right-motor"),
)
def test_usb_and_bluetooth_share_redline_event_with_side_projection(
    settings, left, right, motor
):
    settings.grip_redline_amp = 100
    settings.grip_redline_attack_strength = 0.0
    settings.grip_redline_left = left
    settings.grip_redline_right = right
    mixer = HapticMixer()
    on = _redline_frame(settings, mixer, now=1.0)
    off = _redline_frame(settings, mixer, now=1.071)
    on_rumble = to_compatible_rumble(on)
    off_rumble = to_compatible_rumble(off)
    base = settings.grip_redline_amp / 255.0
    event = 1.0 - (1.0 - base) ** settings.grip_redline_gain

    if motor == "low":
        assert on.left_high == pytest.approx(event)
        assert on.right_high == 0.0
        assert on_rumble.low_frequency - off_rumble.low_frequency == pytest.approx(event)
        assert on_rumble.high_frequency == pytest.approx(off_rumble.high_frequency)
    else:
        assert on.right_high == pytest.approx(event)
        assert on.left_high == 0.0
        assert on_rumble.high_frequency - off_rumble.high_frequency == pytest.approx(event)
        assert on_rumble.low_frequency == pytest.approx(off_rumble.low_frequency)


def test_true_stationary_idle_is_silent(settings):
    frame = HapticMixer().update(
        _telemetry(speed=0.0, rpm=1000.0, idle_rpm=1000.0, accel=0),
        settings,
        now=1.0,
    )

    assert frame == SILENT_FRAME


def test_stationary_revving_produces_engine_only(settings):
    frame = HapticMixer().update(
        _telemetry(
            speed=0.0,
            rpm=7000.0,
            accel=220,
            surface_rumble_fl=1.0,
            wheel_on_rumble_strip_fr=1,
            wheel_in_puddle_rr=1.0,
        ),
        settings,
        now=1.0,
    )

    assert frame.engine_hz > 40.0
    assert frame.engine_amplitude > 0.0
    assert frame.left_low == 0.0
    assert frame.left_high == 0.0
    assert frame.right_low == 0.0
    assert frame.right_high == 0.0


def test_stationary_burnout_uses_only_driven_wheel_rotation(settings):
    mixer = HapticMixer()
    front_noise = mixer.update(
        _telemetry(
            speed=0.0,
            drive_train=1,
            accel=255,
            rpm=7000.0,
            wheel_rotation_speed_fl=120.0,
            tire_combined_slip_fl=9.0,
        ),
        settings,
        now=1.0,
    )
    rear_spin = mixer.update(
        _telemetry(
            speed=0.0,
            drive_train=1,
            accel=255,
            rpm=7000.0,
            wheel_rotation_speed_rr=120.0,
        ),
        settings,
        now=1.1,
    )

    assert front_noise.left_low == 0.0
    assert front_noise.right_low == 0.0
    assert rear_spin.right_low > rear_spin.left_low


def test_stationary_burnout_keeps_material_signatures(settings):
    common = dict(
        speed=0.0,
        drive_train=1,
        accel=255,
        rpm=7000.0,
        wheel_rotation_speed_rr=120.0,
    )
    tarmac = HapticMixer().update(_telemetry(**common), settings, now=1.0)
    dirt = HapticMixer().update(
        _telemetry(**common, surface_rumble_rr=0.2), settings, now=1.0
    )
    gravel = HapticMixer().update(
        _telemetry(**common, surface_rumble_rr=0.4), settings, now=1.0
    )
    water = HapticMixer().update(
        _telemetry(**common, wheel_in_puddle_rr=1.0), settings, now=1.0
    )

    assert dirt.right_high > tarmac.right_high
    assert gravel.right_high > dirt.right_high
    assert gravel.right_low > dirt.right_low > tarmac.right_low
    assert water.right_high > tarmac.right_high
    assert water.right_low > tarmac.right_low
    assert len({tarmac, dirt, gravel, water}) == 4


def test_stationary_surface_excitation_follows_wheel_rotation_ramp(settings):
    def right_high(rotation):
        return _stationary_material_frame(
            settings,
            rotation,
            surface_rumble_rr=0.4,
        ).right_high

    full_strength = right_high(120.0)

    assert right_high(29.99) == 0.0
    assert right_high(30.0) == 0.0
    assert right_high(30.09) == pytest.approx(full_strength * 0.001)
    assert right_high(75.0) == pytest.approx(full_strength * 0.5)
    assert full_strength == pytest.approx(0.3)


def test_stationary_material_excitation_respects_accelerator_deadzone(settings):
    below = _stationary_material_frame(
        settings,
        120.0,
        accel=settings.accel_deadzone - 1,
        surface_rumble_rr=0.4,
    )
    boundary = _stationary_material_frame(
        settings,
        120.0,
        accel=settings.accel_deadzone,
        surface_rumble_rr=0.4,
    )

    assert below.right_high == 0.0
    assert boundary.right_high == pytest.approx(0.3)


@pytest.mark.parametrize(
    ("material", "low_at_full", "high_at_full"),
    [
        ({"surface_rumble_rr": 0.4}, 0.18, 0.30),
        ({"wheel_on_rumble_strip_rr": 1}, 0.0, 0.35),
        ({"wheel_in_puddle_rr": 1.0}, 0.60, 0.30),
    ],
    ids=("surface", "rumble-strip", "puddle"),
)
def test_stationary_contact_sources_scale_with_wheel_excitation(
    settings,
    material,
    low_at_full,
    high_at_full,
):
    half = _stationary_material_frame(settings, 75.0, **material)
    full = _stationary_material_frame(settings, 120.0, **material)

    assert half.right_low == pytest.approx(low_at_full * 0.5)
    assert half.right_high == pytest.approx(high_at_full * 0.5)
    assert full.right_low == pytest.approx(low_at_full)
    assert full.right_high == pytest.approx(high_at_full)


def test_stationary_stale_contact_telemetry_is_silent(settings):
    frame = HapticMixer().update(
        _telemetry(
            speed=0.0,
            accel=0,
            rpm=1000.0,
            surface_rumble_fl=1.0,
            wheel_on_rumble_strip_fr=1,
            wheel_in_puddle_rl=1.0,
            tire_combined_slip_rr=9.0,
        ),
        settings,
        now=1.0,
    )

    assert frame == SILENT_FRAME


def test_stationary_collision_remains_directional(settings):
    mixer = HapticMixer()
    mixer.update(_telemetry(speed=0.0, rpm=1000.0), settings, now=1.0)
    frame = mixer.update(
        _telemetry(speed=0.0, rpm=1000.0, accel_x=10.0), settings, now=1.01
    )

    assert frame.left_low > frame.right_low > 0.0
    assert frame.engine_amplitude == 0.0


def test_stationary_suspension_thud_remains_directional(settings):
    mixer = HapticMixer()
    mixer.update(
        _telemetry(speed=0.0, rpm=1000.0, suspension_travel_meters_fl=0.10),
        settings,
        now=1.0,
    )
    frame = mixer.update(
        _telemetry(speed=0.0, rpm=1000.0, suspension_travel_meters_fl=0.08),
        settings,
        now=1.02,
    )

    assert frame.left_low > frame.right_low
    assert frame.engine_amplitude == 0.0


def test_rolling_hysteresis_prevents_zero_speed_chatter(settings):
    mixer = HapticMixer()
    assert mixer.update(
        _telemetry(speed=0.3, rpm=1000.0, surface_rumble_fl=0.6),
        settings,
        now=1.0,
    ) == SILENT_FRAME

    started = mixer.update(
        _telemetry(speed=0.5, surface_rumble_fl=0.6), settings, now=1.1
    )
    held = mixer.update(
        _telemetry(speed=0.3, surface_rumble_fl=0.6), settings, now=1.2
    )
    stopped = mixer.update(
        _telemetry(speed=0.2, rpm=1000.0, surface_rumble_fl=0.6),
        settings,
        now=1.3,
    )

    assert started.left_high > 0.0
    assert held.left_high > 0.0
    assert stopped == SILENT_FRAME


def test_road_and_puddle_energy_stays_on_matching_side(settings):
    frame = HapticMixer().update(
        _telemetry(surface_rumble_fl=0.6, wheel_in_puddle_fl=1),
        settings,
        now=1.0,
    )

    assert frame.left_high > frame.right_high
    assert frame.left_low > frame.right_low


def test_rumble_strip_is_directional(settings):
    frame = HapticMixer().update(
        _telemetry(wheel_on_rumble_strip_fr=1),
        settings,
        now=1.0,
    )

    assert frame.right_high > frame.left_high


def test_asphalt_hum_increases_with_speed(settings):
    mixer = HapticMixer()
    stopped = mixer.update(_telemetry(speed=0.0), settings, now=1.0)
    moving = mixer.update(_telemetry(speed=200.0), settings, now=2.0)

    assert moving.left_high > stopped.left_high
    assert moving.right_high > stopped.right_high


def test_suspension_compression_creates_left_thud(settings):
    mixer = HapticMixer()
    mixer.update(_telemetry(suspension_travel_meters_fl=0.10), settings, now=1.0)
    frame = mixer.update(_telemetry(suspension_travel_meters_fl=0.08), settings, now=1.02)

    assert frame.left_low > frame.right_low


def test_slip_and_abs_are_clamped(settings):
    frame = HapticMixer().update(
        _telemetry(tire_combined_slip_rr=9.0, brake=255),
        settings,
        now=2.0,
    )

    assert 0.0 < frame.left_low <= 1.0
    assert 0.0 < frame.right_low <= 1.0


def test_abs_requires_configured_minimum_speed(settings):
    mixer = HapticMixer()
    stopped = mixer.update(
        _telemetry(
            speed=0.0,
            rpm=1000.0,
            brake=255,
            tire_combined_slip_fl=9.0,
        ),
        settings,
        now=2.0,
    )
    moving = mixer.update(
        _telemetry(
            speed=settings.abs_min_speed_kmh,
            brake=255,
            tire_combined_slip_fl=9.0,
        ),
        settings,
        now=2.0,
    )

    assert stopped == SILENT_FRAME
    assert moving.left_low > 0.0
    assert moving.right_low > 0.0


@pytest.mark.parametrize(
    ("brake", "speed", "combined_slip", "expected_low"),
    [
        (122.0, 37.5, 2.26, 0.0),
        (123.0, 37.5, 2.26, 0.5),
        (124.0, 37.5, 2.26, 0.5),
        (123.0, 37.49, 2.26, 0.0),
        (123.0, 37.5, 2.26, 0.5),
        (123.0, 38.0, 2.26, 0.5),
        (123.0, 37.5, 2.24, 0.0),
        (123.0, 37.5, 2.25, 0.0),
        (123.0, 37.5, 2.26, 0.5),
    ],
    ids=(
        "brake-below",
        "brake-boundary",
        "brake-above",
        "speed-below",
        "speed-boundary",
        "speed-above",
        "slip-below",
        "slip-boundary",
        "slip-above",
    ),
)
def test_abs_honors_custom_threshold_boundaries(
    settings,
    brake,
    speed,
    combined_slip,
    expected_low,
):
    settings.abs_brake_threshold = 123.0
    settings.abs_min_speed_kmh = 37.5
    settings.abs_combined_slip_threshold = 2.25
    settings.slip_haptics_threshold = 100.0

    frame = HapticMixer().update(
        _telemetry(
            brake=brake,
            speed=speed,
            tire_combined_slip_fl=combined_slip,
        ),
        settings,
        now=2.0,
    )

    assert frame.left_low == pytest.approx(expected_low)
    assert frame.right_low == pytest.approx(expected_low)


def test_collision_jerk_is_directional_and_persists(settings):
    mixer = HapticMixer()
    mixer.update(_telemetry(), settings, now=1.0)
    impact = mixer.update(_telemetry(accel_x=10.0), settings, now=1.01)
    held = mixer.update(_telemetry(accel_x=10.0), settings, now=1.05)

    assert impact.left_low > impact.right_low > 0.0
    assert held.left_low > held.right_low > 0.0


def test_smashable_velocity_arms_a_centered_impact(settings):
    frame = HapticMixer().update(
        _telemetry(smashable_vel_diff=9.0),
        settings,
        now=1.0,
    )

    assert frame.left_low == pytest.approx(frame.right_low)
    assert frame.left_low > 0.0


@pytest.mark.parametrize(
    ("telemetry", "source"),
    [
        ({"accel_x": 10.0}, "jerk"),
        ({"smashable_vel_diff": 9.0}, "smashable"),
        ({"accel_x": 10.0, "smashable_vel_diff": 9.0}, "both"),
    ],
    ids=("jerk", "smashable", "both"),
)
def test_collision_logs_one_arm_with_detector_source(settings, caplog, telemetry, source):
    mixer = HapticMixer()
    mixer.update(_telemetry(speed=0.0, rpm=1000.0), settings, now=1.0)

    with caplog.at_level("INFO", logger="fhds.haptics"):
        mixer.update(
            _telemetry(speed=0.0, rpm=1000.0, **telemetry),
            settings,
            now=1.01,
        )

    armed = [record for record in caplog.records if "Collision armed" in record.message]
    assert len(armed) == 1
    assert f"source={source}" in armed[0].message
    assert "intensity=" in armed[0].message
    assert "direction=" in armed[0].message


def test_collision_requires_signal_release_and_cooldown_before_rearming(settings, caplog):
    mixer = HapticMixer()

    with caplog.at_level("INFO", logger="fhds.haptics"):
        mixer.update(_telemetry(smashable_vel_diff=9.0), settings, now=1.0)
        mixer.update(_telemetry(smashable_vel_diff=9.0), settings, now=1.16)
        mixer.update(_telemetry(smashable_vel_diff=9.0), settings, now=1.30)
        mixer.update(_telemetry(smashable_vel_diff=0.0), settings, now=1.31)
        mixer.update(_telemetry(smashable_vel_diff=9.0), settings, now=1.32)

    armed = [record for record in caplog.records if "Collision armed" in record.message]
    assert len(armed) == 2


def test_body_haptics_reset_reestablishes_collision_acceleration_baseline(settings):
    mixer = HapticMixer()
    mixer.update(
        _telemetry(speed=0.0, rpm=1000.0, accel_x=0.0), settings, now=1.0
    )
    settings.enable_body_haptics = False
    mixer.update(
        _telemetry(speed=0.0, rpm=1000.0, accel_x=10.0), settings, now=1.1
    )
    settings.enable_body_haptics = True

    frame = mixer.update(
        _telemetry(speed=0.0, rpm=1000.0, accel_x=10.0), settings, now=1.2
    )

    assert frame == SILENT_FRAME


def test_collision_uses_main_gap_rebound_and_release_envelope(settings):
    mixer = HapticMixer()
    telemetry = _telemetry(
        speed=0.0,
        rpm=1000.0,
        smashable_vel_diff=15.0,
    )

    main = mixer.update(telemetry, settings, now=1.0)
    gap = mixer.update(telemetry, settings, now=1.050)
    rebound = mixer.update(telemetry, settings, now=1.070)
    release = mixer.update(telemetry, settings, now=1.140)
    ended = mixer.update(telemetry, settings, now=1.151)

    assert main.left_low == pytest.approx(main.right_low)
    assert main.left_high == pytest.approx(main.right_high)
    assert main.left_low > main.left_high > 0.0
    assert gap.left_low == gap.left_high == 0.0
    assert 0.0 < rebound.left_low < main.left_low
    assert 0.0 < rebound.left_high < rebound.left_low
    assert 0.0 < release.left_low < rebound.left_low
    assert ended.left_low == ended.left_high == 0.0


def test_collision_direction_keeps_thirty_five_percent_on_weak_side(settings):
    mixer = HapticMixer()
    mixer.update(_telemetry(speed=0.0, rpm=1000.0), settings, now=1.0)

    frame = mixer.update(
        _telemetry(
            speed=0.0,
            rpm=1000.0,
            accel_x=10.0,
            smashable_vel_diff=15.0,
        ),
        settings,
        now=1.01,
    )

    assert frame.right_low == pytest.approx(
        frame.left_low * settings.collision_haptics_weak_side_ratio
    )


def test_collision_gap_ducks_all_non_collision_haptics(settings):
    settings.enable_grip_redline_haptics = False
    telemetry = dict(
        speed=50.0,
        rpm=7000.0,
        accel=200,
        surface_rumble_rr=0.4,
    )
    reference = HapticMixer()
    collision = HapticMixer()
    reference.update(_telemetry(gear=2, **telemetry), settings, now=1.0)
    collision.update(_telemetry(gear=2, **telemetry), settings, now=1.0)
    reference.update(_telemetry(gear=3, **telemetry), settings, now=1.01)
    collision.update(
        _telemetry(gear=3, smashable_vel_diff=15.0, **telemetry),
        settings,
        now=1.01,
    )

    normal = reference.update(_telemetry(gear=3, **telemetry), settings, now=1.06)
    ducked = collision.update(
        _telemetry(gear=3, smashable_vel_diff=15.0, **telemetry),
        settings,
        now=1.06,
    )

    factor = settings.collision_background_duck
    assert ducked.left_low == pytest.approx(normal.left_low * factor)
    assert ducked.left_high == pytest.approx(normal.left_high * factor)
    assert ducked.right_low == pytest.approx(normal.right_low * factor)
    assert ducked.right_high == pytest.approx(normal.right_high * factor)
    assert ducked.engine_amplitude == pytest.approx(normal.engine_amplitude * factor)


def test_redline_resumes_after_collision_priority_window(settings):
    mixer = HapticMixer()
    mixer.update(
        _telemetry(speed=0.0, rpm=9000.0, accel=255, smashable_vel_diff=15.0),
        settings,
        now=1.0,
    )

    resumed = mixer.update(
        _telemetry(speed=0.0, rpm=9000.0, accel=255, smashable_vel_diff=0.0),
        settings,
        now=1.201,
    )

    base = settings.grip_redline_amp / 255.0
    expected = 1.0 - (1.0 - base) ** settings.grip_redline_gain
    assert resumed.left_high == pytest.approx(expected)
    assert resumed.right_high == 0.0


@pytest.mark.parametrize(
    ("accel_x", "strong_motor"),
    [(10.0, "low"), (-10.0, "high")],
    ids=("left-impact", "right-impact"),
)
def test_bluetooth_collision_projection_preserves_direction(
    settings, accel_x, strong_motor
):
    mixer = HapticMixer()
    mixer.update(_telemetry(speed=0.0, rpm=1000.0), settings, now=1.0)
    frame = mixer.update(
        _telemetry(
            speed=0.0,
            rpm=1000.0,
            accel_x=accel_x,
            smashable_vel_diff=15.0,
        ),
        settings,
        now=1.01,
    )
    rumble = to_compatible_rumble(frame)

    if strong_motor == "low":
        assert rumble.high_frequency == pytest.approx(
            rumble.low_frequency * settings.collision_haptics_weak_side_ratio
        )
    else:
        assert rumble.low_frequency == pytest.approx(
            rumble.high_frequency * settings.collision_haptics_weak_side_ratio
        )


def test_gear_change_is_silent_when_grip_shift_is_disabled(settings):
    mixer = HapticMixer()
    mixer.update(_telemetry(gear=2, speed=50.0), settings, now=1.0)
    frame = mixer.update(_telemetry(gear=3, speed=50.0), settings, now=1.01)

    assert frame.left_low == 0.0
    assert frame.right_low == 0.0


def test_enabled_grip_gear_change_creates_configured_centered_kick(settings):
    settings.enable_grip_gear_shift_haptics = True
    settings.grip_gear_shift_strength = 0.55
    mixer = HapticMixer()
    mixer.update(_telemetry(gear=2, speed=50.0), settings, now=1.0)
    frame = mixer.update(_telemetry(gear=3, speed=50.0), settings, now=1.01)

    assert frame.left_low == pytest.approx(0.55)
    assert frame.right_low == pytest.approx(0.55)


@pytest.mark.parametrize(
    ("previous", "current", "speed"),
    [(0, 1, 50.0), (1, 0, 50.0), (2, 3, 3.0)],
    ids=("from-neutral", "to-neutral", "speed-gate"),
)
def test_grip_gear_shift_requires_positive_gears_and_speed(
    settings, previous, current, speed
):
    settings.enable_grip_gear_shift_haptics = True
    mixer = HapticMixer()
    mixer.update(_telemetry(gear=previous, speed=speed), settings, now=1.0)

    frame = mixer.update(_telemetry(gear=current, speed=speed), settings, now=1.01)

    assert frame.left_low == 0.0
    assert frame.right_low == 0.0


def test_grip_gear_shift_uses_independent_duration_and_intensity(settings):
    settings.enable_grip_gear_shift_haptics = True
    settings.grip_gear_shift_strength = 0.2
    settings.grip_gear_shift_duration_ms = 40.0
    settings.impact_haptics_intensity = 1.5
    settings.body_haptics_intensity = 0.5
    mixer = HapticMixer()
    mixer.update(_telemetry(gear=2, speed=50.0), settings, now=1.0)

    active = mixer.update(_telemetry(gear=3, speed=50.0), settings, now=1.01)
    ended = mixer.update(_telemetry(gear=3, speed=50.0), settings, now=1.051)

    assert active.left_low == pytest.approx(0.15)
    assert active.right_low == pytest.approx(0.15)
    assert ended.left_low == 0.0
    assert ended.right_low == 0.0


def test_grip_and_trigger_shift_settings_are_independent(settings):
    settings.enable_grip_gear_shift_haptics = True
    settings.enable_gear_shift = False
    settings.enable_gear_shift_brake = False
    settings.gear_shift_amp = 255
    settings.gear_shift_duration_ms = 2000.0
    settings.grip_gear_shift_strength = 0.3
    settings.grip_gear_shift_duration_ms = 20.0
    mixer = HapticMixer()
    mixer.update(_telemetry(gear=2, speed=50.0), settings, now=1.0)

    active = mixer.update(_telemetry(gear=3, speed=50.0), settings, now=1.01)
    ended = mixer.update(_telemetry(gear=3, speed=50.0), settings, now=1.031)

    assert active.left_low == pytest.approx(0.3)
    assert active.right_low == pytest.approx(0.3)
    assert ended.left_low == 0.0
    assert ended.right_low == 0.0


def test_disabling_grip_shift_clears_active_event_and_tracks_gears(settings):
    settings.enable_grip_gear_shift_haptics = True
    mixer = HapticMixer()
    mixer.update(_telemetry(gear=2, speed=50.0), settings, now=1.0)
    assert mixer.update(
        _telemetry(gear=3, speed=50.0), settings, now=1.01
    ).left_low > 0.0

    settings.enable_grip_gear_shift_haptics = False
    disabled = mixer.update(_telemetry(gear=4, speed=50.0), settings, now=1.02)
    settings.enable_grip_gear_shift_haptics = True
    reenabled = mixer.update(_telemetry(gear=4, speed=50.0), settings, now=1.03)

    assert disabled.left_low == disabled.right_low == 0.0
    assert reenabled.left_low == reenabled.right_low == 0.0


def test_menu_reset_prevents_stale_suspension_and_gear_events(settings):
    mixer = HapticMixer()
    mixer.update(
        _telemetry(gear=2, speed=50.0, suspension_travel_meters_fl=0.10),
        settings,
        now=1.0,
    )
    mixer.update(_telemetry(on=False), settings, now=1.1)
    frame = mixer.update(
        _telemetry(gear=3, speed=50.0, suspension_travel_meters_fl=0.08),
        settings,
        now=1.2,
    )

    assert frame.left_low == 0.0
    assert frame.right_low == 0.0


def test_non_finite_telemetry_never_escapes(settings):
    bad = float("nan")
    frame = HapticMixer().update(
        _telemetry(
            rpm=bad,
            accel_x=bad,
            accel_z=bad,
            surface_rumble_fl=bad,
            tire_combined_slip_fl=bad,
            suspension_travel_meters_fl=bad,
            smashable_vel_diff=bad,
        ),
        settings,
        now=1.0,
    )

    assert all(math.isfinite(value) for value in (
        frame.left_low,
        frame.left_high,
        frame.right_low,
        frame.right_high,
        frame.engine_hz,
        frame.engine_amplitude,
    ))


def test_master_intensity_zero_mutes_every_amplitude(settings):
    settings.body_haptics_intensity = 0.0
    frame = HapticMixer().update(
        _telemetry(
            rpm=9000.0,
            accel=255,
            surface_rumble_fl=1.0,
            wheel_in_puddle_fr=1,
            tire_combined_slip_rl=3.0,
        ),
        settings,
        now=2.0,
    )

    assert frame.left_low == 0.0
    assert frame.left_high == 0.0
    assert frame.right_low == 0.0
    assert frame.right_high == 0.0
    assert frame.engine_amplitude == 0.0
