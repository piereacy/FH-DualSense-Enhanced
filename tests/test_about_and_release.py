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


def test_gui_settings_exposes_attribution_and_clickable_links():
    source = _source("src/modules/gui/settings_tab.py")

    assert "def _build_about_card" in source
    assert "ATTRIBUTION" in source
    assert "self.app._open_url(SOURCE_URL)" in source
    assert "self.app._open_url(SPONSOR_URL)" in source


def test_tui_settings_exposes_attribution_and_clickable_links():
    source = _source("src/modules/tui/settings_tab.py")

    assert "ATTRIBUTION" in source
    assert "about-source" in source
    assert "about-sponsor" in source
    assert "self.app._open_url(SOURCE_URL)" in source
    assert "self.app._open_url(SPONSOR_URL)" in source


def test_sponsor_is_only_exposed_in_about_and_license_surfaces():
    gui_main = _source("src/modules/gui/main.py")
    tui_main = _source("src/modules/tui/main.py")
    gui_settings = _source("src/modules/gui/settings_tab.py")
    tui_settings = _source("src/modules/tui/settings_tab.py")

    assert "sponsor_btn" not in gui_main
    assert "bb-sponsor" not in tui_main
    assert "action_sponsor" not in tui_main
    assert "self.app._open_url(SPONSOR_URL)" in gui_settings
    assert "self.app._open_url(SPONSOR_URL)" in tui_settings


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
