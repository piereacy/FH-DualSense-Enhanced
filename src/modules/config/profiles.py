"""Named Settings snapshots stored inside user_preferences.json."""
import base64
import binascii
import json
import logging
import zlib

from . import preferences

log = logging.getLogger("fhds")

SHARE_PREFIX = "FHDS:"
MAX_SHARE_CODE_BODY = 128 * 1024
MAX_SHARE_PAYLOAD = 256 * 1024
MAX_PROFILE_NAME = 64
_DEFAULT = preferences.DEFAULT_PROFILE_NAME
_DEFAULT_BEFORE_R11 = preferences.DEFAULT_BEFORE_R11_PROFILE_NAME
_ORIGINAL = preferences.ORIGINAL_PROFILE_NAME


def load_profiles(s=None) -> dict:
    """Read available profiles, retaining this instance's live selection."""
    raw = preferences._read()
    state = preferences._settings_state(s)
    return {
        "active": state.name if state else raw.get("active_profile", "") or "",
        "profiles": raw.get("profiles", {}) or {},
    }


def active_name(s=None) -> str:
    state = preferences._settings_state(s)
    return state.name if state else load_profiles().get("active", "") or ""


def list_profile_names(store: dict) -> list:
    """All profile names with built-in profiles pinned to the top."""
    names = list(store.get("profiles", {}).keys())
    pinned = [
        name
        for name in (_DEFAULT, _DEFAULT_BEFORE_R11, _ORIGINAL)
        if name in names
    ]
    rest = sorted(
        (name for name in names if name not in preferences.BUILTIN_PROFILE_NAMES),
        key=str.lower,
    )
    return pinned + rest


def is_builtin_profile(name: str) -> bool:
    return name in preferences.BUILTIN_PROFILE_NAMES


def _clean_name(name: str, *, fallback: str = "") -> str:
    if not isinstance(name, str):
        return fallback
    cleaned = "".join(
        character
        for character in name.strip()
        if ord(character) >= 32 and ord(character) != 127
    )
    return cleaned[:MAX_PROFILE_NAME].strip() or fallback


def _unique(name: str, taken: dict) -> str:
    """Return `name` or `name1`, `name2`, ... if it collides."""
    if name not in taken:
        return name
    i = 1
    while True:
        suffix = str(i)
        candidate = f"{name[: MAX_PROFILE_NAME - len(suffix)]}{suffix}"
        if candidate not in taken:
            return candidate
        i += 1


def _defaults() -> dict:
    from .settings import Settings
    return preferences._profile_fields(Settings())


def _apply_profile_snapshot(s, snap: dict) -> None:
    from .settings import Settings

    normalized = Settings()
    preferences._apply_snap(normalized, snap, preferences._profile_fields(normalized))
    preferences._apply_snap(s, preferences._profile_fields(normalized), preferences._profile_fields(s))


@preferences._serialized("")
def save_profile(name: str, s) -> str:
    """Save current settings as a new profile. Auto-suffixes on collision.
    Returns the final stored name, or "" if `name` was empty."""
    name = _clean_name(name)
    if not name:
        return ""
    raw = preferences._read_raw()
    profs = raw.setdefault("profiles", {})
    final = _unique(name, profs)
    profs[final] = preferences._profile_fields(s)
    raw["active_profile"] = final
    if not preferences._write(raw):
        return ""
    preferences._bind_profile(s, final, profs[final], raw)
    return final


def next_profile_name(prefix: str = "profile") -> str:
    """Return profile1, profile2, ... using the first available number."""
    taken = load_profiles()["profiles"]
    index = 1
    while f"{prefix}{index}" in taken:
        index += 1
    return f"{prefix}{index}"


@preferences._serialized(False)
def apply_profile(name: str, s) -> bool:
    raw = preferences._read_raw()
    if name != _ORIGINAL and name not in raw.get("profiles", {}):
        return False
    if not preferences.save_pending(s):
        return False
    raw = preferences._read_raw()
    profs = raw.setdefault("profiles", {})
    if name == _ORIGINAL:
        # Loading the built-in preset always restores its canonical values,
        # even if the user previously tuned it during a session.
        snap = preferences.original_profile_fields()
        profs[name] = snap
    else:
        snap = profs.get(name)
    if snap is None:
        return False
    raw["active_profile"] = name
    if not preferences._write(raw):
        return False
    _apply_profile_snapshot(s, snap)
    preferences._bind_profile(s, name, snap, raw)
    return True


@preferences._serialized(False)
def delete_profile(name: str, s=None) -> bool:
    """Delete a snapshot, applying the fallback when deleting the live profile."""
    raw = preferences._read_raw()
    profs = raw.get("profiles", {})
    if name not in profs or is_builtin_profile(name):
        return False
    state = preferences._settings_state(s)
    if state is not None and state.name == name:
        if not preferences.save_pending(s):
            return False
        raw = preferences._read_raw()
        profs = raw.get("profiles", {})
    del profs[name]
    active = raw.get("active_profile", "")
    state = preferences._settings_state(s)
    local_active = state.name if state else active
    fallback = ""
    if local_active == name or active == name:
        if s is None:
            # Changing only the disk selection would let the next autosave
            # overwrite the fallback with the deleted profile's live values.
            return False
        # Prefer Default so the canonical profile stays selected.
        fallback = _DEFAULT if _DEFAULT in profs else next(
            iter(sorted(profs.keys(), key=str.lower)), "")
        if active == name:
            active = fallback
    raw["active_profile"] = active
    if not preferences._write(raw):
        return False
    if local_active == name:
        snapshot = profs.get(fallback, {})
        _apply_profile_snapshot(s, snapshot)
        preferences._bind_profile(s, fallback, snapshot, raw)
    return True


@preferences._serialized("")
def rename_profile(old: str, new: str, s=None) -> str:
    """Rename `old` to `new`, auto-suffixing on collision. Returns "" if
    rejected (built-in profile locked, old missing, new empty)."""
    new = _clean_name(new)
    if not new or old == new or is_builtin_profile(old):
        return ""
    raw = preferences._read_raw()
    profs = raw.get("profiles", {})
    if old not in profs:
        return ""
    final = _unique(new, {k: v for k, v in profs.items() if k != old})
    # Preserve insertion order so the list doesn't reshuffle.
    profs_new = {(final if k == old else k): v for k, v in profs.items()}
    raw["profiles"] = profs_new
    if raw.get("active_profile") == old:
        raw["active_profile"] = final
    if not preferences._write(raw):
        return ""
    state = preferences._settings_state(s)
    if state is not None and state.name == old:
        # Keep the loaded field baselines, including conflicts and pending edits.
        state.name = final
    return final


# MARK: share codes --------------------------------------------------------

def export_profile(name: str) -> str:
    """Encode profile `name` as a short FHDS: code. Empty if missing.
    Only fields that differ from current built-in defaults are encoded."""
    store = load_profiles()
    snap = store["profiles"].get(name)
    if snap is None:
        return ""
    defaults = _defaults()
    diff = {k: v for k, v in snap.items() if defaults.get(k) != v}
    payload = json.dumps([name, diff], separators=(",", ":")).encode("utf-8")
    blob = zlib.compress(payload, level=9)
    return SHARE_PREFIX + base64.urlsafe_b64encode(blob).rstrip(b"=").decode("ascii")


@preferences._serialized("")
def import_profile(code: str) -> str:
    """Decode an FHDS: code into a new profile (auto-suffixed). Returns ""
    on failure. Unknown keys are dropped; missing keys fall back to current
    defaults so codes stay compatible across versions."""
    code = (code or "").strip()
    if not code.startswith(SHARE_PREFIX):
        return ""
    body = code[len(SHARE_PREFIX):]
    if not body or len(body) > MAX_SHARE_CODE_BODY:
        return ""
    pad = "=" * (-len(body) % 4)
    try:
        blob = base64.urlsafe_b64decode(body + pad)
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(blob, MAX_SHARE_PAYLOAD + 1)
        if (
            len(decoded) > MAX_SHARE_PAYLOAD
            or inflater.unconsumed_tail
            or not inflater.eof
            or inflater.unused_data
        ):
            return ""
        decoded += inflater.flush(max(1, MAX_SHARE_PAYLOAD + 1 - len(decoded)))
        if len(decoded) > MAX_SHARE_PAYLOAD:
            return ""
        payload = json.loads(decoded.decode("utf-8"))
    except (ValueError, OSError, zlib.error, binascii.Error, json.JSONDecodeError):
        return ""
    if not (isinstance(payload, list) and len(payload) == 2
            and isinstance(payload[1], dict)):
        return ""
    if not isinstance(payload[0], str):
        return ""
    name = _clean_name(payload[0], fallback="Imported")
    defaults = _defaults()
    cleaned = {k: v for k, v in payload[1].items() if k in defaults}
    # Apply the same typed, finite-value coercion used when loading a profile.
    # Invalid imported fields must fall back to built-in defaults rather than
    # remaining in JSON and later inheriting whichever profile was active.
    from .settings import Settings

    normalized = Settings()
    preferences._apply_snap(normalized, cleaned, preferences._profile_fields(normalized))
    snapshot = preferences._profile_fields(normalized)
    raw = preferences._read_raw()
    profs = raw.setdefault("profiles", {})
    final = _unique(name, profs)
    profs[final] = snapshot
    return final if preferences._write(raw) else ""
