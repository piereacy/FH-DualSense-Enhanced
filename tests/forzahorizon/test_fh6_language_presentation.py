from pathlib import Path

from modules.forzahorizon.fh6_language import (
    ArchiveLanguage,
    FH6Install,
    FH6LanguageState,
    LanguageInspection,
)
from modules.forzahorizon import fh6_language_presentation as presentation
from modules.forzahorizon.fh6_language_presentation import (
    LanguageSummaryView,
    language_summary_view,
    language_view,
)


def _t(value):
    return value


def _inspection(state, language="english"):
    install = FH6Install(Path("C:/Game"), Path("C:/Game/StringTables"), "test", language)
    return LanguageInspection(
        state,
        install,
        ArchiveLanguage.CHINESE,
        ArchiveLanguage.ENGLISH,
    )


def test_view_only_enables_safe_actions_and_blocks_a_running_game(monkeypatch):
    monkeypatch.setattr(presentation, "is_windows_steam_supported", lambda: True)
    native = language_view(
        _inspection(FH6LanguageState.NATIVE), game_running=False, translate=_t
    )
    assert native.action == "enable"
    assert native.action_enabled is True

    running = language_view(
        _inspection(FH6LanguageState.NATIVE), game_running=True, translate=_t
    )
    assert running.action_enabled is False
    assert running.detail.startswith("Close Forza Horizon 6")


def test_view_blocks_non_english_steam_language_and_warns_when_unknown(monkeypatch):
    monkeypatch.setattr(presentation, "is_windows_steam_supported", lambda: True)
    other = language_view(
        _inspection(FH6LanguageState.NATIVE, "schinese"),
        game_running=False,
        translate=_t,
    )
    assert other.action_enabled is False
    assert "Steam Properties" in other.detail

    unknown = language_view(
        _inspection(FH6LanguageState.NATIVE, ""),
        game_running=False,
        translate=_t,
    )
    assert unknown.action_enabled is True
    assert unknown.unknown_language_warning is True


def test_view_disables_the_feature_outside_windows(monkeypatch):
    monkeypatch.setattr(presentation, "is_windows_steam_supported", lambda: False)

    view = language_view(
        _inspection(FH6LanguageState.NATIVE), game_running=False, translate=_t
    )

    assert view.status == "Unavailable in this runtime"
    assert view.action_enabled is False


def test_three_line_summary_distinguishes_game_display_and_voice_languages():
    view = language_summary_view(
        _inspection(FH6LanguageState.SWAPPED),
        _t,
    )

    assert view == LanguageSummaryView(
        game_language="English",
        display_language="Chinese",
        voice_language="English",
    )


def test_xbox_path_support_is_manual_and_does_not_invent_a_language(monkeypatch):
    monkeypatch.setattr(presentation, "is_windows_steam_supported", lambda: True)
    missing = language_view(
        LanguageInspection(FH6LanguageState.NOT_FOUND, None),
        game_running=False,
        translate=_t,
        platform="xbox_app",
    )
    unknown = language_view(
        _inspection(FH6LanguageState.NATIVE, ""),
        game_running=False,
        translate=_t,
        platform="xbox_app",
    )
    summary = language_summary_view(
        _inspection(FH6LanguageState.NATIVE, ""),
        _t,
    )

    assert missing.detail == (
        "Automatic detection failed. Rescan or choose the Xbox App FH6 install folder."
    )
    assert unknown.action_enabled is True
    assert unknown.unknown_language_warning is True
    assert "Steam" not in unknown.detail
    assert summary == LanguageSummaryView("Unknown", "Unknown", "Unknown")
