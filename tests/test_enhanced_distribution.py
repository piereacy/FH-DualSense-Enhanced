import runpy
import hashlib
import tomllib
from pathlib import Path

from PIL import Image

from modules.config import preferences


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "FH-DualSense-Enhanced"
ZUV_NAME = f"{APP_NAME}.zuv.py"
INTERNAL_VERSION = "2"
RELEASE_VERSION = "R2"


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


def test_runtime_surfaces_map_internal_version_to_public_release_version():
    assert preferences._release_version() == RELEASE_VERSION

    for path in ("src/modules/gui/main.py", "src/modules/tui/main.py"):
        source = _source(path)
        assert "_release_version" in source
        assert 'f"v{_version()' not in source


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


def test_linux_docs_describe_manual_udev_setup_without_launcher_claims():
    chinese = _source("README.md")
    english = _source("docs/ReadmeEN.md")
    japanese = _source("docs/ReadmeJA.md")
    workflow = _source(".github/workflows/release.yml")

    for text in (chinese, english, japanese, workflow):
        assert "70-dualsense.rules" in text
    for text in (chinese, english, japanese):
        assert "sudo udevadm control --reload-rules" in text

    assert "启动器会给出安装提示" not in chinese
    assert "launcher provides setup guidance" not in english
    assert "ランチャーにセットアップ案内が表示されます" not in japanese
    assert "launcher offers to install" not in workflow


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
    assert "FH-DualSense-Enhanced.zuv.py" in workflow


def test_windows_packaging_emits_the_enhanced_executable_name():
    spec = _source("packaging/windows/fhds.spec")
    build = _source("packaging/windows/build_exe.bat")
    linux_spec = _source("packaging/linux/fhds.spec")

    assert 'name="FH-DualSense-Enhanced"' in spec
    assert "FH-DualSense-Enhanced-R%VER%.exe" in build
    assert "PUBLIC_VERSION = f\"R{VERSION}\"" in spec
    assert "StringStruct('FileVersion', '{PUBLIC_VERSION}')" in spec
    assert "StringStruct('ProductVersion', '{PUBLIC_VERSION}')" in spec
    assert 'name="FH-DualSense-Enhanced"' in linux_spec
    assert "FH-DualSense-Enhanced-R$VER" in _source("packaging/linux/build_elf.sh")


def test_readme_uses_same_page_three_language_navigation():
    assert not (ROOT / "README_EN.md").exists(), "obsolete root English README remains"
    assert not (ROOT / "docs/ReadmeTR.md").exists(), "obsolete Turkish README remains"
    chinese = _source("README.md")
    english = _source("docs/ReadmeEN.md")
    japanese = _source("docs/ReadmeJA.md")

    assert '<a id="readme-zh-cn"></a>' in chinese
    assert '<a id="readme-en"></a>' in chinese
    assert '<a id="readme-ja"></a>' in chinese
    assert '<strong>简体中文</strong>' in chinese
    assert 'href="#readme-zh-cn">简体中文</a>' in chinese
    assert 'href="#readme-en">English</a>' in chinese
    assert 'href="#readme-ja">日本語</a>' in chinese
    assert 'href="docs/ReadmeEN.md">English</a>' not in chinese
    assert 'href="docs/ReadmeJA.md">日本語</a>' not in chinese

    assert "只需下载" in chinese and "win_start.bat" in chinese
    assert "manual" in english.lower() and ZUV_NAME in english
    assert "手動" in japanese and ZUV_NAME in japanese
    assert "社区" in chinese
    assert "community" in english.lower()
    assert "コミュニティ" in japanese


def test_readmes_are_original_enhanced_project_documentation():
    chinese = _source("README.md")
    english = _source("docs/ReadmeEN.md")
    japanese = _source("docs/ReadmeJA.md")
    combined = chinese + "\n" + english + "\n" + japanese

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
    ):
        assert forbidden not in combined
    assert "sponsor" not in combined.lower()

    assert "防火墙" in chinese
    assert "firewall" in english.lower()
    assert "ファイアウォール" in japanese
    assert "握把触覚" in japanese
    for text in (chinese, english, japanese):
        assert RELEASE_VERSION in text
        assert "Forza-Horizon-DualSense-Python 1.6.2" in text
        assert "HorizonHaptics 1.3.0" in text
        assert "1.6.2.post1" in text


def test_readmes_describe_r2_features_and_public_artifact_names():
    chinese = _source("README.md")
    english = _source("docs/ReadmeEN.md")
    japanese = _source("docs/ReadmeJA.md")

    for text in (chinese, english, japanese):
        assert "FH-DualSense-Enhanced-R2.exe" in text
        assert "wheelspin" in text.lower()
        assert "ABS wall" in text
        assert "R2-preview" in text


def test_release_identity_uses_public_r2_and_internal_pep440_version():
    project = tomllib.loads(_source("src/pyproject.toml"))
    workflow = _source(".github/workflows/release.yml")

    assert project["project"]["version"] == INTERNAL_VERSION
    assert 'tags: ["R*", "v*.*.*"]' in workflow
    assert "release[[:space:]]+(R[0-9]+)" in workflow
    assert 'tag="${release}-preview"' in workflow
    assert 'title="FH-DualSense-Enhanced ${release} Preview"' in workflow
    assert 'title="FH-DualSense-Enhanced $tag"' in workflow
    assert "refs/tags/v*" in workflow
    assert "v[0-9]+\\.[0-9]+\\.[0-9]+" in workflow


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
