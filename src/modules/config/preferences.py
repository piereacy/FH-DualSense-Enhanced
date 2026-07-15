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
import re
from pathlib import Path

from . import paths

log = logging.getLogger("fhds")

_DATA = paths.DATA
PATH = _DATA / "user_preferences.json"
PYPROJECT = paths.PYPROJECT
DEFAULT_PROFILE_NAME = "Default"

# System fields — shared across profiles and preserved across launches.
# Everything else lives in the active profile and is wiped from Default each launch.
GLOBAL_FIELDS = frozenset({
    "udp_port",
    "udp_forward",
    "udp_forward_to",
    "enable_reconnect",
    "reconnect_interval_s",
    "enable_startup_pulse",
    "startup_pulse_force",
    "exit_on_game_close",
    "minimize_to_tray",
    "game_poll_interval_s",
    "check_for_updates",
    "auto_download_updates",
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


def _apply_snap(s, snap: dict, fields: dict) -> None:
    """Copy values from `snap` into `s`, coerced to the type of each field."""
    for k, current in fields.items():
        if k in snap:
            try:
                setattr(s, k, type(current)(snap[k]))
            except (TypeError, ValueError):
                pass


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
    return data


def _read() -> dict:
    """Tolerant read for mutation paths: corruption is logged then ignored."""
    try:
        return _read_raw()
    except PreferencesError as e:
        log.warning("%s Falling back to empty preferences.", e)
        return {}


def _write(raw: dict) -> None:
    raw["version"] = _version()
    # MARK: atomic write - avoid corrupt file on power loss / mid-write crash
    try:
        _DATA.mkdir(parents=True, exist_ok=True)
        tmp = PATH.with_suffix(PATH.suffix + ".tmp")
        tmp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        tmp.replace(PATH)
    except OSError as e:
        log.warning("Could not save preferences: %s", e)


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
    elif raw["active_profile"] not in raw["profiles"]:
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


_GRIP_REDLINE_FIELDS = (
    "enable_grip_redline_haptics",
    "grip_redline_left",
    "grip_redline_right",
    "grip_redline_ratio",
    "grip_redline_release_ratio",
    "grip_redline_freq",
    "grip_redline_amp",
    "grip_redline_gain",
    "grip_redline_low_ratio",
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
    raw = _ensure_active(raw, s)
    _migrate_r3_redline_split(raw, s)
    _migrate_r3_grip_gear_shift(raw, s)
    # Reset Default on every launch so updates ship new tuning automatically;
    # named profiles and globals are preserved.
    raw["profiles"][DEFAULT_PROFILE_NAME] = _profile_fields(type(s)())
    _write(raw)
    snap = dict(raw["globals"])
    snap.update(raw["profiles"][raw["active_profile"]])
    _apply_snap(s, snap, _fields(s))


def reset_file() -> None:
    """Back up the existing file (if any) and remove it so load() can rebuild."""
    if PATH.exists():
        backup = PATH.with_suffix(PATH.suffix + ".bak")
        try:
            backup.write_bytes(PATH.read_bytes())
            log.info("Backed up old preferences to %s", backup.name)
        except OSError as e:
            log.warning("Could not back up %s: %s", PATH.name, e)
        try:
            PATH.unlink()
        except OSError as e:
            log.warning("Could not delete %s: %s", PATH.name, e)


def save(s) -> None:
    # MARK: never let preferences I/O crash the UI event handler
    try:
        raw = _ensure_active(_read(), s)
        raw["profiles"][raw["active_profile"]] = _profile_fields(s)
        raw["globals"].update(_global_fields(s))
        _write(raw)
    except Exception as e:
        log.warning("preferences.save failed: %s", e)


def reset(s) -> None:
    """Restore the active profile to class defaults; mutate s in place so the
    running loop picks them up on its next frame. Global fields are left intact."""
    defaults = type(s)()
    for k in _profile_fields(s):
        if hasattr(defaults, k):
            setattr(s, k, getattr(defaults, k))
    save(s)
