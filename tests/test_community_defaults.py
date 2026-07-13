import json
from pathlib import Path

from modules.config import preferences
from modules.config.settings import Settings


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = json.loads(
    (ROOT / "tests/fixtures/community_defaults_2323.json").read_text(encoding="utf-8")
)


def test_fresh_settings_match_community_defaults():
    settings = Settings()
    actual = {name: getattr(settings, name) for name in EXPECTED}

    assert actual == EXPECTED


def test_fresh_default_profile_matches_community_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")
    settings = Settings()

    preferences.load(settings)

    raw = json.loads(preferences.PATH.read_text(encoding="utf-8"))
    actual = {name: raw["profiles"]["Default"][name] for name in EXPECTED}
    assert actual == EXPECTED


def test_named_profile_is_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")
    custom = dict(EXPECTED)
    custom["brake_max_force"] = 4
    preferences.PATH.write_text(json.dumps({
        "active_profile": "Custom",
        "profiles": {"Custom": custom},
        "globals": {},
    }), encoding="utf-8")
    settings = Settings()

    preferences.load(settings)

    raw = json.loads(preferences.PATH.read_text(encoding="utf-8"))
    assert raw["profiles"]["Custom"]["brake_max_force"] == 4
    assert settings.brake_max_force == 4
