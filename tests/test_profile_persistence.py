import json

from modules.config import preferences, profiles
from modules.config.profile_session import ProfileSession
from modules.config.settings import Settings


def _paths(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")


def test_default_profile_persists_across_restart(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setattr(preferences, "detect_system_language", lambda: "zh")
    settings = Settings()
    preferences.load(settings)
    settings.brake_max_force = 3
    assert preferences.save(settings)

    reloaded = Settings()
    preferences.load(reloaded)

    assert reloaded.brake_max_force == 3
    assert reloaded.language == "zh"


def test_first_run_detects_language_but_existing_config_keeps_user_choice(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setattr(preferences, "detect_system_language", lambda: "ja")
    first = Settings()
    preferences.load(first)
    assert first.language == "ja"
    first.language = "de"
    assert preferences.save(first)

    monkeypatch.setattr(preferences, "detect_system_language", lambda: "zh")
    second = Settings()
    preferences.load(second)
    assert second.language == "de"


def test_factory_restore_resets_all_fields_and_preserves_named_profiles(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setattr(preferences, "detect_system_language", lambda: "zh_tw")
    settings = Settings()
    preferences.load(settings)
    settings.brake_max_force = 3
    settings.minimize_to_tray = False
    assert preferences.save(settings)
    assert profiles.save_profile("Track", settings) == "Track"
    settings.brake_max_force = 2
    settings.minimize_to_tray = False
    assert preferences.save(settings)

    assert preferences.restore_factory(settings)

    store = profiles.load_profiles()
    assert store["active"] == "Default"
    assert "Track" in store["profiles"]
    assert settings.brake_max_force == Settings().brake_max_force
    assert settings.minimize_to_tray is Settings().minimize_to_tray
    assert settings.language == "zh_tw"
    assert preferences.PATH.with_suffix(".json.bak").exists()


def test_profile_session_only_prompts_for_default_profile_tuning(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    settings = Settings()
    preferences.load(settings)
    session = ProfileSession(settings)

    settings.minimize_to_tray = False
    preferences.save(settings)
    assert not session.needs_named_save(settings)

    settings.brake_max_force = 3
    preferences.save(settings)
    assert session.needs_named_save(settings)

    session.accept_current_default(settings)
    assert not session.needs_named_save(settings)
    assert profiles.save_profile("Track", settings) == "Track"
    assert not session.needs_named_save(settings)


def test_profile_session_does_not_treat_new_default_fields_as_user_edits(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    settings = Settings()
    preferences.load(settings)
    raw = json.loads(preferences.PATH.read_text(encoding="utf-8"))
    raw["profiles"]["Default"].pop("enable_tachometer_lightbar")
    preferences.PATH.write_text(json.dumps(raw), encoding="utf-8")

    reloaded = Settings()
    preferences.load(reloaded)

    assert not ProfileSession(reloaded).needs_named_save(reloaded)


def test_next_profile_name_uses_first_available_number(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    raw = {
        "active_profile": "Default",
        "profiles": {"Default": {}, "profile1": {}, "profile3": {}},
        "globals": {},
    }
    preferences.PATH.write_text(json.dumps(raw), encoding="utf-8")

    assert profiles.next_profile_name() == "profile2"
