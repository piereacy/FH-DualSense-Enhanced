import base64
import json
import math
from pathlib import Path
import zlib

import pytest

from modules.config import preferences, profiles
from modules.config.profile_session import ProfileSession
from modules.config.settings import Settings
from modules.xinput.mapping import MAPPING_SETTING_FIELDS
from modules.xinput.gyro import GYRO_SETTING_FIELDS


def test_network_and_exit_timing_settings_are_global():
    assert {
        "udp_host",
        "udp_port",
        "udp_timeout",
        "game_poll_interval_s",
        "telemetry_lost_exit_s",
    } <= preferences.GLOBAL_FIELDS


def test_experimental_xinput_mapping_is_global_not_profile_tuning():
    assert "enable_custom_xinput_mapping" in preferences.GLOBAL_FIELDS
    assert "enable_hidhide" in preferences.GLOBAL_FIELDS
    assert MAPPING_SETTING_FIELDS <= preferences.GLOBAL_FIELDS
    assert GYRO_SETTING_FIELDS <= preferences.GLOBAL_FIELDS


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
    settings.enable_custom_xinput_mapping = True
    settings.enable_xinput_gyro = True
    settings.enable_hidhide = True
    settings.xinput_mapping_cross = "y"
    settings.xinput_gyro_mode = "deflection"
    settings.xinput_gyro_output_stick = "left"
    assert preferences.save(settings)

    reloaded = Settings()
    preferences.load(reloaded)

    assert reloaded.brake_max_force == 3
    assert reloaded.language == "zh"
    assert reloaded.preferred_forza_game == "fh4"
    assert reloaded.preferred_forza_platform == "xbox_app"
    assert reloaded.fh4_install_path == "D:/Steam/FH4"
    assert reloaded.fh6_xbox_install_path == "G:/Xbox/FH6"
    assert reloaded.enable_custom_xinput_mapping is True
    assert reloaded.enable_xinput_gyro is True
    assert reloaded.enable_hidhide is True
    assert reloaded.xinput_mapping_cross == "y"
    assert reloaded.xinput_gyro_mode == "deflection"
    assert reloaded.xinput_gyro_output_stick == "left"


def test_xbox_app_preferences_force_hidhide_on_save_and_upgrade(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    settings = Settings(preferred_forza_platform="xbox_app", enable_hidhide=False)
    assert preferences.save(settings)
    assert settings.enable_hidhide is True

    raw = json.loads(preferences.PATH.read_text(encoding="utf-8"))
    raw["globals"]["enable_hidhide"] = False
    preferences.PATH.write_text(json.dumps(raw), encoding="utf-8")
    loaded = Settings()
    preferences.load(loaded)
    assert loaded.preferred_forza_platform == "xbox_app"
    assert loaded.enable_hidhide is True
    stored = json.loads(preferences.PATH.read_text(encoding="utf-8"))
    assert stored["globals"]["enable_hidhide"] is True


def test_original_profile_is_seeded_from_upstream_v162_defaults(
    tmp_path, monkeypatch
):
    _paths(tmp_path, monkeypatch)
    settings = Settings()

    preferences.load(settings)
    store = profiles.load_profiles()
    original = store["profiles"][preferences.ORIGINAL_PROFILE_NAME]

    assert profiles.list_profile_names(store)[:3] == [
        "Default",
        "Default before R11",
        "Original",
    ]
    historical = store["profiles"][preferences.DEFAULT_BEFORE_R11_PROFILE_NAME]
    assert historical["brake_max_force"] == 5
    assert historical["enable_abs"] is False
    assert original["brake_deadzone"] == 50
    assert original["brake_baseline_force"] == 18
    assert original["brake_max_force"] == 80
    assert original["throttle_max_force"] == 8
    assert original["enable_rev_limiter"] is True
    assert original["enable_gear_shift"] is True
    assert original["gear_shift_amp"] == 255
    assert original["enable_body_haptics"] is True
    assert original["road_haptics_intensity"] == 0.7
    assert original["enable_abs"] is False

    assert profiles.apply_profile("Original", settings)
    assert settings.brake_max_force == 80
    assert settings.throttle_max_force == 8
    assert settings.enable_body_haptics is True
    assert profiles.delete_profile("Original") is False
    assert profiles.rename_profile("Original", "Classic") == ""
    assert profiles.delete_profile("Default before R11") is False
    assert profiles.rename_profile("Default before R11", "Classic") == ""

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


def test_existing_profiles_backfill_throttle_end_wall_off(tmp_path, monkeypatch):
    _paths(tmp_path, monkeypatch)
    preferences.PATH.write_text(json.dumps({
        "version": "9",
        "active_profile": "Default",
        "profiles": {
            "Default": {"throttle_max_force": 7},
            "Legacy": {"throttle_max_force": 3},
        },
        "globals": {},
        "migrations": {preferences.R11_DEFAULT_PROFILE_MIGRATION: True},
    }), encoding="utf-8")

    settings = Settings()
    settings.enable_throttle_end_wall = True
    preferences.load(settings)
    saved = json.loads(preferences.PATH.read_text(encoding="utf-8"))

    assert settings.enable_throttle_end_wall is False
    assert saved["profiles"]["Default"]["enable_throttle_end_wall"] is False
    assert saved["profiles"]["Legacy"]["enable_throttle_end_wall"] is False

    settings.enable_throttle_end_wall = True
    assert profiles.apply_profile("Legacy", settings)
    assert settings.enable_throttle_end_wall is False
    assert settings.throttle_max_force == 3


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
        "migrations": {preferences.R11_DEFAULT_PROFILE_MIGRATION: True},
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


def _old_redline_timing() -> dict[str, float]:
    return {
        "rev_limit_ratio": 0.93,
        "grip_redline_ratio": 0.93,
        "grip_redline_release_ratio": 0.90,
        "tachometer_flash_ratio": 0.93,
    }


def test_r8_redline_timing_migrates_only_untouched_default_once(
    tmp_path,
    monkeypatch,
):
    _paths(tmp_path, monkeypatch)
    raw = {
        "version": "7",
        "active_profile": "Default",
        "profiles": {
            "Default": {**_old_redline_timing(), "brake_max_force": 3},
            "Track": _old_redline_timing(),
        },
        "globals": {},
        "migrations": {preferences.R11_DEFAULT_PROFILE_MIGRATION: True},
    }
    preferences.PATH.write_text(json.dumps(raw), encoding="utf-8")

    migrated = Settings()
    preferences.load(migrated)
    saved = json.loads(preferences.PATH.read_text(encoding="utf-8"))

    assert migrated.rev_limit_ratio == 0.95
    assert migrated.grip_redline_ratio == 0.95
    assert migrated.grip_redline_release_ratio == 0.92
    assert migrated.tachometer_flash_ratio == 0.95
    assert migrated.brake_max_force == 3
    assert {
        key: saved["profiles"]["Track"][key]
        for key in _old_redline_timing()
    } == _old_redline_timing()
    assert (
        saved["migrations"][preferences.R8_REDLINE_TIMING_MIGRATION]
        is True
    )

    for key, value in _old_redline_timing().items():
        setattr(migrated, key, value)
    assert preferences.save(migrated)

    reloaded = Settings()
    preferences.load(reloaded)
    assert {
        key: getattr(reloaded, key)
        for key in _old_redline_timing()
    } == _old_redline_timing()


def test_r8_redline_timing_preserves_a_customized_default_group(
    tmp_path,
    monkeypatch,
):
    _paths(tmp_path, monkeypatch)
    customized = {**_old_redline_timing(), "rev_limit_ratio": 0.91}
    raw = {
        "version": "7",
        "active_profile": "Default",
        "profiles": {"Default": customized},
        "globals": {},
        "migrations": {preferences.R11_DEFAULT_PROFILE_MIGRATION: True},
    }
    preferences.PATH.write_text(json.dumps(raw), encoding="utf-8")

    loaded = Settings()
    preferences.load(loaded)
    saved = json.loads(preferences.PATH.read_text(encoding="utf-8"))

    assert {
        key: getattr(loaded, key)
        for key in customized
    } == customized
    assert (
        saved["migrations"][preferences.R8_REDLINE_TIMING_MIGRATION]
        is True
    )


def test_r11_migration_installs_new_default_and_preserves_previous_default(
    tmp_path,
    monkeypatch,
):
    _paths(tmp_path, monkeypatch)
    previous = preferences.default_before_r11_profile_fields()
    previous["brake_max_force"] = 4
    raw = {
        "version": "10",
        "active_profile": "Default",
        "profiles": {"Default": previous},
        "globals": {},
        "migrations": {
            preferences.R7_RECONNECT_MIGRATION: True,
            preferences.R8_REDLINE_TIMING_MIGRATION: True,
        },
    }
    preferences.PATH.write_text(json.dumps(raw), encoding="utf-8")

    settings = Settings()
    preferences.load(settings)
    saved = json.loads(preferences.PATH.read_text(encoding="utf-8"))

    assert settings.brake_max_force == 2
    assert settings.enable_abs is True
    assert saved["profiles"]["Default"] == preferences._profile_fields(Settings())
    assert saved["profiles"]["Default before R11"] == previous
    assert saved["migrations"][preferences.R11_DEFAULT_PROFILE_MIGRATION] is True


def test_r11_migration_preserves_named_active_profile_and_runs_only_once(
    tmp_path,
    monkeypatch,
):
    _paths(tmp_path, monkeypatch)
    previous = preferences.default_before_r11_profile_fields()
    track = dict(previous)
    track.update({"brake_max_force": 3, "body_haptics_intensity": 0.77})
    raw = {
        "version": "10",
        "active_profile": "Track",
        "profiles": {"Default": previous, "Track": track},
        "globals": {},
        "migrations": {
            preferences.R7_RECONNECT_MIGRATION: True,
            preferences.R8_REDLINE_TIMING_MIGRATION: True,
        },
    }
    preferences.PATH.write_text(json.dumps(raw), encoding="utf-8")

    settings = Settings()
    preferences.load(settings)
    saved = json.loads(preferences.PATH.read_text(encoding="utf-8"))

    assert saved["active_profile"] == "Track"
    assert saved["profiles"]["Track"] == track
    assert settings.brake_max_force == 3
    assert settings.body_haptics_intensity == 0.77

    saved["profiles"]["Default"]["brake_max_force"] = 1
    saved["profiles"]["Default before R11"]["brake_max_force"] = 6
    preferences.PATH.write_text(json.dumps(saved), encoding="utf-8")
    preferences.load(Settings())
    reloaded = json.loads(preferences.PATH.read_text(encoding="utf-8"))

    assert reloaded["profiles"]["Default"]["brake_max_force"] == 1
    assert reloaded["profiles"]["Default before R11"]["brake_max_force"] == 6


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
    settings.enable_custom_xinput_mapping = True
    settings.enable_xinput_gyro = True
    settings.xinput_mapping_touchpad_right = "guide"
    settings.xinput_gyro_mode = "camera"
    assert preferences.save(settings)
    assert profiles.save_profile("Track", settings) == "Track"
    settings.brake_max_force = 2
    settings.minimize_to_tray = False
    assert preferences.save(settings)

    assert preferences.restore_factory(settings)

    store = profiles.load_profiles()
    assert store["active"] == "Default"
    assert "Track" in store["profiles"]
    assert profiles.list_profile_names(store)[:3] == [
        "Default",
        "Default before R11",
        "Original",
    ]
    assert store["profiles"]["Default before R11"]["brake_max_force"] == 5
    assert store["profiles"]["Default before R11"]["enable_abs"] is False
    assert settings.brake_max_force == Settings().brake_max_force
    assert settings.minimize_to_tray is Settings().minimize_to_tray
    assert settings.preferred_forza_game == "fh6"
    assert settings.preferred_forza_platform == "steam"
    assert settings.fh4_install_path == ""
    assert settings.fh5_install_path == ""
    assert settings.fh6_install_path == ""
    assert settings.fh6_xbox_install_path == ""
    assert settings.enable_custom_xinput_mapping is False
    assert settings.enable_xinput_gyro is False
    assert settings.xinput_mapping_touchpad_right == "start"
    assert settings.xinput_gyro_mode == "deflection"
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
