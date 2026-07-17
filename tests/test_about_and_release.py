import asyncio
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTION = "Originally created by Hamza Yeşilmen (HamzaYslmn)."
SOURCE_URL = "https://github.com/HamzaYslmn/Forza-Horizon-DualSense-Python"
SPONSOR_URL = "https://github.com/sponsors/HamzaYslmn"


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_shared_about_metadata_matches_the_license_exactly():
    path = ROOT / "src/modules/about.py"

    assert path.exists(), "shared about metadata module is missing"
    values = runpy.run_path(str(path))
    assert values["ATTRIBUTION"] == ATTRIBUTION
    assert values["SOURCE_URL"] == SOURCE_URL
    assert values["SPONSOR_URL"] == SPONSOR_URL


def test_gui_about_page_exposes_attribution_and_clickable_links():
    source = _source("src/modules/gui/about_tab.py")
    settings = _source("src/modules/gui/settings_tab.py")

    assert "ATTRIBUTION" in source
    assert "self.app._open_url(SOURCE_URL)" in source
    assert "self.app._open_url(SPONSOR_URL)" in source
    assert "ATTRIBUTION" not in settings
    assert "About and licenses" not in settings


def test_tui_about_page_exposes_attribution_and_clickable_links():
    source = _source("src/modules/tui/about_tab.py")
    settings = _source("src/modules/tui/settings_tab.py")

    assert "ATTRIBUTION" in source
    assert "about-source" in source
    assert "about-sponsor" in source
    assert "self.app._open_url(SOURCE_URL)" in source
    assert "self.app._open_url(SPONSOR_URL)" in source
    assert "ATTRIBUTION" not in settings
    assert "About and licenses" not in settings


def test_sponsor_is_only_exposed_in_about_and_license_surfaces():
    gui_main = _source("src/modules/gui/main.py")
    tui_main = _source("src/modules/tui/main.py")
    gui_about = _source("src/modules/gui/about_tab.py")
    tui_about = _source("src/modules/tui/about_tab.py")

    assert "sponsor_btn" not in gui_main
    assert "bb-sponsor" not in tui_main
    assert "action_sponsor" not in tui_main
    assert "self.app._open_url(SPONSOR_URL)" in gui_about
    assert "self.app._open_url(SPONSOR_URL)" in tui_about


def test_about_page_is_after_logs_in_both_interfaces():
    gui = _source("src/modules/gui/main.py")
    tui = _source("src/modules/tui/main.py")

    assert '"System", "Language", "Logs", "About"' in gui
    assert "self.about_tab = AboutTab" in gui
    assert '"About":    self.about_tab' in gui
    assert tui.index('id="tab-logs"') < tui.index('id="tab-about"')


def test_tui_about_page_mounts_with_both_required_links():
    from textual.app import App, ComposeResult
    from textual.widgets import Button

    from modules.tui.about_tab import AboutTab

    class AboutHarness(App):
        def compose(self) -> ComposeResult:
            yield AboutTab()

    async def check():
        app = AboutHarness()
        async with app.run_test():
            assert app.query_one("#about-source", Button)
            assert app.query_one("#about-sponsor", Button)

    asyncio.run(check())


def test_every_non_english_catalog_translates_about_heading():
    for path in sorted((ROOT / "src/lang").glob("*.py")):
        if path.name in {"__init__.py", "en.py"}:
            continue
        strings = runpy.run_path(str(path))["STRINGS"]
        assert "About and licenses" in strings, f"{path.name} is missing About and licenses"


def test_windows_packaging_ships_both_license_notice_files():
    spec = _source("packaging/windows/fhds.spec")
    build = _source("packaging/windows/build_exe.bat")

    assert 'str(ROOT / "LICENSE")' in spec
    assert "FH-DualSense-Update-Helper.exe" in spec
    assert 'copy /y "LICENSE" "%DIST%\\LICENSE"' in build
    assert 'copy /y "docs\\THIRD_PARTY_NOTICES.md" "%DIST%\\THIRD_PARTY_NOTICES.md"' in build
