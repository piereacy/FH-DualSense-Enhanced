import ast
import runpy
from dataclasses import fields
from pathlib import Path

from modules.config import preferences
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
    "Automatically uses high-fidelity USB audio or Bluetooth compatible rumble. "
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
