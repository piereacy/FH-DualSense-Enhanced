"""Persist Settings as the active profile inside user_preferences.json.

File layout:
    {
      "version": "x.y.z",
      "active_profile": "Default",
      "profiles": {
        "Default": { ...flat Settings fields... },
        "Sport":   { ... }
      }
    }

On first launch a "Default" profile is seeded from the class defaults.
save(s) always writes into the currently active profile.
"""
import json
import logging
import math
from pathlib import Path
import re
import uuid
from . import paths
from .system_language import detect_system_language

log = logging.getLogger("fhds")

_DATA = paths.DATA
PATH = _DATA / "user_preferences.json"
PYPROJECT = paths.PYPROJECT
DEFAULT_PROFILE_NAME = "Default"
ORIGINAL_PROFILE_NAME = "Original"
BUILTIN_PROFILE_NAMES = frozenset({DEFAULT_PROFILE_NAME, ORIGINAL_PROFILE_NAME})
R7_RECONNECT_MIGRATION = "r7_enable_reconnect_default"

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
    "language",
    "controller_lock_serial",
    "use_dsx",
    "dsx_host",
    "dsx_port",
})

_SIMPLE = (bool, int, float, str)


class PreferencesError(Exception):
    """Raised when user_preferences.json cannot be parsed or is incompatible."""


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
    return {k: v for k, v in vars(s).items() if isinstance(v, _SIMPLE)}


def _profile_fields(s) -> dict:
    return {k: v for k, v in _fields(s).items() if k not in GLOBAL_FIELDS}


def _global_fields(s) -> dict:
    return {k: v for k, v in _fields(s).items() if k in GLOBAL_FIELDS}


def original_profile_fields() -> dict:
    """Current profile schema populated with upstream v1.6.2 defaults."""
    from .settings import Settings

    snapshot = _profile_fields(Settings())
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
    except OSError as e:
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
    # Multiple UI instances can remain open even when only one owns the UDP
    # port. Give each atomic save its own staging file so concurrent saves can
    # be last-writer-wins without truncating one shared temporary file.
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
    # Original is a built-in canonical preset, not a user-owned snapshot.
    # Refresh it so upgrades receive corrections to the bundled preset too.
    raw["profiles"][ORIGINAL_PROFILE_NAME] = original_profile_fields()
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
    defaults = type(s)()
    for name, snapshot in profiles.items():
        if name == DEFAULT_PROFILE_NAME or not isinstance(snapshot, dict):
            continue
        if "enable_grip_redline_haptics" in snapshot:
            for field in _GRIP_REDLINE_FIELDS:
                snapshot.setdefault(field, getattr(defaults, field))
            continue

        if re.match(r"^3(?:\.|$)", version):
            trigger_freq = snapshot.get("rev_limit_freq", defaults.rev_limit_freq)
            trigger_amp = snapshot.get("rev_limit_amp", defaults.rev_limit_amp)
            snapshot["enable_grip_redline_haptics"] = bool(
                snapshot.get("enable_rev_limiter", defaults.enable_rev_limiter)
            )
            snapshot["grip_redline_ratio"] = snapshot.get(
                "rev_limit_ratio", defaults.grip_redline_ratio
            )
            if trigger_freq == 10 and trigger_amp == 96:
                snapshot["rev_limit_freq"] = defaults.rev_limit_freq
                snapshot["rev_limit_amp"] = defaults.rev_limit_amp
                snapshot["grip_redline_freq"] = defaults.grip_redline_freq
                snapshot["grip_redline_amp"] = defaults.grip_redline_amp
            else:
                snapshot["grip_redline_freq"] = trigger_freq
                snapshot["grip_redline_amp"] = trigger_amp

        for field in _GRIP_REDLINE_FIELDS:
            snapshot.setdefault(field, getattr(defaults, field))


def _migrate_r3_grip_gear_shift(raw: dict, s) -> None:
    """Add independent, default-off grip shift tuning to named profiles."""
    profiles = raw.get("profiles")
    if not isinstance(profiles, dict):
        return
    defaults = type(s)()
    for name, snapshot in profiles.items():
        if name == DEFAULT_PROFILE_NAME or not isinstance(snapshot, dict):
            continue
        for field in _GRIP_GEAR_SHIFT_FIELDS:
            snapshot.setdefault(field, getattr(defaults, field))


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
    _migrate_r3_redline_split(raw, s)
    _migrate_r3_grip_gear_shift(raw, s)
    _write(raw)
    snap = dict(raw["globals"])
    snap.update(raw["profiles"][raw["active_profile"]])
    _apply_snap(s, snap, _fields(s))


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


def save(s) -> bool:
    # MARK: never let preferences I/O crash the UI event handler
    try:
        # A file that becomes corrupt while the app is running must not be
        # replaced by a seemingly successful save. Startup recovery remains
        # the single explicit path that may discard malformed preferences.
        raw = _ensure_active(_read_raw(), s)
        raw["profiles"][raw["active_profile"]] = _profile_fields(s)
        raw["globals"].update(_global_fields(s))
        return _write(raw)
    except Exception as e:
        log.warning("preferences.save failed: %s", e)
        return False


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
        ORIGINAL_PROFILE_NAME: original_profile_fields(),
        **named,
    }
    raw["active_profile"] = DEFAULT_PROFILE_NAME
    raw["globals"] = _global_fields(defaults)

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
    return True


def reset(s) -> bool:
    """Compatibility alias for the full factory restore."""
    return restore_factory(s)
