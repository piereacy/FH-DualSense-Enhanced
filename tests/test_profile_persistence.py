import base64
import json
import math
from pathlib import Path
import zlib

import pytest

from modules.config import preferences, profiles
from modules.config.profile_session import ProfileSession
from modules.config.settings import Settings


def test_network_and_exit_timing_settings_are_global():
    assert {
        "udp_host",
        "udp_port",
        "udp_timeout",
        "game_poll_interval_s",
        "telemetry_lost_exit_s",
    } <= preferences.GLOBAL_FIELDS


def _paths(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    monkeypatch.setattr(preferences, "PATH", tmp_path / "user_preferences.json")


def test_default_profile_persists_across_restart(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setattr(preferences, "detect_system_language", lambda: "zh")
    settings = Settings()
    preferences.load(settings)
    settings.brake_max_force = 3
    settings.preferred_forza_game = "fh4"
    settings.preferred_forza_platform = "xbox_app"
    settings.fh4_install_path = "D:/Steam/FH4"
    settings.fh6_xbox_install_path = "G:/Xbox/FH6"
    assert preferences.save(settings)

    reloaded = Settings()
    preferences.load(reloaded)

    assert reloaded.brake_max_force == 3
    assert reloaded.language == "zh"
    assert reloaded.preferred_forza_game == "fh4"
    assert reloaded.preferred_forza_platform == "xbox_app"
    assert reloaded.fh4_install_path == "D:/Steam/FH4"
    assert reloaded.fh6_xbox_install_path == "G:/Xbox/FH6"


def test_original_profile_is_seeded_from_upstream_v162_defaults(
    tmp_path, monkeypatch
):
    _paths(tmp_path, monkeypatch)
    settings = Settings()

    preferences.load(settings)
    store = profiles.load_profiles()
    original = store["profiles"][preferences.ORIGINAL_PROFILE_NAME]

    assert profiles.list_profile_names(store)[:2] == ["Default", "Original"]
    assert original["brake_deadzone"] == 50
    assert original["brake_baseline_force"] == 18
    assert original["brake_max_force"] == 80
    assert original["throttle_max_force"] == 8
    assert original["enable_rev_limiter"] is True
    assert original["enable_gear_shift"] is True
    assert original["gear_shift_amp"] == 255
    assert original["enable_body_haptics"] is True

    assert profiles.apply_profile("Original", settings)
    assert settings.brake_max_force == 80
    assert settings.throttle_max_force == 8
    assert settings.enable_body_haptics is True
    assert profiles.delete_profile("Original") is False
    assert profiles.rename_profile("Original", "Classic") == ""

    raw = json.loads(preferences.PATH.read_text(encoding="utf-8"))
    raw["profiles"]["Original"]["brake_max_force"] = 1
    raw["profiles"]["Original"]["enable_body_haptics"] = False
    preferences.PATH.write_text(json.dumps(raw), encoding="utf-8")

    preferences.load(Settings())
    refreshed = profiles.load_profiles()["profiles"]["Original"]
    assert refreshed["brake_max_force"] == 80
    assert refreshed["enable_body_haptics"] is True

    assert profiles.apply_profile("Original", settings)
    assert settings.brake_max_force == 80


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


def test_r7_reconnect_migration_runs_once_and_preserves_driving_settings(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    raw = {
        "version": "6",
        "active_profile": "Default",
        "profiles": {
            "Default": {
                "brake_max_force": 3,
                "body_haptics_intensity": 0.77,
            }
        },
        "globals": {"enable_reconnect": False, "reconnect_interval_s": 9.0},
    }
    preferences.PATH.write_text(json.dumps(raw), encoding="utf-8")

    migrated = Settings()
    preferences.load(migrated)

    assert migrated.enable_reconnect is True
    assert migrated.reconnect_interval_s == 9.0
    assert migrated.brake_max_force == 3
    assert migrated.body_haptics_intensity == 0.77

    migrated.enable_reconnect = False
    assert preferences.save(migrated)
    reloaded = Settings()
    preferences.load(reloaded)
    saved = json.loads(preferences.PATH.read_text(encoding="utf-8"))

    assert reloaded.enable_reconnect is False
    assert saved["migrations"][preferences.R7_RECONNECT_MIGRATION] is True


def test_factory_restore_resets_all_fields_and_preserves_named_profiles(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    monkeypatch.setattr(preferences, "detect_system_language", lambda: "zh_tw")
    settings = Settings()
    preferences.load(settings)
    settings.brake_max_force = 3
    settings.minimize_to_tray = False
    settings.preferred_forza_game = "fh5"
    settings.preferred_forza_platform = "xbox_app"
    settings.fh5_install_path = "E:/Steam/FH5"
    settings.fh6_xbox_install_path = "G:/Xbox/FH6"
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
    assert settings.preferred_forza_game == "fh6"
    assert settings.preferred_forza_platform == "steam"
    assert settings.fh4_install_path == ""
    assert settings.fh5_install_path == ""
    assert settings.fh6_install_path == ""
    assert settings.fh6_xbox_install_path == ""
    assert settings.enable_reconnect is True
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


def test_new_and_imported_profile_names_are_bounded_and_drop_control_characters(
    tmp_path, monkeypatch
):
    _paths(tmp_path, monkeypatch)
    settings = Settings()
    preferences.load(settings)

    saved = profiles.save_profile("  Race\n\x00" + "x" * 100, settings)

    payload = json.dumps(["\tImported\r" + "y" * 100, {}]).encode("utf-8")
    code = profiles.SHARE_PREFIX + base64.urlsafe_b64encode(
        zlib.compress(payload)
    ).rstrip(b"=").decode("ascii")
    imported = profiles.import_profile(code)

    assert saved.startswith("Race") and len(saved) == profiles.MAX_PROFILE_NAME
    assert imported.startswith("Imported") and len(imported) == profiles.MAX_PROFILE_NAME
    assert all(ord(character) >= 32 for character in saved + imported)


@pytest.mark.parametrize(
    "bad_field,bad_value",
    [
        ("profiles", []),
        ("profiles", {"Default": []}),
        ("active_profile", 7),
        ("globals", "invalid"),
        ("migrations", []),
    ],
)
def test_malformed_nested_preferences_raise_a_recoverable_error(
    tmp_path,
    monkeypatch,
    bad_field,
    bad_value,
):
    _paths(tmp_path, monkeypatch)
    raw = {
        "active_profile": "Default",
        "profiles": {"Default": {}},
        "globals": {},
        bad_field: bad_value,
    }
    preferences.PATH.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(preferences.PreferencesError):
        preferences.load(Settings())


def test_invalid_boolean_and_non_finite_numbers_do_not_poison_settings(
    tmp_path,
    monkeypatch,
):
    _paths(tmp_path, monkeypatch)
    raw = {
        "active_profile": "Default",
        "profiles": {
            "Default": {
                "enable_abs": "false",
                "brake_curve": float("nan"),
                "idle_period_s": float("inf"),
            }
        },
        "globals": {},
    }
    preferences.PATH.write_text(json.dumps(raw), encoding="utf-8")
    settings = Settings()

    preferences.load(settings)

    assert settings.enable_abs is Settings().enable_abs
    assert math.isfinite(settings.brake_curve)
    assert settings.brake_curve == Settings().brake_curve
    assert math.isfinite(settings.idle_period_s)
    assert settings.idle_period_s == Settings().idle_period_s


def test_background_save_never_overwrites_preferences_corrupted_after_startup(
    tmp_path,
    monkeypatch,
):
    _paths(tmp_path, monkeypatch)
    corrupted = b'{"profiles": '
    preferences.PATH.write_bytes(corrupted)

    assert preferences.save(Settings()) is False
    assert profiles.save_profile("profile1", Settings()) == ""
    assert preferences.PATH.read_bytes() == corrupted


def test_reset_never_deletes_preferences_when_verified_backup_fails(
    tmp_path,
    monkeypatch,
):
    _paths(tmp_path, monkeypatch)
    original = b'{"profiles": '
    preferences.PATH.write_bytes(original)
    real_write_bytes = Path.write_bytes

    def fail_backup(self, data):
        if self.name.startswith(".user_preferences.json.bak."):
            raise OSError("synthetic backup failure")
        return real_write_bytes(self, data)

    monkeypatch.setattr(Path, "write_bytes", fail_backup)

    with pytest.raises(preferences.PreferencesError):
        preferences.reset_file()

    assert preferences.PATH.read_bytes() == original
    assert not preferences.PATH.with_suffix(".json.bak").exists()


def test_imported_profile_invalid_values_fall_back_to_built_in_defaults(
    tmp_path,
    monkeypatch,
):
    _paths(tmp_path, monkeypatch)
    preferences.load(Settings())
    payload = json.dumps(
        [
            "Community",
            {
                "enable_abs": "false",
                "brake_curve": "not-a-number",
                "brake_max_force": 3,
            },
        ],
        separators=(",", ":"),
    ).encode("utf-8")
    body = base64.urlsafe_b64encode(zlib.compress(payload)).rstrip(b"=").decode("ascii")

    imported = profiles.import_profile(profiles.SHARE_PREFIX + body)
    snapshot = profiles.load_profiles()["profiles"][imported]

    assert imported == "Community"
    assert snapshot["enable_abs"] is Settings().enable_abs
    assert snapshot["brake_curve"] == Settings().brake_curve
    assert snapshot["brake_max_force"] == 3
