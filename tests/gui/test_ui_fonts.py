from customtkinter import ThemeManager

from modules.gui import theme
from modules.gui.main import TriggerGUI


def test_windows_ui_fonts_follow_the_interface_language():
    assert theme.ui_font_family("zh", "win32") == "Microsoft YaHei UI"
    assert theme.ui_font_family("zh_tw", "win32") == "Microsoft JhengHei UI"
    assert theme.ui_font_family("ja", "win32") == "Yu Gothic UI"
    assert theme.ui_font_family("en", "win32") == "Segoe UI"
    assert theme.ui_font_family("de", "win32") == "Segoe UI"


def test_non_windows_keeps_customtkinter_font():
    assert theme.ui_font_family("zh", "linux") == "Roboto"


def test_apply_theme_sets_customtkinter_default_font_family():
    previous = ThemeManager.theme["CTkFont"]["family"]
    try:
        TriggerGUI._apply_theme("Microsoft YaHei UI")
        assert ThemeManager.theme["CTkFont"]["family"] == "Microsoft YaHei UI"
    finally:
        ThemeManager.theme["CTkFont"]["family"] = previous
