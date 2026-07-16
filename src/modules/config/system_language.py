"""Map the operating-system display language to an available UI catalog."""

from __future__ import annotations

import ctypes
import locale
import os
import sys


SUPPORTED = frozenset({"en", "de", "ja", "ru", "tr", "zh", "zh_tw"})


def map_language_tag(tag: str | None) -> str:
    """Return the closest supported catalog for a BCP-47-like language tag."""
    normalized = (tag or "").strip().replace("_", "-").lower()
    if not normalized:
        return "en"
    if normalized.startswith("zh"):
        traditional = ("hant", "-tw", "-hk", "-mo")
        return "zh_tw" if any(part in normalized for part in traditional) else "zh"
    primary = normalized.split("-", 1)[0]
    return primary if primary in SUPPORTED else "en"


def _windows_language_tag() -> str:
    """Read the Windows display locale without changing process locale."""
    try:
        kernel32 = ctypes.windll.kernel32
        buffer = ctypes.create_unicode_buffer(85)
        if kernel32.GetUserDefaultLocaleName(buffer, len(buffer)):
            return buffer.value
    except (AttributeError, OSError, TypeError, ValueError):
        pass

    try:
        language_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return locale.windows_locale.get(language_id, "")
    except (AttributeError, OSError, TypeError, ValueError):
        return ""


def detect_system_language() -> str:
    """Detect the display language, falling back to English."""
    candidates: list[str | None] = []
    if sys.platform.startswith("win"):
        candidates.append(_windows_language_tag())
    try:
        candidates.append(locale.getlocale()[0])
    except (TypeError, ValueError):
        pass
    candidates.extend(
        os.environ.get(name) for name in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")
    )
    for candidate in candidates:
        if candidate:
            return map_language_tag(candidate.split(":", 1)[0].split(".", 1)[0])
    return "en"
