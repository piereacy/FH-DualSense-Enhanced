import math

import pytest

from modules.config.settings import Settings
from modules.dualsense.adaptive_trigger import M_VIBRATE, M_VIBRATE_ZONES
from modules.forzahorizon.effects import Controller, TriggerAnimations, _AsymmetricEwma


WHEELS = ("fl", "fr", "rl", "rr")


def _telemetry(**overrides):
    value = {
        "on": True,
        "speed": 50.0,
        "drive_train": 2,
        "accel": 255,
        "brake": 0,
        "handbrake": 0,
        "rpm": 1000.0,
        "max_rpm": 9000.0,
        "accel_x": 0.0,
        "accel_z": 0.0,
    }
    for wheel in WHEELS:
        value[f"tire_slip_ratio_{wheel}"] = 0.0
        value[f"tire_combined_slip_{wheel}"] = 0.0
        value[f"wheel_rotation_speed_{wheel}"] = 0.0
        value[f"wheel_in_puddle_{wheel}"] = 0.0
        value[f"surface_rumble_{wheel}"] = 0.0
    value.update(overrides)
    return value


def _settled_wheelspin(animation, telemetry, settings, start=1.0):
    assert animation.wheelspin_buzz(telemetry, settings, start) is None
    return animation.wheelspin_buzz(telemetry, settings, start + 0.04)


def _unpack_zones(frame):
    _, params = frame
    active = params[0] | (params[1] << 8)
    packed = params[2] | (params[3] << 8) | (params[4] << 16) | (params[5] << 24)
    return [
        ((packed >> (3 * index)) & 0x07) + 1 if active & (1 << index) else 0
        for index in range(10)
    ]


def test_asymmetric_ewma_uses_elapsed_time_and_distinct_time_constants():
    ewma = _AsymmetricEwma()

    assert ewma.update(1.0, now=1.0, attack_ms=40.0, release_ms=125.0) == 0.0

    attack = ewma.update(1.0, now=1.04, attack_ms=40.0, release_ms=125.0)
    assert attack == pytest.approx(1.0 - math.exp(-1.0))

    release = ewma.update(0.0, now=1.08, attack_ms=40.0, release_ms=125.0)
    assert release == pytest.approx(attack * math.exp(-0.04 / 0.125))
    assert release > 0.0


def test_asymmetric_ewma_clamps_targets_and_can_reset():
    ewma = _AsymmetricEwma()
    ewma.update(2.0, now=1.0, attack_ms=40.0, release_ms=125.0)
    assert ewma.update(2.0, now=1.04, attack_ms=40.0, release_ms=125.0) < 1.0

    ewma.reset()

    assert ewma.value == 0.0
    assert ewma.update(-1.0, now=2.0, attack_ms=40.0, release_ms=125.0) == 0.0


def test_wheelspin_uses_only_driven_wheel_longitudinal_slip():
    settings = Settings()
    animation = TriggerAnimations()
    rear_only = _telemetry(
        drive_train=0,
        tire_slip_ratio_rl=3.0,
        tire_slip_ratio_rr=3.0,
        tire_combined_slip_fl=9.0,
    )

    assert animation.wheelspin_buzz(rear_only, settings, 1.0) is None
    assert animation.wheelspin_buzz(rear_only, settings, 1.04) is None

    front_slip = _telemetry(drive_train=0, tire_slip_ratio_fl=2.0)
    frame = _settled_wheelspin(TriggerAnimations(), front_slip, settings)

    assert frame[0] == M_VIBRATE
    assert frame[1][1] > 0


def test_wheelspin_rejects_lateral_only_slip_and_lift_off_drift():
    settings = Settings()

    lateral = _telemetry(tire_combined_slip_rr=9.0)
    assert _settled_wheelspin(TriggerAnimations(), lateral, settings) is None

    lift_off = _telemetry(accel=0, tire_slip_ratio_rr=3.0)
    assert _settled_wheelspin(TriggerAnimations(), lift_off, settings) is None


def test_wheelspin_sensitivity_changes_the_effective_threshold():
    telemetry = _telemetry(tire_slip_ratio_rr=0.4)

    normal = Settings()
    assert _settled_wheelspin(TriggerAnimations(), telemetry, normal) is None

    sensitive = Settings()
    sensitive.wheelspin_sensitivity = 2.0
    assert _settled_wheelspin(TriggerAnimations(), telemetry, sensitive)[0] == M_VIBRATE


def test_low_speed_burnout_uses_driven_wheel_rotation():
    settings = Settings()
    non_driven = _telemetry(
        speed=0.0,
        drive_train=1,
        wheel_rotation_speed_fl=120.0,
        tire_slip_ratio_rr=9.0,
    )
    assert _settled_wheelspin(TriggerAnimations(), non_driven, settings) is None

    driven = _telemetry(speed=0.0, drive_train=1, wheel_rotation_speed_rr=120.0)
    assert _settled_wheelspin(TriggerAnimations(), driven, settings)[0] == M_VIBRATE


def test_wheelspin_hysteresis_holds_until_the_release_threshold():
    settings = Settings()
    animation = TriggerAnimations()
    active = _telemetry(tire_slip_ratio_rr=1.5)
    _settled_wheelspin(animation, active, settings)

    animation.wheelspin_buzz(
        _telemetry(tire_slip_ratio_rr=0.55), settings, 1.08
    )
    assert animation._wheelspin_active is True

    animation.wheelspin_buzz(
        _telemetry(tire_slip_ratio_rr=0.50), settings, 1.12
    )
    assert animation._wheelspin_active is False


@pytest.mark.parametrize(
    ("material", "expected_band"),
    [
        ({}, (90, 180)),
        ({"wheel_in_puddle_rr": 1.0}, (80, 150)),
        ({"surface_rumble_rr": 0.20}, (30, 70)),
        ({"surface_rumble_rr": 0.40}, (12, 30)),
    ],
)
def test_wheelspin_preserves_dynamic_surface_frequency_bands(material, expected_band):
    settings = Settings()
    telemetry = _telemetry(tire_slip_ratio_rr=2.0, **material)

    frame = _settled_wheelspin(TriggerAnimations(), telemetry, settings)

    assert expected_band[0] <= frame[1][0] <= expected_band[1]


def test_wheelspin_g_force_is_only_a_mild_inverse_amplitude_damping():
    settings = Settings()
    calm = _settled_wheelspin(
        TriggerAnimations(), _telemetry(tire_slip_ratio_rr=2.0), settings
    )
    one_g = _settled_wheelspin(
        TriggerAnimations(),
        _telemetry(tire_slip_ratio_rr=2.0, accel_z=9.80665),
        settings,
    )

    assert one_g[1][1] < calm[1][1]
    assert one_g[1][1] == pytest.approx(calm[1][1] * 0.8, abs=1)

    extreme = _settled_wheelspin(
        TriggerAnimations(),
        _telemetry(tire_slip_ratio_rr=2.0, accel_z=39.2266),
        settings,
    )
    assert extreme[1][1] >= calm[1][1] * 0.7 - 1


def test_wheelspin_reset_clears_latched_and_smoothed_state():
    settings = Settings()
    animation = TriggerAnimations()
    _settled_wheelspin(animation, _telemetry(tire_slip_ratio_rr=2.0), settings)

    animation.reset_transients()

    assert animation._wheelspin_active is False
    assert animation._wheelspin_ewma.value == 0.0


def test_r2_trigger_wheelspin_takes_priority_over_rev_limiter_at_speed():
    settings = Settings()
    controller = Controller(settings)
    telemetry = _telemetry(
        rpm=9000.0,
        max_rpm=9000.0,
        tire_slip_ratio_rr=2.0,
    )

    controller.R2(telemetry, settings, 1.0)
    frame = controller.R2(telemetry, settings, 1.04)

    assert frame[0] == M_VIBRATE
    assert frame[1] != (settings.rev_limit_freq, settings.rev_limit_amp)
    assert frame[1][0] > settings.rev_limit_freq


def test_r2_trigger_low_speed_raw_rotation_takes_priority_over_rev_limiter():
    settings = Settings()
    controller = Controller(settings)
    telemetry = _telemetry(
        speed=0.0,
        drive_train=1,
        rpm=9000.0,
        max_rpm=9000.0,
        wheel_rotation_speed_rr=120.0,
    )

    controller.R2(telemetry, settings, 1.0)
    frame = controller.R2(telemetry, settings, 1.04)

    assert frame[0] == M_VIBRATE
    assert frame[1] != (settings.rev_limit_freq, settings.rev_limit_amp)
    assert frame[1][0] > settings.rev_limit_freq


def test_r2_trigger_rev_limiter_still_runs_when_driven_wheels_have_grip():
    settings = Settings()
    telemetry = _telemetry(rpm=9000.0, max_rpm=9000.0)

    frame = Controller(settings).R2(telemetry, settings, 1.0)

    assert frame == (M_VIBRATE, (settings.rev_limit_freq, settings.rev_limit_amp))


def test_abs_requires_brake_and_minimum_speed():
    settings = Settings()
    animation = TriggerAnimations()
    slipping = _telemetry(brake=255, tire_slip_ratio_fl=1.0)

    assert animation.abs_pulse({**slipping, "brake": 254}, settings, 1.0) is None
    assert animation.abs_pulse({**slipping, "speed": 5.9}, settings, 1.0) is None
    assert animation.abs_pulse(slipping, settings, 1.0)[0] == M_VIBRATE_ZONES


def test_abs_uses_longitudinal_slip_as_primary_and_combined_as_weaker_auxiliary():
    settings = Settings()
    longitudinal = TriggerAnimations().abs_pulse(
        _telemetry(brake=255, tire_slip_ratio_fl=1.0), settings, 1.0
    )
    combined = TriggerAnimations().abs_pulse(
        _telemetry(brake=255, tire_combined_slip_fl=1.0), settings, 1.0
    )

    assert longitudinal[1][8] > combined[1][8]
    assert _unpack_zones(longitudinal)[0] >= _unpack_zones(combined)[0]


def test_abs_speed_is_a_gate_not_an_intensity_input():
    settings = Settings()
    common = dict(brake=255, tire_slip_ratio_fl=1.0)

    slow = TriggerAnimations().abs_pulse(_telemetry(speed=10.0, **common), settings, 1.0)
    fast = TriggerAnimations().abs_pulse(_telemetry(speed=200.0, **common), settings, 1.0)

    assert slow == fast


def test_abs_frequency_and_amplitude_rise_with_slip():
    settings = Settings()
    low = TriggerAnimations().abs_pulse(
        _telemetry(brake=255, tire_slip_ratio_fl=0.4), settings, 1.0
    )
    high = TriggerAnimations().abs_pulse(
        _telemetry(brake=255, tire_slip_ratio_fl=2.0), settings, 1.0
    )

    assert low[0] == high[0] == M_VIBRATE_ZONES
    assert low[1][8] < high[1][8]
    assert _unpack_zones(low)[0] < _unpack_zones(high)[0]


def test_abs_keeps_the_top_three_zones_at_maximum_wall_strength():
    settings = Settings()

    frame = TriggerAnimations().abs_pulse(
        _telemetry(brake=255, tire_slip_ratio_fl=1.0), settings, 1.0
    )
    zones = _unpack_zones(frame)

    assert zones[-3:] == [8, 8, 8]
    assert all(1 <= strength < 8 for strength in zones[:-3])


def test_abs_holds_the_last_dynamic_pulse_for_100_ms():
    settings = Settings()
    animation = TriggerAnimations()
    active = _telemetry(brake=255, tire_slip_ratio_fl=1.0)
    clear = _telemetry(brake=255)

    frame = animation.abs_pulse(active, settings, 1.0)

    assert animation.abs_pulse(clear, settings, 1.099) == frame
    assert animation.abs_pulse(clear, settings, 1.101) is None
