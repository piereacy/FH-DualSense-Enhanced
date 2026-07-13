import runpy
import hashlib
import tomllib
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "FH-DualSense-Enhanced"
ZUV_NAME = f"{APP_NAME}.zuv.py"


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_shared_application_identity_is_enhanced():
    about = runpy.run_path(str(ROOT / "src/modules/about.py"))
    project = tomllib.loads(_source("src/pyproject.toml"))

    assert about["APP_NAME"] == APP_NAME
    assert project["project"]["name"] == "fh-dualsense-enhanced"


def test_runtime_surfaces_use_the_shared_enhanced_name():
    for path in (
        "src/main.py",
        "src/modules/gui/main.py",
        "src/modules/gui/tray.py",
        "src/modules/tui/main.py",
    ):
        source = _source(path)
        assert "APP_NAME" in source, f"{path} does not use APP_NAME"


def test_runtime_chrome_does_not_link_to_original_release_updates():
    original_releases = "Forza-Horizon-DualSense-Python/releases/latest"

    assert original_releases not in _source("src/modules/gui/main.py")
    assert original_releases not in _source("src/modules/tui/main.py")


def test_standalone_modes_do_not_show_zuv_update_controls():
    gui = _source("src/modules/gui/system_tab.py")
    tui = _source("src/modules/tui/system_tab.py")

    assert "if sentinel_path() is not None:" in gui
    assert "if sentinel_path() is not None:" in tui
    assert "ZUV not found:" not in gui
    assert "ZUV not found:" not in tui


def test_windows_launcher_downloads_or_reuses_the_enhanced_bundle():
    launcher = _source("win_start.bat")

    assert ZUV_NAME in launcher
    assert 'set "REPO=piereacy/FH-DualSense-Enhanced"' in launcher
    assert 'set "APP=%DIR%app"' in launcher
    assert f'set "MANUAL=%DIR%{ZUV_NAME}"' in launcher
    assert f"releases/latest/download/{ZUV_NAME}" in launcher
    assert "curl.exe -L --fail" in launcher
    assert 'if exist "%MANUAL%"' in launcher
    assert "where uv" in launcher
    assert "https://astral.sh/uv/install.ps1" in launcher
    assert "UV_PYTHON_PREFERENCE=only-managed" in launcher
    assert "HamzaYslmn/Forza-Horizon-DualSense-Python" not in launcher


def test_linux_launcher_downloads_or_reuses_the_enhanced_bundle():
    launcher = _source("linux_start.sh")

    assert ZUV_NAME in launcher
    assert 'REPO="piereacy/FH-DualSense-Enhanced"' in launcher
    assert 'APP="$ROOT/app"' in launcher
    assert f'MANUAL="$ROOT/{ZUV_NAME}"' in launcher
    assert f"releases/latest/download/{ZUV_NAME}" in launcher
    assert "curl -LsSf --fail" in launcher
    assert "HamzaYslmn/Forza-Horizon-DualSense-Python" not in launcher


def test_local_zuv_builder_has_optional_update_repo_and_release_notices():
    path = ROOT / "packaging/zuv/build_zuv.bat"

    assert path.exists(), "local ZUV build script is missing"
    source = path.read_text(encoding="utf-8")
    assert ZUV_NAME in source
    assert "UPDATE_REPO" in source
    assert "--update-repo" in source
    assert "LICENSE" in source
    assert "THIRD_PARTY_NOTICES.md" in source


def test_github_release_uses_the_current_fork_as_zuv_update_source():
    workflow = _source(".github/workflows/release.yml")

    assert f"release/{ZUV_NAME}" in workflow
    assert '--update-repo "$GITHUB_REPOSITORY"' in workflow
    assert "FH-DualSense-Enhanced-$tag.exe" in workflow
    assert "HamzaYslmn/Forza-Horizon-DualSense-Python" not in workflow
    assert "Download **`win_start.bat`**" in workflow
    assert "manual ZUV fallback" in workflow


def test_windows_packaging_emits_the_enhanced_executable_name():
    spec = _source("packaging/windows/fhds.spec")
    build = _source("packaging/windows/build_exe.bat")
    linux_spec = _source("packaging/linux/fhds.spec")

    assert 'name="FH-DualSense-Enhanced"' in spec
    assert "FH-DualSense-Enhanced-v%VER%.exe" in build
    assert 'name="FH-DualSense-Enhanced"' in linux_spec


def test_root_readme_is_chinese_with_an_english_switch_and_release_guidance():
    english_path = ROOT / "README_EN.md"

    assert english_path.exists(), "English README is missing"
    chinese = _source("README.md")
    english = _source("README_EN.md")
    assert "简体中文" in chinese
    assert "README_EN.md" in chinese
    assert "English" in english
    assert "README.md" in english
    assert "只需下载" in chinese and "win_start.bat" in chinese
    assert "manual" in english.lower() and ZUV_NAME in english
    assert "社区" in chinese
    assert "community" in english.lower()


def test_readmes_are_original_enhanced_project_documentation():
    chinese = _source("README.md")
    english = _source("README_EN.md")
    combined = chinese + "\n" + english

    for text in (
        "Steam Input",
        "Data Out",
        "5300",
        "win_start.bat",
        ZUV_NAME,
        "USB",
        "Bluetooth",
        "HorizonHaptics",
    ):
        assert text.lower() in combined.lower()

    for forbidden in (
        "steamcommunity.com/id/teccno",
        "tradeoffer",
        "youtube.com/watch",
        "github.com/sponsors",
        "Jared (jmac122)",
        "2323",
        "docs/ReadmeTR.md",
        "docs/ReadmeJA.md",
    ):
        assert forbidden not in combined
    assert "sponsor" not in combined.lower()

    assert 'href="README_EN.md"' in chinese
    assert 'href="README.md"' in english
    assert "防火墙" in chinese
    assert "firewall" in english.lower()


def test_release_identity_is_the_enhanced_post_release():
    project = tomllib.loads(_source("src/pyproject.toml"))
    workflow = _source(".github/workflows/release.yml")

    assert project["project"]["version"] == "1.6.2.post1"
    assert "FH-DualSense-Enhanced 1.6.2 Enhanced R1" in workflow
    assert "v1.6.2.post1" in workflow


def test_selected_icon_is_used_by_all_application_surfaces():
    icon = ROOT / "src/data/icon.ico"
    png = ROOT / "src/data/icon.png"

    assert hashlib.sha256(icon.read_bytes()).hexdigest().upper() == (
        "FF195DE9560D31D3A5646206D73B55844F69FF3BDB99618CAA2414ACF423852B"
    )
    with Image.open(icon) as image:
        assert sorted(image.info["sizes"]) == [
            (16, 16),
            (24, 24),
            (32, 32),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256),
        ]
    with Image.open(png).convert("RGB") as image:
        white_pixels = sum(
            red > 240 and green > 240 and blue > 240
            for red, green, blue in image.crop(
                (0, 700, 250, 1024)
            ).get_flattened_data()
        )
        assert white_pixels > 5000

    assert 'ICON = SRC / "data" / "icon.ico"' in _source(
        "packaging/windows/fhds.spec"
    )
    assert "paths.ICON_ICO" in _source("src/modules/gui/main.py")
    assert "paths.ICON_PNG" in _source("src/modules/gui/main.py")
    assert "paths.ICON_PNG" in _source("src/modules/gui/tray.py")
