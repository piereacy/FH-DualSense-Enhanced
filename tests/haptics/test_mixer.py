import math

import pytest

from modules.config.settings import Settings
from modules.haptics.frame import SILENT_FRAME, to_compatible_rumble
from modules.haptics.mixer import HapticMixer


@pytest.fixture
def settings():
    value = Settings()
    value.enable_body_haptics = True
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


def test_redline_grip_warning_starts_immediately_and_is_bilateral(settings):
    mixer = HapticMixer()

    frame = _redline_frame(settings, mixer, now=1.0)

    assert frame.left_high == pytest.approx(settings.rev_limit_amp / 255.0)
    assert frame.right_high == pytest.approx(frame.left_high)
    assert frame.engine_amplitude > 0.0


def test_redline_grip_warning_uses_ten_hz_half_duty_fuel_cut_pulse(settings):
    mixer = HapticMixer()

    onset = _redline_frame(settings, mixer, now=1.0)
    still_on = _redline_frame(settings, mixer, now=1.049)
    off_half = _redline_frame(settings, mixer, now=1.050)
    next_cycle = _redline_frame(settings, mixer, now=1.100)

    assert onset.left_high > 0.0
    assert still_on.left_high == pytest.approx(onset.left_high)
    assert off_half.left_high == 0.0
    assert next_cycle.left_high == pytest.approx(onset.left_high)


def test_redline_grip_warning_holds_for_configured_deadline(settings):
    mixer = HapticMixer()
    _redline_frame(settings, mixer, now=1.0)

    held = _redline_frame(settings, mixer, now=1.10, rpm=1000.0)
    expired = _redline_frame(settings, mixer, now=1.121, rpm=1000.0)

    assert held.left_high > 0.0
    assert expired.left_high == 0.0
    assert expired.right_high == 0.0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: setattr(value, "enable_rev_limiter", False),
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

    settings.enable_rev_limiter = False
    frame = _redline_frame(settings, mixer, now=1.01, rpm=1000.0)

    assert frame.left_high == 0.0
    assert frame.right_high == 0.0


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
            rpm=settings.rev_limit_ratio * 9000.0 - 1.0,
            accel=255,
        ),
        settings,
        now=2.0,
    )

    assert no_accel.left_high == no_accel.right_high == 0.0
    assert below_redline.left_high == below_redline.right_high == 0.0


def test_usb_and_bluetooth_share_the_same_normalized_redline_envelope(settings):
    mixer = HapticMixer()
    usb_frame = _redline_frame(settings, mixer, now=1.0)
    bluetooth_rumble = to_compatible_rumble(usb_frame)

    assert usb_frame.left_high == usb_frame.right_high
    assert bluetooth_rumble.high_frequency == pytest.approx(usb_frame.left_high)


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


def test_gear_change_creates_centered_kick(settings):
    mixer = HapticMixer()
    mixer.update(_telemetry(gear=2, speed=50.0), settings, now=1.0)
    frame = mixer.update(_telemetry(gear=3, speed=50.0), settings, now=1.01)

    assert frame.left_low == pytest.approx(0.8)
    assert frame.right_low == pytest.approx(0.8)


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
