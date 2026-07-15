import ast
import asyncio
import runpy
from dataclasses import fields
from pathlib import Path

from modules.config import preferences, profiles
from modules.config.preferences import GLOBAL_FIELDS
from modules.config.settings import Settings


ROOT = Path(__file__).resolve().parents[1]
BODY_FIELDS = (
    "enable_body_haptics",
    "body_haptics_intensity",
    "engine_haptics_intensity",
    "road_haptics_intensity",
    "impact_haptics_intensity",
    "slip_haptics_intensity",
    "slip_haptics_threshold",
)
BODY_LABELS = {
    "Body haptics",
    "Enable body haptics",
    "Uses the same haptic mix over USB and Bluetooth; only the transport path differs. "
    "Disable in-game vibration only if you feel competing or doubled output.",
    "Master intensity",
    "Engine intensity",
    "Road texture intensity",
    "Impact and suspension intensity",
    "Slip and ABS intensity",
    "Slip threshold",
}
BEHAVIOR_FIELDS = ("exit_on_game_close", "minimize_to_tray")
BEHAVIOR_LABELS = {
    "Application behavior",
    "Close the app when the game closes",
    "Move the app to the tray when minimized",
}
NORMAL_R4_FIELDS = {
    "R2 optional dynamic resistance": (
        "boost_resistance_threshold",
        "boost_resistance_force",
        "gforce_resistance_force",
    ),
    "ABS (anti-lock brake) rumble": ("abs_amp", "abs_sensitivity"),
    "R2 trigger redline vibration": (
        "rev_limit_ratio",
        "rev_limit_freq",
        "rev_limit_amp",
        "rev_limit_hold_ms",
    ),
    "Grip redline vibration": (
        "grip_redline_ratio",
        "grip_redline_freq",
        "grip_redline_amp",
        "grip_redline_duty_cycle",
        "grip_redline_attack_strength",
    ),
    "Optional trigger events": (
        "collision_trigger_freq",
        "collision_trigger_amp",
        "collision_trigger_duration_ms",
        "trigger_surface_freq",
        "trigger_surface_amp",
        "trigger_rumble_strip_freq",
        "trigger_rumble_strip_amp",
    ),
    "Grip gear-shift thump": (
        "grip_gear_shift_strength",
        "grip_gear_shift_duration_ms",
    ),
    "Traction/grip feedback": ("wheelspin_amp", "wheelspin_sensitivity"),
}
EXPERIMENTAL_FIELDS = (
    "abs_brake_threshold",
    "abs_min_speed_kmh",
    "abs_slip_ratio_threshold",
    "abs_combined_slip_threshold",
    "abs_combined_slip_weight",
    "abs_slip_full_scale",
    "abs_freq_min",
    "abs_freq",
    "abs_amp_min",
    "abs_hold_ms",
    "abs_wall_zones",
    "wheelspin_slip_threshold",
    "wheelspin_hysteresis",
    "wheelspin_slip_full_scale",
    "wheelspin_attack_ms",
    "wheelspin_release_ms",
    "wheelspin_g_damping",
    "wheelspin_burnout_rotation_threshold",
    "wheelspin_burnout_rotation_full_scale",
    "wheelspin_tarmac_freq_min",
    "wheelspin_tarmac_freq_max",
    "wheelspin_water_freq_min",
    "wheelspin_water_freq_max",
    "wheelspin_dirt_freq_min",
    "wheelspin_dirt_freq_max",
    "wheelspin_gravel_freq_min",
    "wheelspin_gravel_freq_max",
    "grip_redline_release_ratio",
    "grip_redline_gain",
    "grip_redline_low_ratio",
    "grip_redline_background_duck",
    "grip_redline_attack_duration_ms",
    "gforce_lateral_weight",
    "gforce_longitudinal_weight",
    "gforce_full_scale",
    "gforce_attack_ms",
    "gforce_release_ms",
    "collision_haptics_jerk_threshold",
    "collision_haptics_duration_ms",
    "collision_haptics_cooldown_ms",
    "collision_haptics_rebound_ratio",
    "collision_haptics_weak_side_ratio",
    "collision_background_duck",
)
R4_LABELS = {
    "Sensitivity",
    "Shared feedback",
    "Grip feedback",
    "Grip gear-shift thump",
    "Redline feedback",
    "R2 trigger redline vibration",
    "Grip redline vibration",
    "Left grip",
    "Right grip",
    "Trigger near redline at",
    "Trigger vibration frequency (Hz)",
    "Trigger vibration strength",
    "Trigger hold time (ms)",
    "Grip trigger near redline at",
    "Grip pulse rate (Hz)",
    "Grip pulse strength",
    "Grip pulse width",
    "Grip entry impact",
    "Traction/grip feedback",
    "Grip feedback strength",
    "Experimental features",
    "Not recommended for manual adjustment.",
    "ABS advanced tuning",
    "Traction/grip advanced tuning",
    "Minimum brake input",
    "Minimum speed (km/h)",
    "Longitudinal slip threshold",
    "Combined slip threshold",
    "Combined slip influence",
    "Slip at maximum feedback",
    "Minimum frequency (Hz)",
    "Maximum frequency (Hz)",
    "Minimum strength",
    "Feedback hold (ms)",
    "Top wall zones",
    "Slip hysteresis",
    "Attack smoothing (ms)",
    "Release smoothing (ms)",
    "G-force damping",
    "Burnout rotation threshold",
    "Burnout rotation at maximum feedback",
    "Tarmac minimum frequency (Hz)",
    "Tarmac maximum frequency (Hz)",
    "Water minimum frequency (Hz)",
    "Water maximum frequency (Hz)",
    "Dirt minimum frequency (Hz)",
    "Dirt maximum frequency (Hz)",
    "Gravel minimum frequency (Hz)",
    "Gravel maximum frequency (Hz)",
    "Grip redline advanced tuning",
    "Grip release below redline at",
    "Grip signal gain",
    "Low-frequency pulse ratio",
    "Redline background level",
    "Grip entry impact duration (ms)",
    "R2 optional dynamic resistance",
    "Boost activation threshold",
    "Boost extra resistance",
    "G-force extra resistance",
    "G-force resistance advanced tuning",
    "Lateral G weight",
    "Longitudinal G weight",
    "G force at maximum resistance",
    "G-force attack smoothing (ms)",
    "G-force release smoothing (ms)",
    "Optional trigger events",
    "Collision trigger frequency (Hz)",
    "Collision trigger strength",
    "Collision trigger duration (ms)",
    "Road texture frequency (Hz)",
    "Road texture strength",
    "Rumble strip frequency (Hz)",
    "Rumble strip strength",
    "Collision trigger jolt",
    "Idle road texture",
    "Turbo boost resistance",
    "G-force resistance",
    "Collision haptics advanced tuning",
    "Collision jerk threshold",
    "Collision duration (ms)",
    "Collision cooldown (ms)",
    "Collision rebound strength",
    "Collision weak-side strength",
    "Collision background level",
    "R2 trigger gear-shift thump",
    "Grip thump strength",
    "Grip thump length (ms)",
}

LIGHTING_FIELDS = (
    "enable_tachometer_lightbar",
    "tachometer_start_ratio",
    "tachometer_flash_ratio",
    "tachometer_flash_rate_hz",
    "tachometer_brightness",
    "tachometer_start_red",
    "tachometer_start_green",
    "tachometer_start_blue",
    "tachometer_redline_red",
    "tachometer_redline_green",
    "tachometer_redline_blue",
    "enable_gear_player_leds",
)
LIGHTING_LABELS = {
    "Controller lighting",
    "Optional visual feedback with independent switches.",
    "Tachometer lightbar",
    "Enable tachometer lightbar",
    "Uses controller lighting only; it does not change trigger or grip feedback.",
    "Lightbar starts at RPM ratio",
    "Lightbar flashes at RPM ratio",
    "Flash rate (Hz)",
    "Lightbar brightness",
    "Lightbar colors",
    "Start color red",
    "Start color green",
    "Start color blue",
    "Redline color red",
    "Redline color green",
    "Redline color blue",
    "Gear player LEDs",
    "Show gear on player LEDs",
    "Gears 1 to 5+ use the five white player indicator LEDs.",
}


def _sections(path, variable):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == variable
                   for target in node.targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"{variable} not found in {path}")


def _setting_sections(path):
    return _sections(path, "SETTING_SECTIONS")


def _body_fields(path):
    sections = _setting_sections(path)
    section = next((items for title, items in sections if title == "Body haptics"), None)
    assert section is not None, f"Body haptics section missing from {path}"
    return tuple(item[0] for item in section)


def _behavior_fields(path):
    sections = _sections(path, "SYSTEM_SECTIONS")
    section = next((items for title, items in sections if title == "Application behavior"), None)
    assert section is not None, f"Application behavior section missing from {path}"
    return tuple(item[0] for item in section)


def _fields_by_section(path, variable):
    return {
        title: tuple(item[0] for item in items)
        for title, items in _sections(path, variable)
    }


def test_gui_and_tui_expose_the_same_body_haptics_fields():
    gui = _body_fields(ROOT / "src/modules/gui/settings_tab.py")
    tui = _body_fields(ROOT / "src/modules/tui/settings_tab.py")

    assert gui == BODY_FIELDS
    assert tui == BODY_FIELDS


def test_body_haptics_fields_are_profile_scoped_settings():
    setting_names = {field.name for field in fields(Settings)}

    assert set(BODY_FIELDS) <= setting_names
    assert set(BODY_FIELDS).isdisjoint(GLOBAL_FIELDS)


def test_every_non_english_catalog_translates_body_haptics_labels():
    for path in sorted((ROOT / "src/lang").glob("*.py")):
        if path.name in {"__init__.py", "en.py"}:
            continue
        strings = runpy.run_path(str(path))["STRINGS"]
        missing = BODY_LABELS - strings.keys()
        assert not missing, f"{path.name} is missing {sorted(missing)}"


def test_gui_and_tui_expose_the_same_application_behavior_fields():
    gui = _behavior_fields(ROOT / "src/modules/gui/settings_tab.py")
    tui = _behavior_fields(ROOT / "src/modules/tui/settings_tab.py")

    assert gui == BEHAVIOR_FIELDS
    assert tui == BEHAVIOR_FIELDS


def test_application_behavior_defaults_are_enabled_and_global():
    settings = Settings()

    assert settings.exit_on_game_close is True
    assert settings.minimize_to_tray is True
    assert set(BEHAVIOR_FIELDS) <= GLOBAL_FIELDS


def test_application_behavior_globals_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")
    settings = Settings()
    settings.exit_on_game_close = False
    settings.minimize_to_tray = False

    preferences.save(settings)
    loaded = Settings()
    preferences.load(loaded)

    assert loaded.exit_on_game_close is False
    assert loaded.minimize_to_tray is False


def test_every_non_english_catalog_translates_application_behavior_labels():
    for path in sorted((ROOT / "src/lang").glob("*.py")):
        if path.name in {"__init__.py", "en.py"}:
            continue
        strings = runpy.run_path(str(path))["STRINGS"]
        missing = BEHAVIOR_LABELS - strings.keys()
        assert not missing, f"{path.name} is missing {sorted(missing)}"


def test_gui_and_tui_expose_identical_normal_r4_tuning_sections():
    for relative in ("src/modules/gui/settings_tab.py", "src/modules/tui/settings_tab.py"):
        sections = _fields_by_section(ROOT / relative, "SETTING_SECTIONS")
        for title, expected in NORMAL_R4_FIELDS.items():
            assert sections[title] == expected


def test_gui_and_tui_expose_identical_advanced_r4_fields():
    gui = _fields_by_section(
        ROOT / "src/modules/gui/settings_tab.py", "EXPERIMENTAL_SECTIONS"
    )
    tui = _fields_by_section(
        ROOT / "src/modules/tui/settings_tab.py", "EXPERIMENTAL_SECTIONS"
    )

    assert gui == tui
    assert tuple(field for fields_ in gui.values() for field in fields_) == EXPERIMENTAL_FIELDS


def test_all_r4_tuning_fields_are_profile_scoped_settings():
    setting_names = {field.name for field in fields(Settings)}
    normal_fields = {field for values in NORMAL_R4_FIELDS.values() for field in values}
    all_fields = normal_fields | set(EXPERIMENTAL_FIELDS)

    assert all_fields <= setting_names
    assert all_fields.isdisjoint(GLOBAL_FIELDS)


def test_r2_tuning_fields_round_trip_in_a_named_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")
    settings = Settings()
    preferences.load(settings)
    settings.abs_sensitivity = 1.7
    settings.abs_hold_ms = 88.0
    settings.wheelspin_sensitivity = 1.4
    settings.wheelspin_attack_ms = 35.0
    settings.wheelspin_tarmac_freq_max = 175
    settings.enable_grip_gear_shift_haptics = True
    settings.grip_gear_shift_strength = 0.6
    settings.grip_gear_shift_duration_ms = 80.0
    settings.grip_redline_gain = 1.25
    assert profiles.save_profile("R2 Test", settings) == "R2 Test"

    loaded = Settings()
    preferences.load(loaded)

    assert loaded.abs_sensitivity == 1.7
    assert loaded.abs_hold_ms == 88.0
    assert loaded.wheelspin_sensitivity == 1.4
    assert loaded.wheelspin_attack_ms == 35.0
    assert loaded.wheelspin_tarmac_freq_max == 175
    assert loaded.enable_grip_gear_shift_haptics is True
    assert loaded.grip_gear_shift_strength == 0.6
    assert loaded.grip_gear_shift_duration_ms == 80.0
    assert loaded.grip_redline_gain == 1.25


def test_r2_tuning_fields_round_trip_through_share_code(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")
    settings = Settings()
    preferences.load(settings)
    settings.abs_sensitivity = 1.6
    settings.abs_wall_zones = 4
    settings.wheelspin_sensitivity = 1.3
    settings.wheelspin_release_ms = 140.0
    settings.enable_grip_gear_shift_haptics = True
    settings.grip_gear_shift_strength = 0.65
    assert profiles.save_profile("R2 Share", settings) == "R2 Share"

    code = profiles.export_profile("R2 Share")
    imported = profiles.import_profile(code)
    snapshot = profiles.load_profiles()["profiles"][imported]

    assert code.startswith(profiles.SHARE_PREFIX)
    assert imported == "R2 Share1"
    assert snapshot["abs_sensitivity"] == 1.6
    assert snapshot["abs_wall_zones"] == 4
    assert snapshot["wheelspin_sensitivity"] == 1.3
    assert snapshot["wheelspin_release_ms"] == 140.0
    assert snapshot["enable_grip_gear_shift_haptics"] is True
    assert snapshot["grip_gear_shift_strength"] == 0.65


def test_experimental_settings_are_collapsed_by_default_and_excluded_from_system_tabs():
    gui = (ROOT / "src/modules/gui/settings_tab.py").read_text(encoding="utf-8")
    gui_system = (ROOT / "src/modules/gui/system_tab.py").read_text(encoding="utf-8")
    tui = (ROOT / "src/modules/tui/settings_tab.py").read_text(encoding="utf-8")
    tui_system = (ROOT / "src/modules/tui/system_tab.py").read_text(encoding="utf-8")

    assert "self._experimental_open = False" in gui
    assert "collapsed=True" in tui
    assert "SHOW_EXPERIMENTAL = False" in gui_system
    assert "SHOW_EXPERIMENTAL = False" in tui_system


def test_tui_experimental_settings_mount_collapsed():
    from textual.app import App, ComposeResult
    from textual.widgets import Collapsible

    from modules.tui.settings_tab import SettingsTab

    class SettingsHarness(App):
        def compose(self) -> ComposeResult:
            yield SettingsTab(Settings())

    async def check():
        app = SettingsHarness()
        async with app.run_test():
            experimental = app.query_one("#experimental-settings", Collapsible)
            assert experimental.collapsed is True

    asyncio.run(check())


def test_every_non_english_catalog_translates_r4_settings_labels():
    for path in sorted((ROOT / "src/lang").glob("*.py")):
        if path.name in {"__init__.py", "en.py"}:
            continue
        strings = runpy.run_path(str(path))["STRINGS"]
        missing = R4_LABELS - strings.keys()
        assert not missing, f"{path.name} is missing {sorted(missing)}"


def test_gui_and_tui_expose_identical_profile_scoped_lighting_fields():
    gui = _fields_by_section(
        ROOT / "src/modules/gui/lighting_tab.py", "LIGHTING_SECTIONS"
    )
    tui = _fields_by_section(
        ROOT / "src/modules/tui/lighting_tab.py", "LIGHTING_SECTIONS"
    )
    flattened = tuple(field for values in gui.values() for field in values)

    assert gui == tui
    assert flattened == LIGHTING_FIELDS
    assert set(flattened).isdisjoint(GLOBAL_FIELDS)


def test_every_non_english_catalog_translates_lighting_labels():
    for path in sorted((ROOT / "src/lang").glob("*.py")):
        if path.name in {"__init__.py", "en.py"}:
            continue
        strings = runpy.run_path(str(path))["STRINGS"]
        missing = LIGHTING_LABELS - strings.keys()
        assert not missing, f"{path.name} is missing {sorted(missing)}"


def test_gui_and_tui_separate_trigger_and_grip_redline_controls():
    gui = _sections(ROOT / "src/modules/gui/controls_tab.py", "TRIGGER_CONTROLS")
    tui = _sections(ROOT / "src/modules/tui/controls_tab.py", "TRIGGER_CONTROLS")

    assert gui == tui
    assert "yield Label(t(trigger), classes=\"section\")" in (
        ROOT / "src/modules/tui/controls_tab.py"
    ).read_text(encoding="utf-8")
    groups = {title: dict(items) for title, items in gui}
    assert groups["R2 - Throttle"]["enable_rev_limiter"] == (
        "R2 trigger redline vibration"
    )
    assert groups["L2 - Brake"]["enable_collision_trigger_l2"] == (
        "Collision trigger jolt"
    )
    assert groups["L2 - Brake"]["enable_trigger_surface_l2"] == "Idle road texture"
    assert groups["R2 - Throttle"]["enable_boost_resistance"] == (
        "Turbo boost resistance"
    )
    assert groups["R2 - Throttle"]["enable_gforce_resistance"] == (
        "G-force resistance"
    )
    assert groups["R2 - Throttle"]["enable_collision_trigger_r2"] == (
        "Collision trigger jolt"
    )
    assert groups["R2 - Throttle"]["enable_trigger_surface_r2"] == "Idle road texture"
    assert "enable_wheelspin_buzz" not in groups["R2 - Throttle"]
    assert groups["Shared feedback"] == {
        "enable_wheelspin_buzz": "Traction/grip feedback",
    }
    assert groups["Grip feedback"] == {
        "enable_grip_gear_shift_haptics": "Grip gear-shift thump",
    }
    assert groups["Redline feedback"] == {
        "enable_grip_redline_haptics": "Grip redline vibration",
        "grip_redline_left": "Left grip",
        "grip_redline_right": "Right grip",
    }


def test_simplified_chinese_distinguishes_r2_trigger_and_grip_redline():
    strings = runpy.run_path(str(ROOT / "src/lang/zh.py"))["STRINGS"]

    assert strings["R2 trigger redline vibration"] == "R2 扳机键红线震动"
    assert strings["Grip redline vibration"] == "握把红线震动"
    assert strings["Left grip"] == "左握把"
    assert strings["Right grip"] == "右握把"
    assert strings["Grip feedback"] == "握把反馈"
    assert strings["Grip gear-shift thump"] == "握把换挡冲击"
    assert strings["R2 trigger gear-shift thump"] == "R2 扳机键换挡冲击"
