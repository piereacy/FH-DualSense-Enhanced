"""TUI parity for optional controller lighting."""

from .settings_tab import SettingsTab


LIGHTING_SECTIONS = [
    ("Tachometer lightbar", [
        ("enable_tachometer_lightbar", "Enable tachometer lightbar", None, None,
         "Uses controller lighting only; it does not change trigger or grip feedback."),
        ("tachometer_start_ratio", "Lightbar starts at RPM ratio", 0.0, 1.0, ""),
        ("tachometer_flash_ratio", "Lightbar flashes at RPM ratio", 0.0, 1.0, ""),
        ("tachometer_flash_rate_hz", "Flash rate (Hz)", 0.0, 24.0, ""),
        ("tachometer_brightness", "Lightbar brightness", 0.0, 1.0, ""),
    ]),
    ("Lightbar colors", [
        ("tachometer_start_red", "Start color red", 0, 255, ""),
        ("tachometer_start_green", "Start color green", 0, 255, ""),
        ("tachometer_start_blue", "Start color blue", 0, 255, ""),
        ("tachometer_redline_red", "Redline color red", 0, 255, ""),
        ("tachometer_redline_green", "Redline color green", 0, 255, ""),
        ("tachometer_redline_blue", "Redline color blue", 0, 255, ""),
    ]),
    ("Gear player LEDs", [
        ("enable_gear_player_leds", "Show gear on player LEDs", None, None,
         "Gears 1 to 5+ use the five white player indicator LEDs."),
    ]),
]


class LightingTab(SettingsTab):
    SWITCH_SECTIONS: tuple = ()
    SECTIONS: list = LIGHTING_SECTIONS
    SHOW_RESET = False
    SHOW_ABOUT = False
    SHOW_EXPERIMENTAL = False

