"""Persist Settings as the active profile inside user_preferences.json.

File layout:
    {
      "version": "x.y.z",
      "active_profile": "Default",
      "profiles": {
        "Default":           { ...flat Settings fields... },
        "Default before R11": { ...previous defaults... },
        "Sport":             { ... }
      }
    }

On first launch a "Default" profile is seeded from the class defaults.
save(s) merges local changes into the profile loaded by that Settings instance.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
import json
import logging
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid
from . import paths
from .system_language import detect_system_language

log = logging.getLogger("fhds")

_DATA = paths.DATA
PATH = _DATA / "user_preferences.json"
PYPROJECT = paths.PYPROJECT
DEFAULT_PROFILE_NAME = "Default"
DEFAULT_BEFORE_R11_PROFILE_NAME = "Default before R11"
ORIGINAL_PROFILE_NAME = "Original"
BUILTIN_PROFILE_NAMES = frozenset({
    DEFAULT_PROFILE_NAME,
    DEFAULT_BEFORE_R11_PROFILE_NAME,
    ORIGINAL_PROFILE_NAME,
})
R7_RECONNECT_MIGRATION = "r7_enable_reconnect_default"
R8_REDLINE_TIMING_MIGRATION = "r8_redline_timing_defaults"
R11_DEFAULT_PROFILE_MIGRATION = "r11_default_profile_from_33"

_DEFAULT_BEFORE_R11_OVERRIDES = {
    "abs_amp": 90,
    "abs_amp_min": 32,
    "abs_brake_threshold": 255,
    "abs_combined_slip_threshold": 0.3,
    "abs_combined_slip_weight": 0.35,
    "abs_freq": 60,
    "abs_hold_ms": 100.0,
    "abs_min_speed_kmh": 6.0,
    "abs_sensitivity": 1.0,
    "abs_slip_ratio_threshold": 0.3,
    "body_haptics_intensity": 0.5,
    "brake_curve": 5.0,
    "brake_max_force": 5,
    "collision_background_duck": 0.2,
    "collision_haptics_rebound_ratio": 0.45,
    "collision_haptics_weak_side_ratio": 0.35,
    "collision_trigger_amp": 220,
    "collision_trigger_duration_ms": 90.0,
    "collision_trigger_freq": 2,
    "enable_abs": False,
    "enable_grip_gear_shift_haptics": False,
    "enable_idle_buzz": True,
    "enable_tachometer_lightbar": False,
    "engine_haptics_intensity": 0.5,
    "gear_shift_amp": 10,
    "gear_shift_duration_ms": 100.0,
    "gear_shift_freq": 10,
    "grip_gear_shift_duration_ms": 100.0,
    "grip_gear_shift_strength": 0.8,
    "grip_redline_amp": 220,
    "grip_redline_attack_duration_ms": 120.0,
    "grip_redline_attack_strength": 0.65,
    "grip_redline_background_duck": 0.3,
    "grip_redline_duty_cycle": 0.7,
    "grip_redline_gain": 1.5,
    "grip_redline_low_ratio": 0.45,
    "grip_redline_ratio": 0.95,
    "grip_redline_release_ratio": 0.92,
    "grip_redline_right": False,
    "idle_amp_high": 60,
    "impact_haptics_intensity": 2.0,
    "rev_limit_amp": 12,
    "rev_limit_freq": 30,
    "rev_limit_hold_ms": 120.0,
    "rev_limit_ratio": 0.95,
    "road_haptics_intensity": 0.7,
    "slip_haptics_threshold": 0.8,
    "tachometer_brightness": 0.7,
    "tachometer_flash_rate_hz": 10.0,
    "tachometer_flash_ratio": 0.95,
    "tachometer_start_ratio": 0.7,
    "throttle_curve": 5.0,
    "throttle_max_force": 1,
    "wheelspin_amp": 90,
    "wheelspin_attack_ms": 40.0,
    "wheelspin_burnout_rotation_full_scale": 120.0,
    "wheelspin_burnout_rotation_threshold": 30.0,
    "wheelspin_dirt_freq_max": 70,
    "wheelspin_dirt_freq_min": 30,
    "wheelspin_g_damping": 0.25,
    "wheelspin_gravel_freq_max": 30,
    "wheelspin_gravel_freq_min": 12,
    "wheelspin_hysteresis": 0.15,
    "wheelspin_release_ms": 125.0,
    "wheelspin_sensitivity": 1.0,
    "wheelspin_slip_full_scale": 3.0,
    "wheelspin_tarmac_freq_max": 180,
    "wheelspin_tarmac_freq_min": 90,
    "wheelspin_water_freq_max": 150,
    "wheelspin_water_freq_min": 80,
}

# System fields - shared across profiles and preserved across launches.
# Everything else lives in the active profile.
GLOBAL_FIELDS = frozenset({
    "udp_host",
    "udp_port",
    "udp_timeout",
    "udp_forward",
    "udp_forward_to",
    "enable_reconnect",
    "reconnect_interval_s",
    "enable_startup_pulse",
    "startup_pulse_force",
    "exit_on_game_close",
    "minimize_to_tray",
    "game_poll_interval_s",
    "telemetry_lost_exit_s",
    "check_for_updates",
    "auto_download_updates",
    "preferred_forza_platform",
    "preferred_forza_game",
    "fh4_install_path",
    "fh5_install_path",
    "fh6_install_path",
    "fh6_xbox_install_path",
    "enable_hidhide",
    "enable_custom_xinput_mapping",
    "xinput_mapping_cross",
    "xinput_mapping_circle",
    "xinput_mapping_square",
    "xinput_mapping_triangle",
    "xinput_mapping_l1",
    "xinput_mapping_r1",
    "xinput_mapping_create",
    "xinput_mapping_options",
    "xinput_mapping_l3",
    "xinput_mapping_r3",
    "xinput_mapping_ps",
    "xinput_mapping_dpad_up",
    "xinput_mapping_dpad_down",
    "xinput_mapping_dpad_left",
    "xinput_mapping_dpad_right",
    "xinput_mapping_touchpad_left",
    "xinput_mapping_touchpad_right",
    "enable_xinput_gyro",
    "xinput_gyro_mode",
    "xinput_gyro_output_stick",
    "xinput_gyro_activation",
    "xinput_gyro_horizontal_axis",
    "xinput_gyro_sensitivity_dps",
    "xinput_gyro_deflection_angle",
    "xinput_gyro_deadzone_dps",
    "xinput_gyro_smoothing_ms",
    "xinput_gyro_vertical_enabled",
    "xinput_gyro_invert_horizontal",
    "xinput_gyro_invert_vertical",
    "language",
    "controller_lock_serial",
    "use_dsx",
    "dsx_host",
    "dsx_port",
})

_SIMPLE = (bool, int, float, str)


class PreferencesError(Exception):
    """Raised when user_preferences.json cannot be parsed or is incompatible."""


_MUTATION_LOCK = threading.RLock()
_LOCK_STATE = threading.local()
_RAISE = object()
_MISSING = object()


@contextmanager
def _transaction():
    """Serialize each complete read/modify/write, including nested profile calls."""
    with _MUTATION_LOCK:
        if getattr(_LOCK_STATE, "held", False):
            yield
            return
        PATH.parent.mkdir(parents=True, exist_ok=True)
        # Keep the lock file: unlinking it would allow two different locked inodes.
        with PATH.with_suffix(PATH.suffix + ".lock").open("a+b") as stream:
            if os.name == "nt":
                import msvcrt

                if stream.tell() == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                def acquire():
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                def release():
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                def acquire():
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                def release():
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            deadline = time.monotonic() + 2.0
            while True:
                try:
                    acquire()
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise PreferencesError("Preferences are busy in another instance.") from None
                    time.sleep(0.02)
            _LOCK_STATE.held = True
            try:
                yield
            finally:
                _LOCK_STATE.held = False
                release()


def _serialized(failure=_RAISE):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            try:
                with _transaction():
                    return function(*args, **kwargs)
            except (OSError, PreferencesError) as exc:
                if failure is _RAISE:
                    if isinstance(exc, PreferencesError):
                        raise
                    raise PreferencesError(f"Could not access preferences: {exc}") from exc
                log.warning("Could not update preferences: %s", exc)
                return failure
        return wrapped
    return decorate


@dataclass
class _SettingsState:
    path: Path
    name: str
    profile: dict
    profile_disk: dict
    globals: dict
    globals_disk: dict


def _settings_state(s) -> _SettingsState | None:
    state = getattr(s, "_preferences_state", None)
    return state if isinstance(state, _SettingsState) and state.path == PATH.resolve() else None


def pending_changes(s) -> tuple[bool, bool]:
    """Return unsaved tuning/application fields for this loaded instance."""
    state = _settings_state(s)
    if state is None:
        return False, False
    return _profile_fields(s) != state.profile, _global_fields(s) != state.globals


def save_pending(s) -> bool:
    """Retry failed autosaves before a caller discards the live settings."""
    return not any(pending_changes(s)) or save(s)


def save_failure_message(s) -> str:
    if pending_changes(s)[1]:
        return (
            "Application settings could not be saved. Your changes are still open. "
            "Check file access or restore conflicting application settings before retrying. "
            "Saving a named profile only preserves tuning."
        )
    return (
        "Settings could not be saved. Your changes are still open. "
        "Check file access or save a named profile before retrying."
    )


def _bind_loaded(s, raw: dict) -> None:
    name = raw["active_profile"]
    s._preferences_state = _SettingsState(
        PATH.resolve(), name, _profile_fields(s), dict(raw["profiles"][name]),
        _global_fields(s), dict(raw["globals"]),
    )


def _bind_profile(s, name: str, snapshot: dict, raw: dict) -> None:
    state = _settings_state(s)
    if state is None:
        defaults = type(s)()
        _apply_snap(defaults, raw.get("globals", {}), _global_fields(defaults))
        state = _SettingsState(
            PATH.resolve(), name, {}, {}, _global_fields(defaults),
            dict(raw.get("globals", {})),
        )
        s._preferences_state = state
    state.name = name
    state.profile = _profile_fields(s)
    state.profile_disk = dict(snapshot)


def _merge_changes(current: dict, baseline: dict, saved: dict, disk: dict) -> None:
    for key, value in current.items():
        if value == baseline.get(key, _MISSING):
            continue
        external = disk.get(key, _MISSING)
        if external != saved.get(key, _MISSING) and external != value:
            raise PreferencesError(
                f"Setting '{key}' changed in another instance; reload the profile "
                "or save a named copy before retrying."
            )
        disk[key] = value


def _version() -> str:
    try:
        m = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', PYPROJECT.read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    except OSError:
        return ""


def _release_version() -> str:
    """Map the internal PEP 440 package version to the public R release label."""
    version = _version()
    match = re.match(r"^(\d+)", version)
    return f"R{match.group(1)}" if match else ""


def _fields(s) -> dict:
    return {
        k: v for k, v in vars(s).items()
        if not k.startswith("_") and isinstance(v, _SIMPLE)
    }


def _profile_fields(s) -> dict:
    return {k: v for k, v in _fields(s).items() if k not in GLOBAL_FIELDS}


def _global_fields(s) -> dict:
    return {k: v for k, v in _fields(s).items() if k in GLOBAL_FIELDS}


def default_before_r11_profile_fields() -> dict:
    """Current profile schema populated with the pre-R11 defaults."""
    from .settings import Settings

    snapshot = _profile_fields(Settings())
    snapshot.update(_DEFAULT_BEFORE_R11_OVERRIDES)
    return snapshot


def original_profile_fields() -> dict:
    """Current profile schema populated with upstream v1.6.2 defaults."""
    snapshot = default_before_r11_profile_fields()
    snapshot.update({
        "brake_deadzone": 50,
        "brake_baseline_force": 18,
        "brake_max_force": 80,
        "enable_handbrake_bonus": True,
        "handbrake_bonus": 60,
        "abs_brake_threshold": 80,
        "abs_min_speed_kmh": 15.0,
        "abs_slip_ratio_threshold": 1.0,
        "abs_combined_slip_threshold": 1.0,
        "abs_freq_min": 10,
        "abs_freq": 10,
        "abs_amp_min": 20,
        "abs_amp": 20,
        "accel_deadzone": 50,
        "throttle_baseline_force": 1,
        "throttle_max_force": 8,
        "enable_rev_limiter": True,
        "wheelspin_amp": 3,
        "idle_amp_high": 30,
        "enable_gear_shift": True,
        "enable_gear_shift_brake": True,
        "gear_shift_freq": 10,
        "gear_shift_amp": 255,
        "gear_shift_duration_ms": 100.0,
        # Keep the upstream trigger tuning while retaining Enhanced grip output.
        "enable_body_haptics": True,
        "enable_grip_redline_haptics": False,
        "enable_grip_gear_shift_haptics": False,
    })
    return snapshot


def _apply_snap(s, snap: dict, fields: dict) -> None:
    """Copy values from `snap` into `s`, coerced to the type of each field."""
    for k, current in fields.items():
        if k in snap:
            try:
                raw = snap[k]
                if isinstance(current, bool):
                    if isinstance(raw, bool):
                        value = raw
                    elif type(raw) is int and raw in (0, 1):
                        value = bool(raw)
                    else:
                        continue
                elif isinstance(current, int):
                    if isinstance(raw, bool):
                        continue
                    value = int(raw)
                    if not math.isfinite(float(value)):
                        continue
                elif isinstance(current, float):
                    if isinstance(raw, bool):
                        continue
                    value = float(raw)
                    if not math.isfinite(value):
                        continue
                elif isinstance(current, str):
                    if not isinstance(raw, str):
                        continue
                    value = raw
                else:
                    continue
                if k == "tachometer_flash_rate_hz":
                    value = max(0.0, min(24.0, value))
                setattr(s, k, value)
            except (TypeError, ValueError, OverflowError):
                pass


def _validate_raw_shape(data: dict) -> None:
    """Reject valid JSON whose nested preference containers are malformed."""
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict):
        raise PreferencesError(f"{PATH.name}: 'profiles' must be a JSON object.")
    if any(not isinstance(snapshot, dict) for snapshot in profiles.values()):
        raise PreferencesError(
            f"{PATH.name}: every profile must contain a JSON object."
        )
    if "active_profile" in data and not isinstance(data["active_profile"], str):
        raise PreferencesError(f"{PATH.name}: 'active_profile' must be text.")
    for key in ("globals", "migrations"):
        if key in data and not isinstance(data[key], dict):
            raise PreferencesError(f"{PATH.name}: '{key}' must be a JSON object.")


def _read_raw() -> dict:
    """Return the parsed file, {} if missing. Raises PreferencesError on bad JSON."""
    if not PATH.exists():
        return {}
    try:
        text = PATH.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as e:
        raise PreferencesError(f"Could not read {PATH.name}: {e}") from e
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise PreferencesError(f"{PATH.name} is corrupted ({e.msg} at line {e.lineno}).") from e
    if not isinstance(data, dict):
        raise PreferencesError(f"{PATH.name} must contain a JSON object at the top level.")
    _validate_raw_shape(data)
    return data


def _read() -> dict:
    """Tolerant read for mutation paths: corruption is logged then ignored."""
    try:
        return _read_raw()
    except PreferencesError as e:
        log.warning("%s Falling back to empty preferences.", e)
        return {}


def _write(raw: dict) -> bool:
    raw["version"] = _version()
    # MARK: atomic write - avoid corrupt file on power loss / mid-write crash
    # Mutators hold _transaction() through the complete read/modify/write.
    # Unique staging files also avoid collisions with interrupted older saves.
    tmp = PATH.with_name(f".{PATH.name}.{uuid.uuid4().hex}.tmp")
    try:
        _DATA.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        tmp.replace(PATH)
        return True
    except OSError as e:
        log.warning("Could not save preferences: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def _migrate_legacy(raw: dict, s) -> None:
    """Fold root-level Settings keys (v0 flat layout) into a Default profile."""
    field_names = set(_fields(s).keys())
    legacy = {k: v for k, v in raw.items() if k in field_names}
    if not legacy:
        return
    raw.setdefault("profiles", {})
    raw["profiles"].setdefault(DEFAULT_PROFILE_NAME, {}).update(legacy)
    raw["active_profile"] = raw.get("active_profile") or DEFAULT_PROFILE_NAME
    for k in legacy:
        raw.pop(k, None)


def _ensure_active(raw: dict, s) -> dict:
    """Guarantee raw has a profiles dict, valid active_profile, and globals."""
    _migrate_legacy(raw, s)
    raw.setdefault("profiles", {})
    raw.setdefault("active_profile", "")
    raw.setdefault("globals", {})
    if not raw["profiles"]:
        raw["profiles"][DEFAULT_PROFILE_NAME] = _profile_fields(s)
        raw["active_profile"] = DEFAULT_PROFILE_NAME
    raw["profiles"].setdefault(
        DEFAULT_BEFORE_R11_PROFILE_NAME,
        default_before_r11_profile_fields(),
    )
    # Original is a built-in canonical preset, not a user-owned snapshot.
    # Refresh it so upgrades receive corrections to the bundled preset too.
    raw["profiles"][ORIGINAL_PROFILE_NAME] = original_profile_fields()
    # Old profile snapshots predate the explicit R2 end-wall switch. Backfill
    # the safe default instead of inheriting the value from whichever profile
    # happened to be active before a switch.
    for snapshot in raw["profiles"].values():
        snapshot.setdefault("enable_throttle_end_wall", False)
    if raw["active_profile"] not in raw["profiles"]:
        raw["active_profile"] = sorted(raw["profiles"].keys(), key=str.lower)[0]
    # Migrate global fields out of per-profile snapshots (older versions stored
    # them there). Active profile wins so the user's in-use value carries over.
    active_snap = raw["profiles"].get(raw["active_profile"], {})
    for k in GLOBAL_FIELDS:
        if k not in raw["globals"]:
            if k in active_snap:
                raw["globals"][k] = active_snap[k]
            else:
                for prof in raw["profiles"].values():
                    if k in prof:
                        raw["globals"][k] = prof[k]
                        break
        for prof in raw["profiles"].values():
            prof.pop(k, None)
    for k, v in _global_fields(s).items():
        raw["globals"].setdefault(k, v)
    return raw


def _migrate_r7_reconnect_default(raw: dict) -> bool:
    """Enable reconnect once for existing installs, then respect user choice."""
    migrations = raw.setdefault("migrations", {})
    if not isinstance(migrations, dict):
        migrations = {}
        raw["migrations"] = migrations
    if migrations.get(R7_RECONNECT_MIGRATION) is True:
        return False
    raw.setdefault("globals", {})["enable_reconnect"] = True
    migrations[R7_RECONNECT_MIGRATION] = True
    return True


def _migrate_r8_redline_timing_defaults(raw: dict) -> bool:
    """Move an untouched Default profile to the later R8 warning timing."""
    migrations = raw.setdefault("migrations", {})
    if not isinstance(migrations, dict):
        migrations = {}
        raw["migrations"] = migrations
    if migrations.get(R8_REDLINE_TIMING_MIGRATION) is True:
        return False

    migrations[R8_REDLINE_TIMING_MIGRATION] = True
    profiles = raw.get("profiles")
    if not isinstance(profiles, dict):
        return True
    snapshot = profiles.get(DEFAULT_PROFILE_NAME)
    if not isinstance(snapshot, dict):
        return True

    old_defaults = {
        "rev_limit_ratio": 0.93,
        "grip_redline_ratio": 0.93,
        "grip_redline_release_ratio": 0.90,
        "tachometer_flash_ratio": 0.93,
    }
    untouched = all(
        not isinstance(snapshot.get(key, old), bool)
        and isinstance(snapshot.get(key, old), (int, float))
        and math.isclose(
            float(snapshot.get(key, old)),
            old,
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        for key, old in old_defaults.items()
    )
    if untouched:
        snapshot.update({
            "rev_limit_ratio": 0.95,
            "grip_redline_ratio": 0.95,
            "grip_redline_release_ratio": 0.92,
            "tachometer_flash_ratio": 0.95,
        })
    return True


def _migrate_r11_default_profile(raw: dict, s, *, first_run: bool) -> bool:
    """Install the R11 Default once and preserve the prior Default snapshot."""
    migrations = raw.setdefault("migrations", {})
    if not isinstance(migrations, dict):
        migrations = {}
        raw["migrations"] = migrations
    if migrations.get(R11_DEFAULT_PROFILE_MIGRATION) is True:
        return False

    profiles = raw.get("profiles")
    if isinstance(profiles, dict) and not first_run:
        previous = default_before_r11_profile_fields()
        stored_default = profiles.get(DEFAULT_PROFILE_NAME)
        if isinstance(stored_default, dict):
            previous.update(stored_default)
        profiles[DEFAULT_BEFORE_R11_PROFILE_NAME] = previous
        profiles[DEFAULT_PROFILE_NAME] = _profile_fields(type(s)())

    migrations[R11_DEFAULT_PROFILE_MIGRATION] = True
    return True


_GRIP_REDLINE_FIELDS = (
    "enable_grip_redline_haptics",
    "grip_redline_left",
    "grip_redline_right",
    "grip_redline_ratio",
    "grip_redline_release_ratio",
    "grip_redline_freq",
    "grip_redline_amp",
    "grip_redline_gain",
    "grip_redline_duty_cycle",
    "grip_redline_low_ratio",
    "grip_redline_attack_strength",
    "grip_redline_attack_duration_ms",
    "grip_redline_background_duck",
)

_GRIP_GEAR_SHIFT_FIELDS = (
    "enable_grip_gear_shift_haptics",
    "grip_gear_shift_strength",
    "grip_gear_shift_duration_ms",
)


def _migrate_r3_redline_split(raw: dict, s) -> None:
    """Split the prerelease grip pulse back out of the R2 trigger fields.

    R2 profiles keep their trigger tuning and receive fresh grip defaults.
    Local version-3 previews used rev_limit_* for the grip pulse, so their
    values are copied once when the new grip marker field is absent.
    """
    profiles = raw.get("profiles")
    if not isinstance(profiles, dict):
        return
    version = str(raw.get("version", ""))
    defaults = default_before_r11_profile_fields()
    for name, snapshot in profiles.items():
        if name == DEFAULT_PROFILE_NAME or not isinstance(snapshot, dict):
            continue
        if "enable_grip_redline_haptics" in snapshot:
            for field in _GRIP_REDLINE_FIELDS:
                snapshot.setdefault(field, defaults[field])
            continue

        if re.match(r"^3(?:\.|$)", version):
            trigger_freq = snapshot.get("rev_limit_freq", defaults["rev_limit_freq"])
            trigger_amp = snapshot.get("rev_limit_amp", defaults["rev_limit_amp"])
            snapshot["enable_grip_redline_haptics"] = bool(
                snapshot.get("enable_rev_limiter", defaults["enable_rev_limiter"])
            )
            snapshot["grip_redline_ratio"] = snapshot.get(
                "rev_limit_ratio", defaults["grip_redline_ratio"]
            )
            if trigger_freq == 10 and trigger_amp == 96:
                snapshot["rev_limit_freq"] = defaults["rev_limit_freq"]
                snapshot["rev_limit_amp"] = defaults["rev_limit_amp"]
                snapshot["grip_redline_freq"] = defaults["grip_redline_freq"]
                snapshot["grip_redline_amp"] = defaults["grip_redline_amp"]
            else:
                snapshot["grip_redline_freq"] = trigger_freq
                snapshot["grip_redline_amp"] = trigger_amp

        for field in _GRIP_REDLINE_FIELDS:
            snapshot.setdefault(field, defaults[field])


def _migrate_r3_grip_gear_shift(raw: dict, s) -> None:
    """Add independent, default-off grip shift tuning to named profiles."""
    profiles = raw.get("profiles")
    if not isinstance(profiles, dict):
        return
    defaults = default_before_r11_profile_fields()
    for name, snapshot in profiles.items():
        if name == DEFAULT_PROFILE_NAME or not isinstance(snapshot, dict):
            continue
        for field in _GRIP_GEAR_SHIFT_FIELDS:
            snapshot.setdefault(field, defaults[field])


@_serialized()
def load(s) -> None:
    """Read the file and apply the active profile to `s`.

    Raises PreferencesError if the file is unreadable / corrupted so the caller
    can prompt the user before any destructive recovery.
    """
    raw = _read_raw()
    first_run = not raw
    if first_run and hasattr(s, "language"):
        s.language = detect_system_language()
    raw = _ensure_active(raw, s)
    _migrate_r7_reconnect_default(raw)
    _migrate_r8_redline_timing_defaults(raw)
    _migrate_r3_redline_split(raw, s)
    _migrate_r3_grip_gear_shift(raw, s)
    _migrate_r11_default_profile(raw, s, first_run=first_run)
    if raw["globals"].get("preferred_forza_platform") == "xbox_app":
        raw["globals"]["enable_hidhide"] = True
    _write(raw)
    snap = dict(raw["globals"])
    snap.update(raw["profiles"][raw["active_profile"]])
    _apply_snap(s, snap, _fields(s))
    _bind_loaded(s, raw)


def _backup_current() -> Path | None:
    """Atomically back up the current preferences, or raise without deleting it."""
    if not PATH.exists():
        return None
    backup = PATH.with_suffix(PATH.suffix + ".bak")
    temporary = backup.with_name(f".{backup.name}.{uuid.uuid4().hex}.tmp")
    try:
        original = PATH.read_bytes()
        temporary.write_bytes(original)
        if temporary.read_bytes() != original:
            raise OSError("preference backup verification failed")
        # Refuse to call this a backup if another instance changed the source
        # while it was being copied.
        if PATH.read_bytes() != original:
            raise OSError("preferences changed while the backup was being created")
        temporary.replace(backup)
        return backup
    except OSError as exc:
        raise PreferencesError(f"Could not back up {PATH.name}: {exc}") from exc
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


@_serialized()
def reset_file() -> None:
    """Back up the existing file and remove it only after verification succeeds."""
    backup = _backup_current()
    if backup is None:
        return
    try:
        PATH.unlink()
    except OSError as exc:
        raise PreferencesError(f"Could not delete {PATH.name}: {exc}") from exc
    log.info("Backed up old preferences to %s", backup.name)


@_serialized(False)
def save(s) -> bool:
    # Never let preference I/O or an external edit overwrite unrelated tuning.
    try:
        raw = _read_raw()
        state = _settings_state(s)
        if state is None and raw:
            raise PreferencesError("Load settings before saving existing preferences.")
        if state is not None and not raw:
            raise PreferencesError("Preferences were removed; reload before saving.")
        if (
            state is not None
            and _profile_fields(s) != state.profile
            and state.name not in raw.get("profiles", {})
        ):
            raise PreferencesError(
                f"Profile '{state.name}' was removed or renamed in another "
                "instance; reload a profile or save a named copy."
            )
        raw = _ensure_active(raw, s)
        if state is None:
            raw["profiles"][raw["active_profile"]] = _profile_fields(s)
            raw["globals"].update(_global_fields(s))
        else:
            current = _profile_fields(s)
            if current != state.profile:
                _merge_changes(current, state.profile, state.profile_disk, raw["profiles"][state.name])
            _merge_changes(_global_fields(s), state.globals, state.globals_disk, raw["globals"])
        if raw["globals"].get("preferred_forza_platform") == "xbox_app":
            raw["globals"]["enable_hidhide"] = True
        if not _write(raw):
            return False
        if getattr(s, "preferred_forza_platform", "") == "xbox_app":
            s.enable_hidhide = True
        if state is None:
            _bind_loaded(s, raw)
        else:
            # Keep unchanged baselines: unseen external edits must not later
            # become implicit permission to overwrite the same field.
            for current, baseline, saved, disk in (
                (_profile_fields(s), state.profile, state.profile_disk,
                 raw["profiles"].get(state.name, {})),
                (_global_fields(s), state.globals, state.globals_disk, raw["globals"]),
            ):
                for key, value in current.items():
                    if value != baseline.get(key, _MISSING):
                        baseline[key] = value
                        saved[key] = disk[key]
        return True
    except Exception as e:
        log.warning("preferences.save failed: %s", e)
        return False


@_serialized(False)
def restore_factory(s, *, language: str | None = None) -> bool:
    """Restore all settings and Default while preserving named profiles.

    A byte-for-byte backup is written before the replacement. The in-memory
    Settings object is mutated only after the atomic write succeeds.
    """
    defaults = type(s)()
    if hasattr(defaults, "language"):
        defaults.language = language or detect_system_language()

    raw = _ensure_active(_read(), s)
    named = {
        name: snapshot
        for name, snapshot in raw.get("profiles", {}).items()
        if name not in BUILTIN_PROFILE_NAMES
    }
    raw["profiles"] = {
        DEFAULT_PROFILE_NAME: _profile_fields(defaults),
        DEFAULT_BEFORE_R11_PROFILE_NAME: default_before_r11_profile_fields(),
        ORIGINAL_PROFILE_NAME: original_profile_fields(),
        **named,
    }
    raw["active_profile"] = DEFAULT_PROFILE_NAME
    raw["globals"] = _global_fields(defaults)
    raw.setdefault("migrations", {})[R11_DEFAULT_PROFILE_MIGRATION] = True

    if PATH.exists():
        try:
            _backup_current()
        except PreferencesError as e:
            log.warning("Could not back up preferences before factory restore: %s", e)
            return False
    if not _write(raw):
        return False

    snap = dict(raw["globals"])
    snap.update(raw["profiles"][DEFAULT_PROFILE_NAME])
    _apply_snap(s, snap, _fields(s))
    _bind_loaded(s, raw)
    return True


def reset(s) -> bool:
    """Compatibility alias for the full factory restore."""
    return restore_factory(s)
