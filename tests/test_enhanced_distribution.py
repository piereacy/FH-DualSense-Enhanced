import runpy
import hashlib
import tomllib
from pathlib import Path

from PIL import Image

from modules.config import preferences


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "FH-DualSense-Enhanced"
ZUV_NAME = f"{APP_NAME}.zuv.py"
CURRENT_INTERNAL_VERSION = "4"
CURRENT_RELEASE_VERSION = "R4"


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
    assert preferences._release_version() == CURRENT_RELEASE_VERSION

    for path in ("src/modules/gui/main.py", "src/modules/tui/main.py"):
        source = _source(path)
        assert "_release_version" in source
        assert 'f"v{_version()' not in source


def test_runtime_chrome_does_not_link_to_original_release_updates():
    original_releases = "Forza-Horizon-DualSense-Python/releases/latest"

    assert original_releases not in _source("src/modules/gui/main.py")
    assert original_releases not in _source("src/modules/tui/main.py")


def test_standalone_modes_show_builtin_update_controls_without_zuv_gate():
    gui = _source("src/modules/gui/system_tab.py")
    tui = _source("src/modules/tui/system_tab.py")

    assert "sentinel_path" not in gui
    assert "sentinel_path" not in tui
    assert "UpdatePhase" in gui
    assert "UpdatePhase" in tui
    assert "Automatically check for updates" in gui
    assert "Automatically check for updates" in tui
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
    english = _source("README.md")
    chinese = _source("docs/ReadmeZH.md")
    japanese = _source("docs/ReadmeJA.md")
    workflow = _source(".github/workflows/release.yml")

    for text in (chinese, english, japanese, workflow):
        assert "70-dualsense.rules" in text
    for text in (chinese, english, japanese):
        assert "sudo udevadm control --reload-rules" not in text

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
    assert "packaging\\windows\\build_exe.bat" in workflow
    assert "HamzaYslmn/Forza-Horizon-DualSense-Python" not in workflow
    assert "Windows 独立 EXE（推荐）" in workflow
    assert "win_start.bat" in workflow
    assert "ZUV / Linux 备用方式" in workflow
    assert "FH-DualSense-Enhanced-{0}.exe" in workflow
    assert "Miku-Stage" not in workflow
    assert "Miku-Studio" not in workflow
    assert "Miku Console" not in workflow
    assert "FH-DualSense-Enhanced.zuv.py" in workflow
    assert "Enhanced R4 中文说明" in workflow
    assert "握把换挡冲击" in workflow
    assert "默认关闭 R2 扳机键红线、开启握把红线" in workflow
    assert "Forza-Horizon-DualSense-Python 1.6.2" in workflow
    assert "HorizonHaptics 1.3.0" in workflow


def test_windows_packaging_emits_the_enhanced_executable_name():
    spec = _source("packaging/windows/fhds.spec")
    build = _source("packaging/windows/build_exe.bat")
    linux_spec = _source("packaging/linux/fhds.spec")

    assert "name=EXE_NAME" in spec
    assert "Miku-Stage" not in spec
    assert "Miku-Studio" not in spec
    assert "FH-DualSense-Enhanced-R%VER%.exe" in build
    assert "FH-DualSense-Update-Helper.exe" in spec
    assert "FH-DualSense-Update-Helper" in build
    assert "$p+'.sha256'" in build
    assert "PUBLIC_VERSION = f\"R{VERSION}\"" in spec
    assert "StringStruct('FileVersion', '{PUBLIC_VERSION}')" in spec
    assert "StringStruct('ProductVersion', '{PUBLIC_VERSION}')" in spec
    assert 'name="FH-DualSense-Enhanced"' in linux_spec
    assert "FH-DualSense-Enhanced-R$VER" in _source("packaging/linux/build_elf.sh")


def test_readme_defaults_to_english_with_separate_language_pages():
    assert not (ROOT / "README_EN.md").exists(), "obsolete root English README remains"
    assert not (ROOT / "docs/ReadmeEN.md").exists(), "duplicate English README remains"
    assert not (ROOT / "docs/ReadmeTR.md").exists(), "obsolete Turkish README remains"
    english = _source("README.md")
    chinese = _source("docs/ReadmeZH.md")
    japanese = _source("docs/ReadmeJA.md")

    assert '<strong>English</strong>' in english
    assert 'href="docs/ReadmeZH.md">简体中文</a>' in english
    assert 'href="docs/ReadmeJA.md">日本語</a>' in english
    assert 'href="../README.md">English</a>' in chinese
    assert '<strong>简体中文</strong>' in chinese
    assert 'href="ReadmeJA.md">日本語</a>' in chinese
    assert 'href="../README.md">English</a>' in japanese
    assert 'href="ReadmeZH.md">简体中文</a>' in japanese
    assert '<strong>日本語</strong>' in japanese

    for text in (english, chinese, japanese):
        assert "FH-DualSense-Enhanced-R<n>.exe" in text
        assert "win_start.bat" in text
    assert "manual" in english.lower() and ZUV_NAME in english
    assert "手动" in chinese and ZUV_NAME in chinese
    assert "手動" in japanese and ZUV_NAME in japanese
    assert "社区" in chinese
    assert "community" in english.lower()
    assert "コミュニティ" in japanese


def test_readmes_are_original_enhanced_project_documentation():
    english = _source("README.md")
    chinese = _source("docs/ReadmeZH.md")
    japanese = _source("docs/ReadmeJA.md")
    combined = chinese + "\n" + english + "\n" + japanese

    for readme in (chinese, english, japanese):
        for text in (
            "Steam Input",
            "Data Out",
            "5300",
            "win_start.bat",
            ZUV_NAME,
            "USB",
            "Bluetooth",
            "HorizonHaptics",
            "Forza-Horizon-DualSense-Python 1.6.2",
        ):
            assert text.lower() in readme.lower()

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
    assert "1.6.2.post1" not in combined


def test_readmes_explicitly_compare_enhanced_with_upstream_1_6_2():
    english = _source("README.md")
    chinese = _source("docs/ReadmeZH.md")
    japanese = _source("docs/ReadmeJA.md")

    sections = (
        (english, "## What Enhanced adds over upstream 1.6.2", "## Download"),
        (chinese, "## 相比上游 1.6.2 的增强", "## 下载"),
        (japanese, "## アップストリーム 1.6.2 からの拡張", "## ダウンロード"),
    )
    for text, heading, next_heading in sections:
        assert heading in text
        body = text.split(heading, 1)[1].split(next_heading, 1)[0]
        bullets = [line for line in body.splitlines() if line.startswith("- ")]
        assert 4 <= len(bullets) <= 6
        assert "Bluetooth" in body
        assert "1.6.2" not in body


def test_readmes_stay_concise_and_avoid_implementation_details():
    english = _source("README.md")
    chinese = _source("docs/ReadmeZH.md")
    japanese = _source("docs/ReadmeJA.md")
    combined = "\n".join((english, chinese, japanese))

    for text in (chinese, english, japanese):
        assert len(text.splitlines()) <= 120
        assert "FH-DualSense-Enhanced-R<n>.exe" in text
        assert "Miku Console" not in text
        assert "Miku-Stage" not in text
        assert "Miku-Studio" not in text
        assert "wheelspin" in text.lower()
    assert len(english.split()) <= 900

    for detail in (
        "Background behavior",
        "后台行为",
        "バックグラウンド動作",
        "HapticPcmRenderer",
        "report `0x36`",
        "398 字节",
        "单槽最新帧队列",
        "R4-preview",
        "ABS wall",
        "1.6.2.post1",
    ):
        assert detail not in combined


def test_readmes_require_in_game_vibration_off_but_keep_steam_input_on():
    english = _source("README.md")
    chinese = _source("docs/ReadmeZH.md")
    japanese = _source("docs/ReadmeJA.md")

    for text in (english, chinese, japanese):
        assert "> [!IMPORTANT]" in text

    assert "Keep Steam Input enabled" in english
    assert "turn **Vibration** off" in english
    assert "grip feedback will not work correctly" in english

    assert "Steam Input 必须保持开启" in chinese
    assert "必须在 Forza 游戏设置中关闭“振动”" in chinese
    assert "握把反馈无法正常工作" in chinese

    assert "Steam Input は有効のまま" in japanese
    assert "「振動」は必ず無効" in japanese
    assert "握把フィードバックが正常に動作しません" in japanese


def test_release_identity_uses_public_r4_and_internal_pep440_version():
    project = tomllib.loads(_source("src/pyproject.toml"))
    workflow = _source(".github/workflows/release.yml")

    assert project["project"]["version"] == CURRENT_INTERNAL_VERSION
    assert 'tags: ["R*", "v*.*.*"]' in workflow
    assert "release[[:space:]]+(R[0-9]+)" in workflow
    assert 'tag="${release}-preview"' in workflow
    assert 'title="FH-DualSense-Enhanced ${release} Preview"' in workflow
    assert 'title="FH-DualSense-Enhanced $tag"' in workflow
    assert "RELEASE_CHANNEL: ${{ github.event.inputs.channel }}" in workflow
    assert '"$RELEASE_CHANNEL" == "stable"' in workflow
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
