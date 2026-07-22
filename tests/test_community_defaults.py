import json
from pathlib import Path

from modules.config import preferences
from modules.config.settings import Settings


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = json.loads(
    (ROOT / "tests/fixtures/community_defaults.json").read_text(encoding="utf-8")
)


def test_fresh_settings_match_community_defaults():
    settings = Settings()
    actual = {name: getattr(settings, name) for name in EXPECTED}

    assert actual == EXPECTED


def test_r4_grip_effects_use_safe_defaults():
    settings = Settings()

    assert settings.enable_rev_limiter is False
    assert settings.enable_grip_redline_haptics is True
    assert settings.grip_redline_amp == 220
    assert settings.grip_redline_gain == 1.5
    assert settings.grip_redline_duty_cycle == 0.7
    assert settings.grip_redline_low_ratio == 0.45
    assert settings.grip_redline_attack_strength == 0.65
    assert settings.enable_grip_gear_shift_haptics is False
    assert settings.grip_gear_shift_strength == 0.8
    assert settings.grip_gear_shift_duration_ms == 100.0


def test_fresh_default_profile_matches_community_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")
    settings = Settings()

    preferences.load(settings)

    raw = json.loads(preferences.PATH.read_text(encoding="utf-8"))
    persisted = dict(raw["globals"])
    persisted.update(raw["profiles"]["Default"])
    actual = {name: persisted[name] for name in EXPECTED}
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


def _without_grip_redline_fields(snapshot):
    return {
        key: value
        for key, value in snapshot.items()
        if not key.startswith("grip_redline_")
        and key != "enable_grip_redline_haptics"
    }


def test_r2_named_profile_keeps_trigger_redline_and_gets_grip_defaults(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")
    custom = _without_grip_redline_fields(EXPECTED)
    preferences.PATH.write_text(json.dumps({
        "version": "2",
        "active_profile": "Custom",
        "profiles": {"Custom": custom},
        "globals": {},
    }), encoding="utf-8")

    settings = Settings()
    preferences.load(settings)

    raw = json.loads(preferences.PATH.read_text(encoding="utf-8"))
    assert settings.rev_limit_freq == 30
    assert settings.rev_limit_amp == 12
    assert settings.grip_redline_freq == 10
    assert settings.grip_redline_amp == 220
    assert settings.grip_redline_gain == 1.5
    assert settings.enable_grip_redline_haptics is True
    assert settings.grip_redline_left is True
    assert settings.grip_redline_right is False
    assert settings.enable_grip_gear_shift_haptics is False
    assert settings.grip_gear_shift_strength == 0.8
    assert settings.grip_gear_shift_duration_ms == 100.0
    assert raw["profiles"]["Custom"]["rev_limit_freq"] == 30
    assert raw["profiles"]["Custom"]["rev_limit_amp"] == 12
    assert raw["profiles"]["Custom"]["grip_redline_freq"] == 10
    assert raw["profiles"]["Custom"]["grip_redline_amp"] == 220
    assert raw["profiles"]["Custom"]["grip_redline_gain"] == 1.5
    assert raw["profiles"]["Custom"]["enable_grip_gear_shift_haptics"] is False


def test_r2_named_profile_custom_redline_values_are_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")
    custom = _without_grip_redline_fields(EXPECTED)
    custom["rev_limit_freq"] = 7
    custom["rev_limit_amp"] = 144
    preferences.PATH.write_text(json.dumps({
        "version": "2",
        "active_profile": "Custom",
        "profiles": {"Custom": custom},
        "globals": {},
    }), encoding="utf-8")

    settings = Settings()
    preferences.load(settings)

    assert settings.rev_limit_freq == 7
    assert settings.rev_limit_amp == 144
    assert settings.grip_redline_freq == 10
    assert settings.grip_redline_amp == 220


def test_r3_prerelease_defaults_split_into_trigger_and_new_grip_defaults(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")
    custom = _without_grip_redline_fields(EXPECTED)
    custom["rev_limit_freq"] = 10
    custom["rev_limit_amp"] = 96
    preferences.PATH.write_text(json.dumps({
        "version": "3",
        "active_profile": "Custom",
        "profiles": {"Custom": custom},
        "globals": {},
    }), encoding="utf-8")

    settings = Settings()
    preferences.load(settings)

    raw = json.loads(preferences.PATH.read_text(encoding="utf-8"))
    snapshot = raw["profiles"]["Custom"]
    assert settings.rev_limit_freq == 30
    assert settings.rev_limit_amp == 12
    assert settings.grip_redline_freq == 10
    assert settings.grip_redline_amp == 220
    assert snapshot["rev_limit_freq"] == 30
    assert snapshot["rev_limit_amp"] == 12
    assert snapshot["grip_redline_freq"] == 10
    assert snapshot["grip_redline_amp"] == 220


def test_r3_prerelease_custom_values_are_preserved_and_copied_once(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")
    custom = _without_grip_redline_fields(EXPECTED)
    custom["enable_rev_limiter"] = False
    custom["rev_limit_freq"] = 7
    custom["rev_limit_amp"] = 144
    preferences.PATH.write_text(json.dumps({
        "version": "3",
        "active_profile": "Custom",
        "profiles": {"Custom": custom},
        "globals": {},
    }), encoding="utf-8")

    first = Settings()
    preferences.load(first)
    second = Settings()
    preferences.load(second)

    raw = json.loads(preferences.PATH.read_text(encoding="utf-8"))
    snapshot = raw["profiles"]["Custom"]
    assert second.enable_rev_limiter is False
    assert second.enable_grip_redline_haptics is False
    assert second.rev_limit_freq == 7
    assert second.rev_limit_amp == 144
    assert second.grip_redline_freq == 7
    assert second.grip_redline_amp == 144
    assert snapshot["rev_limit_freq"] == 7
    assert snapshot["grip_redline_freq"] == 7


def test_named_profile_preserves_explicit_r3_grip_values_across_reloads(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")
    custom = dict(EXPECTED)
    custom.update({
        "enable_grip_redline_haptics": True,
        "grip_redline_gain": 1.2,
        "enable_grip_gear_shift_haptics": True,
        "grip_gear_shift_strength": 0.55,
        "grip_gear_shift_duration_ms": 75.0,
    })
    preferences.PATH.write_text(json.dumps({
        "version": "3",
        "active_profile": "Custom",
        "profiles": {"Custom": custom},
        "globals": {},
    }), encoding="utf-8")

    first = Settings()
    preferences.load(first)
    second = Settings()
    preferences.load(second)

    assert second.enable_grip_redline_haptics is True
    assert second.grip_redline_gain == 1.2
    assert second.enable_grip_gear_shift_haptics is True
    assert second.grip_gear_shift_strength == 0.55
    assert second.grip_gear_shift_duration_ms == 75.0
