from pathlib import Path
from types import SimpleNamespace

from modules.config import preferences
from modules.config.settings import Settings
from modules.forzahorizon.fh6_language import (
    FH6Install,
    FH6LanguageState,
    LanguageInspection,
)
from modules.gui.fh6_utilities_tab import FH6UtilitiesTab
from modules.gui import fh6_utilities_tab
from modules.gui.main import TriggerGUI
from modules.gui.overview_tab import OverviewTab


ROOT = Path(__file__).resolve().parents[2]


class _Frame:
    def __init__(self, name, events, *, fail=False):
        self.name = name
        self.events = events
        self.fail = fail

    def tkraise(self):
        self.events.append(f"{self.name}.raise")
        if self.fail:
            raise RuntimeError("raise failed")

    def on_show(self):
        self.events.append(f"{self.name}.show")

    def on_hide(self):
        self.events.append(f"{self.name}.hide")


class _Button:
    def __init__(self):
        self.calls = []

    def configure(self, **kwargs):
        self.calls.append(kwargs)


class _Widget:
    def __init__(self):
        self.configure_calls = []

    def configure(self, **kwargs):
        self.configure_calls.append(kwargs)


def _navigation_shell(*, failing_target=False):
    events = []
    gui = TriggerGUI.__new__(TriggerGUI)
    gui._active_nav = "old"
    gui._tab_frames = {
        "old": _Frame("old", events),
        "new": _Frame("new", events, fail=failing_target),
    }
    gui._nav_buttons = {"old": _Button(), "new": _Button()}
    return gui, events


def test_gui_navigation_uses_lifecycle_hooks_and_raise_without_repacking():
    gui, events = _navigation_shell()

    TriggerGUI._select_nav(gui, "new")

    assert events == ["old.hide", "new.raise", "new.show"]
    assert gui._active_nav == "new"
    old_calls = list(gui._nav_buttons["old"].calls)
    new_calls = list(gui._nav_buttons["new"].calls)

    TriggerGUI._select_nav(gui, "new")

    assert events == ["old.hide", "new.raise", "new.show"]
    assert gui._nav_buttons["old"].calls == old_calls
    assert gui._nav_buttons["new"].calls == new_calls


def test_failed_gui_raise_restores_the_previous_page_and_selection():
    gui, events = _navigation_shell(failing_target=True)

    TriggerGUI._select_nav(gui, "new")

    assert events == ["old.hide", "new.raise", "old.raise", "old.show"]
    assert gui._active_nav == "old"
    assert gui._nav_buttons["old"].calls == []
    assert gui._nav_buttons["new"].calls == []


def test_quick_launch_presentation_does_not_reconfigure_unchanged_widgets():
    tab = OverviewTab.__new__(OverviewTab)
    tab._selected_platform = "steam"
    tab._selected_game_key = "fh6"
    tab._launch_request_busy = False
    tab._launch_render_cache = None
    tab._game_launch_button = _Widget()
    tab._game_selector_button = _Widget()
    tab._platform_selector = _Widget()

    tab._render_forza_launch("Launch FH6", True)
    first_counts = (
        len(tab._game_launch_button.configure_calls),
        len(tab._game_selector_button.configure_calls),
        len(tab._platform_selector.configure_calls),
    )
    tab._render_forza_launch("Launch FH6", True)

    assert first_counts == (1, 1, 1)
    assert (
        len(tab._game_launch_button.configure_calls),
        len(tab._game_selector_button.configure_calls),
        len(tab._platform_selector.configure_calls),
    ) == first_counts

    tab._render_forza_launch("FH6 is running", False)
    assert len(tab._game_launch_button.configure_calls) == 2
    assert len(tab._game_selector_button.configure_calls) == 1
    assert len(tab._platform_selector.configure_calls) == 1


def test_fh6_path_or_platform_changes_invalidate_both_utility_caches():
    tab = FH6UtilitiesTab.__new__(FH6UtilitiesTab)
    tab.settings = Settings()
    tab._fh6_platform = "steam"
    tab._fh6_path_hint = ""
    tab._icon_platform = "steam"
    tab._icon_path_hint = ""
    invalidated = []
    tab._invalidate_fh6 = lambda: invalidated.append("language")
    tab._invalidate_icons = lambda: invalidated.append("icons")

    tab.settings.fh6_install_path = "D:/ForzaHorizon6"
    changed = tab._sync_context()

    assert changed == (True, True)
    assert invalidated == ["language", "icons"]


def test_fh6_language_utility_uses_the_selected_platform_path():
    tab = FH6UtilitiesTab.__new__(FH6UtilitiesTab)
    tab.settings = Settings(
        fh6_install_path="D:/Steam/FH6",
        fh6_xbox_install_path="E:/Xbox/FH6",
    )

    assert tab._language_saved_path("steam") == "D:/Steam/FH6"
    assert tab._language_saved_path("xbox_app") == "E:/Xbox/FH6"


def test_manual_xbox_folder_supersedes_an_automatic_gui_scan(monkeypatch):
    started = []

    class _Thread:
        def __init__(self, *, target, name, daemon):
            self.target = target

        def start(self):
            started.append(self.target)

    monkeypatch.setattr(fh6_utilities_tab.threading, "Thread", _Thread)
    tab = FH6UtilitiesTab.__new__(FH6UtilitiesTab)
    tab.app = SimpleNamespace(_tearing_down=False)
    tab.settings = Settings(preferred_forza_platform="xbox_app")
    tab._fh6_scan_busy = True
    tab._fh6_operation_busy = False
    tab._fh6_scan_serial = 4
    tab._fh6_install = None
    tab._fh6_silent_scan = True
    tab._fh6_error = ""
    tab._fh6_last_scan = 0.0
    tab._fh6_platform = "xbox_app"
    tab._render_fh6_status = lambda: None

    tab._start_fh6_scan(rediscover=False, manual_path="E:/Xbox/FH6")

    assert tab._fh6_active_serial == 5
    assert tab._fh6_scan_busy is True
    assert len(started) == 1


def test_manual_xbox_icon_folder_supersedes_an_automatic_gui_scan(monkeypatch):
    started = []

    class _Thread:
        def __init__(self, *, target, name, daemon):
            self.target = target

        def start(self):
            started.append(self.target)

    monkeypatch.setattr(fh6_utilities_tab.threading, "Thread", _Thread)
    tab = FH6UtilitiesTab.__new__(FH6UtilitiesTab)
    tab.app = SimpleNamespace(_tearing_down=False)
    tab.settings = Settings(preferred_forza_platform="xbox_app")
    tab._icon_scan_busy = True
    tab._icon_operation_busy = False
    tab._icon_scan_serial = 8
    tab._icon_inspection = fh6_utilities_tab.inspect_controller_icons(None)
    tab._icon_silent_scan = True
    tab._icon_error = ""
    tab._icon_last_scan = 0.0
    tab._icon_platform = "xbox_app"
    tab._render_icon_status = lambda: None

    tab._start_icon_scan(rediscover=False, manual_path="E:/Xbox/FH6")

    assert tab._icon_active_serial == 9
    assert tab._icon_scan_busy is True
    assert len(started) == 1


def test_xbox_language_scan_saves_only_the_xbox_path(monkeypatch, tmp_path):
    root = tmp_path / "XboxFH6"
    install = FH6Install(root, root / "media/Stripped/StringTables", "Manual Xbox App")
    inspection = LanguageInspection(FH6LanguageState.NATIVE, install)
    tab = FH6UtilitiesTab.__new__(FH6UtilitiesTab)
    tab.settings = Settings(
        fh6_install_path="D:/Steam/FH6",
        fh6_xbox_install_path="",
        preferred_forza_platform="xbox_app",
    )
    tab._fh6_active_serial = 9
    tab._fh6_scan_busy = True
    tab._fh6_silent_scan = False
    tab._fh6_platform = "xbox_app"
    tab._fh6_path_hint = ""
    tab._fh6_render_cache = None
    tab._visible = True
    tab._render_fh6_status = lambda: None
    saved = []
    monkeypatch.setattr(preferences, "save", lambda settings: saved.append(settings))

    tab._apply_fh6_scan(
        9,
        "xbox_app",
        "",
        True,
        install,
        inspection,
        False,
        "",
    )

    assert tab.settings.fh6_install_path == "D:/Steam/FH6"
    assert tab.settings.fh6_xbox_install_path == str(root)
    assert saved == [tab.settings]


def test_fh6_tools_exist_only_in_the_dedicated_gui_and_tui_pages():
    gui_system = (ROOT / "src/modules/gui/system_tab.py").read_text(encoding="utf-8")
    gui_utilities = (ROOT / "src/modules/gui/fh6_utilities_tab.py").read_text(
        encoding="utf-8"
    )
    tui_system = (ROOT / "src/modules/tui/system_tab.py").read_text(encoding="utf-8")
    tui_utilities = (ROOT / "src/modules/tui/fh6_utilities_tab.py").read_text(
        encoding="utf-8"
    )

    for source in (gui_system, tui_system):
        assert "FH6 Chinese text + English voice" not in source
        assert "FH6 DualSense button icons" not in source
        assert "scan_fh6" not in source
        assert "scan_icon" not in source
    for source in (gui_utilities, tui_utilities):
        assert "FH6 Chinese text + English voice" in source
        assert "FH6 DualSense button icons" in source
        assert "Current FH6 game language: {language}" in source
        assert "Actual display language: {language}" in source
        assert "Voice language: {language}" in source
        assert "Steam language: {language}" not in source
    assert "_start_fh6_scan" in gui_utilities
    assert "_start_icon_scan" in gui_utilities
    assert "_scan_fh6" in tui_utilities
    assert "_scan_icons" in tui_utilities


def test_all_non_english_catalogs_name_the_fh6_utilities_page():
    from lang import de, ja, ru, tr, zh, zh_tw

    for catalog in (de, ja, ru, tr, zh, zh_tw):
        assert catalog.STRINGS["FH6 utilities"]
        assert catalog.STRINGS[
            "Language files and PlayStation button icons for Forza Horizon 6."
        ]
        for key in (
            "Current FH6 game language: {language}",
            "Actual display language: {language}",
            "Voice language: {language}",
            "English",
            "Chinese",
            "Unknown",
        ):
            assert catalog.STRINGS[key]


def test_product_default_platform_remains_steam():
    settings = Settings()
    assert settings.preferred_forza_platform == "steam"
