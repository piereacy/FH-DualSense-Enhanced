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

log = logging.getLogger("fhds")

_DATA = Path(__file__).resolve().parent.parent / "data"
PATH = _DATA / "user_preferences.json"
PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"
DEFAULT_PROFILE_NAME = "Default"

_SIMPLE = (bool, int, float, str)


class PreferencesError(Exception):
    """Raised when user_preferences.json cannot be parsed or is incompatible."""


def _version() -> str:
    try:
        m = re.search(r'(?m)^\s*version\s*=\s*"([^"]+)"', PYPROJECT.read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    except OSError:
        return ""


def _fields(s) -> dict:
    return {k: v for k, v in vars(s).items() if isinstance(v, _SIMPLE)}


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
    try:
        _DATA.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(raw, indent=2), encoding="utf-8")
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
    """Guarantee raw has a profiles dict and a valid active_profile."""
    _migrate_legacy(raw, s)
    raw.setdefault("profiles", {})
    raw.setdefault("active_profile", "")
    if not raw["profiles"]:
        raw["profiles"][DEFAULT_PROFILE_NAME] = _fields(s)
        raw["active_profile"] = DEFAULT_PROFILE_NAME
    elif raw["active_profile"] not in raw["profiles"]:
        raw["active_profile"] = sorted(raw["profiles"].keys(), key=str.lower)[0]
    return raw


def load(s) -> None:
    """Read the file and apply the active profile to `s`.

    Raises PreferencesError if the file is unreadable / corrupted so the caller
    can prompt the user before any destructive recovery.
    """
    raw = _read_raw()
    if raw and raw.get("version") and raw["version"] != _version():
        log.info("Preferences version changed (%s -> %s).",
                 raw.get("version"), _version() or "unknown")
    raw = _ensure_active(raw, s)
    _write(raw)
    snap = raw["profiles"][raw["active_profile"]]
    for k, current in _fields(s).items():
        if k in snap:
            try:
                setattr(s, k, type(current)(snap[k]))
            except (TypeError, ValueError):
                pass


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
    raw = _ensure_active(_read(), s)
    raw["profiles"][raw["active_profile"]] = _fields(s)
    _write(raw)


def reset(s) -> None:
    """Restore the active profile to class defaults; mutate s in place so the
    running loop picks them up on its next frame."""
    defaults = type(s)()
    for k in _fields(s):
        if hasattr(defaults, k):
            setattr(s, k, getattr(defaults, k))
    save(s)
