"""Shared GUI/TUI presentation for the FH6 language archive feature."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .fh6_language import (
    FH6LanguageState,
    LanguageInspection,
    SteamLanguageState,
    is_windows_steam_supported,
)


@dataclass(frozen=True, slots=True)
class LanguageView:
    status: str
    detail: str
    action: str
    action_label: str
    action_enabled: bool
    unknown_language_warning: bool = False


def language_view(
    inspection: LanguageInspection,
    *,
    game_running: bool,
    translate: Callable[[str], str],
) -> LanguageView:
    if not is_windows_steam_supported():
        return LanguageView(
            translate("Unavailable in this runtime"),
            translate(
                "Windows Steam only. Detection is automatic, but files change only after you press a button and confirm."
            ),
            "",
            "",
            False,
        )
    state = inspection.state
    install = inspection.install
    if state is FH6LanguageState.NOT_FOUND:
        return LanguageView(
            translate("FH6 installation not found"),
            translate("Run FH6 at least once, then rescan or choose its install folder."),
            "",
            "",
            False,
        )
    mappings = {
        FH6LanguageState.NATIVE: (
            "Original language files",
            "CHS.zip is Chinese and EN.zip is English.",
            "enable",
            "Enable Chinese text + English voice",
        ),
        FH6LanguageState.SWAPPED: (
            "Chinese text + English voice enabled",
            "File contents are swapped. Steam updates may restore the original files.",
            "restore",
            "Restore original language files",
        ),
        FH6LanguageState.RECOVERY_REQUIRED: (
            "Interrupted language swap detected",
            "No automatic repair was performed. Confirm repair to restore the original layout.",
            "repair",
            "Repair original language files",
        ),
        FH6LanguageState.MISSING: (
            "Language files are missing",
            "Verify the FH6 game files in Steam, then rescan.",
            "",
            "",
        ),
        FH6LanguageState.UNKNOWN: (
            "Language files are not recognized",
            "The archives were left unchanged because their contents could not be identified safely.",
            "",
            "",
        ),
        FH6LanguageState.CORRUPT: (
            "Language archive is damaged",
            "Verify the FH6 game files in Steam before trying again.",
            "",
            "",
        ),
    }
    status_key, detail_key, action, action_label_key = mappings[state]
    enabled = bool(action)
    warning = False
    if game_running:
        detail_key = "Close Forza Horizon 6 before changing language files."
        enabled = False
    elif state is FH6LanguageState.NATIVE and install is not None:
        if install.steam_language_state is SteamLanguageState.OTHER:
            detail_key = "Set the FH6 language to English in Steam Properties first."
            enabled = False
        elif install.steam_language_state is SteamLanguageState.UNKNOWN:
            detail_key = (
                "Steam language could not be verified. Continuing requires an extra confirmation."
            )
            warning = True
    if state is FH6LanguageState.RECOVERY_REQUIRED and not inspection.can_repair:
        enabled = False
    return LanguageView(
        translate(status_key),
        translate(detail_key),
        action,
        translate(action_label_key) if action_label_key else "",
        enabled,
        warning,
    )
