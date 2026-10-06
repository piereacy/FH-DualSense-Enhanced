import pytest

from modules.config import preferences
from modules.config.settings import Settings
from modules.dualsense.output_state import ControllerVisualState, NO_VISUAL_CONTROL
from modules.forzahorizon.lighting import LightingController
from modules.forzahorizon.redline import RedlineDetector


def _before_r11_settings():
    settings = Settings()
    preferences._apply_snap(
        settings,
        preferences.default_before_r11_profile_fields(),
        preferences._profile_fields(settings),
    )
    return settings


def _telemetry(**overrides):
    value = {
        "on": True,
        "rpm": 0.0,
        "max_rpm": 9000.0,
        "gear": 1,
    }
    value.update(overrides)
    return value


def _detector_telemetry(**overrides):
    value = {
        "on": True,
        "rpm": 6100.0,
        "max_rpm": 12_000.0,
        "idle_rpm": 900.0,
        "gear": 3,
        "accel": 255,
        "clutch": 0,
        "speed": 120.0,
        "power": 120_000.0,
        "torque": 300.0,
        "car_ordinal": 101,
        "car_performance_index": 800,
        "num_cylinders": 8,
    }
    for wheel in ("fl", "fr", "rl", "rr"):
        value[f"tire_slip_ratio_{wheel}"] = 0.0
        value[f"tire_combined_slip_{wheel}"] = 0.0
    value.update(overrides)
    return value


def _confirm_broad_cut(detector, start, rpm):
    detector.update(_detector_telemetry(rpm=rpm), start)
    detector.update(
        _detector_telemetry(
            rpm=rpm - 90.0,
            power=8_000.0,
            torque=20.0,
        ),
        start + 0.02,
    )
    return detector.update(
        _detector_telemetry(
            rpm=rpm - 100.0,
            power=100_000.0,
            torque=260.0,
        ),
        start + 0.15,
    )


def test_lighting_does_not_claim_controller_fields_when_disabled():
    assert LightingController().update(_telemetry(), _before_r11_settings(), 1.0) == (
        NO_VISUAL_CONTROL
    )


def test_tachometer_uses_teal_gradient_and_flashes_at_redline():
    settings = _before_r11_settings()
    settings.enable_tachometer_lightbar = True
    controller = LightingController()

    below = controller.update(_telemetry(rpm=5000.0), settings, 1.0)
    start = controller.update(
        _telemetry(rpm=settings.tachometer_start_ratio * 9000.0),
        settings,
        1.0,
    )
    redline_on = controller.update(_telemetry(rpm=9000.0), settings, 1.0)
    redline_off = controller.update(_telemetry(rpm=9000.0), settings, 1.05)

    assert below.lightbar == (0, 0, 0)
    assert start.lightbar == (40, 138, 131)
    assert redline_on.lightbar == (178, 27, 56)
    assert redline_off.lightbar == (0, 0, 0)


def test_tachometer_uses_the_shared_dynamic_redline_when_available():
    settings = _before_r11_settings()
    settings.enable_tachometer_lightbar = True
    controller = LightingController()

    state = controller.update(
        _telemetry(
            rpm=7200.0,
            max_rpm=9000.0,
            effective_redline_rpm=7500.0,
        ),
        settings,
        1.0,
    )

    assert state.lightbar == (178, 27, 56)


def test_tachometer_follows_the_new_broad_learning_result_end_to_end():
    settings = _before_r11_settings()
    settings.enable_tachometer_lightbar = True
    lighting = LightingController()
    detector = RedlineDetector()

    before_learning = lighting.update(
        _telemetry(rpm=5900.0, max_rpm=12_000.0),
        settings,
        2.0,
    )

    detector.update(_detector_telemetry(), 0.0)
    detector.update(_detector_telemetry(), 0.40)
    _confirm_broad_cut(detector, 0.50, 6200.0)
    _confirm_broad_cut(detector, 0.90, 6240.0)
    learned = _confirm_broad_cut(detector, 1.30, 6180.0)

    after_learning = lighting.update(
        _telemetry(
            rpm=5900.0,
            max_rpm=12_000.0,
            effective_redline_rpm=learned.effective_rpm,
            rev_limiter_active=learned.limiter_active,
            redline_alert_allowed=learned.redline_alert_allowed,
        ),
        settings,
        2.0,
    )

    assert learned.learned is True
    assert 6100.0 <= learned.effective_rpm <= 6300.0
    assert before_learning.lightbar == (0, 0, 0)
    assert after_learning.lightbar == (178, 27, 56)


def test_confirmed_limiter_event_forces_the_tachometer_flash():
    settings = _before_r11_settings()
    settings.enable_tachometer_lightbar = True

    state = LightingController().update(
        _telemetry(
            rpm=6000.0,
            max_rpm=9000.0,
            effective_redline_rpm=7500.0,
            rev_limiter_active=True,
        ),
        settings,
        1.0,
    )

    assert state.lightbar == (178, 27, 56)


def test_ev_tachometer_stays_steady_red_without_shift_flashing():
    settings = _before_r11_settings()
    settings.enable_tachometer_lightbar = True
    controller = LightingController()
    electric_limit = _telemetry(
        rpm=9000.0,
        effective_redline_rpm=9000.0,
        redline_alert_allowed=False,
        rev_limiter_active=True,
    )

    first = controller.update(electric_limit, settings, 1.0)
    terrain_dip = controller.update(
        {**electric_limit, "rpm": 8950.0, "rev_limiter_active": False},
        settings,
        1.05,
    )
    repeated_limit = controller.update(electric_limit, settings, 1.10)

    assert first.lightbar == (178, 27, 56)
    assert terrain_dip.lightbar == (178, 27, 56)
    assert repeated_limit.lightbar == (178, 27, 56)


def test_multi_speed_ev_tachometer_keeps_near_limit_gradient_and_steady_red():
    settings = _before_r11_settings()
    settings.enable_tachometer_lightbar = True
    controller = LightingController()
    electric = _telemetry(
        gear=2,
        effective_redline_rpm=9000.0,
        redline_alert_allowed=False,
    )

    approaching = controller.update(
        {**electric, "rpm": 8100.0},
        settings,
        1.00,
    )
    limit_on_flash_phase = controller.update(
        {**electric, "rpm": 9000.0},
        settings,
        1.05,
    )
    limit_on_dark_phase = controller.update(
        {**electric, "rpm": 9000.0},
        settings,
        1.10,
    )

    assert approaching.lightbar not in {(0, 0, 0), (178, 27, 56)}
    assert limit_on_flash_phase.lightbar == (178, 27, 56)
    assert limit_on_dark_phase.lightbar == (178, 27, 56)


def test_gear_player_leds_progress_from_one_to_five():
    settings = Settings()
    settings.enable_gear_player_leds = True
    controller = LightingController()

    assert [
        controller.update(_telemetry(gear=gear), settings, 1.0).player_leds
        for gear in range(1, 6)
    ] == [0x04, 0x0A, 0x15, 0x1B, 0x1F]


def test_disabling_lighting_clears_once_then_releases_field_ownership():
    settings = Settings()
    settings.enable_tachometer_lightbar = True
    settings.enable_gear_player_leds = True
    controller = LightingController()
    controller.update(_telemetry(rpm=8000.0, gear=4), settings, 1.0)

    settings.enable_tachometer_lightbar = False
    settings.enable_gear_player_leds = False
    cleared = controller.update(_telemetry(), settings, 1.1)
    released = controller.update(_telemetry(), settings, 1.2)

    assert cleared.lightbar == (0, 0, 0)
    assert cleared.player_leds == 0
    assert released == NO_VISUAL_CONTROL


def test_telemetry_off_explicitly_blanks_enabled_lighting():
    settings = Settings()
    settings.enable_tachometer_lightbar = True
    settings.enable_gear_player_leds = True

    state = LightingController().update({"on": False}, settings, 1.0)

    assert state.lightbar == (0, 0, 0)
    assert state.player_leds == 0


def test_non_finite_lighting_inputs_fail_silent_instead_of_crashing():
    settings = Settings()
    settings.enable_tachometer_lightbar = True
    settings.enable_gear_player_leds = True

    state = LightingController().update(
        _telemetry(rpm=float("nan"), max_rpm=float("inf"), gear=float("nan")),
        settings,
        float("nan"),
    )

    assert state.lightbar == (0, 0, 0)
    assert state.player_leds == 0
    assert ControllerVisualState(
        lightbar=(float("nan"), float("inf"), "invalid"),
        player_leds=float("nan"),
    ).normalized() == ControllerVisualState(lightbar=(0, 0, 0), player_leds=0)


@pytest.mark.parametrize("timestamp", [2.0, 2.03, 1e308])
def test_finite_extreme_flash_rate_is_bounded_and_does_not_overflow(timestamp):
    settings = Settings()
    settings.enable_tachometer_lightbar = True
    settings.tachometer_flash_rate_hz = 1e308
    telemetry = _telemetry(rpm=9000.0)

    actual = LightingController().update(telemetry, settings, timestamp)
    settings.tachometer_flash_rate_hz = 24.0
    expected = LightingController().update(telemetry, settings, timestamp)

    assert actual == expected
    assert all(0 <= channel <= 255 for channel in actual.lightbar)
