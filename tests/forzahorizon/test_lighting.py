from modules.config.settings import Settings
from modules.dualsense.output_state import NO_VISUAL_CONTROL
from modules.forzahorizon.lighting import LightingController


def _telemetry(**overrides):
    value = {
        "on": True,
        "rpm": 0.0,
        "max_rpm": 9000.0,
        "gear": 1,
    }
    value.update(overrides)
    return value


def test_lighting_does_not_claim_controller_fields_by_default():
    assert LightingController().update(_telemetry(), Settings(), 1.0) == (
        NO_VISUAL_CONTROL
    )


def test_tachometer_uses_teal_gradient_and_flashes_at_redline():
    settings = Settings()
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
