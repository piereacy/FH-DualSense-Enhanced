import ast
import runpy
from pathlib import Path

from modules.gui.controls_tab import responsive_column_count


ROOT = Path(__file__).resolve().parents[2]


def _constant_translation_keys() -> set[str]:
    keys = set()
    for folder in (ROOT / "src/modules/gui", ROOT / "src/modules/tui"):
        for path in folder.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "t"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)
                ):
                    keys.add(node.args[0].value)
    return keys


def test_console_is_the_only_gui_shell_and_windows_asset_is_canonical():
    main = (ROOT / "src/modules/gui/main.py").read_text(encoding="utf-8")
    spec = (ROOT / "packaging/windows/fhds.spec").read_text(encoding="utf-8")
    build = (ROOT / "packaging/windows/build_exe.bat").read_text(encoding="utf-8")

    assert not (ROOT / "src/modules/gui/variants.py").exists()
    assert "Miku Console" in main
    assert "current_variant" not in main
    assert "FHDS_BUILD_VARIANT" not in spec
    assert "ui_variant.txt" not in spec
    assert 'EXE_NAME = f"FH-DualSense-Enhanced-{PUBLIC_VERSION}"' in spec
    assert "FH-DualSense-Enhanced-R%VER%.exe" in build
    assert "FH-DualSense-Update-Helper.exe" in spec


def test_driving_layout_switches_to_one_column_before_cards_clip():
    assert responsive_column_count(1040) == 2
    assert responsive_column_count(720) == 2
    assert responsive_column_count(719) == 1


def test_windows_spec_bundles_update_helper_once_per_exe():
    spec = (ROOT / "packaging/windows/fhds.spec").read_text(encoding="utf-8")

    assert "FH-DualSense-Update-Helper.exe" in spec
    assert "src/modules/gui/main.py" not in spec
    assert "main.py" in spec


def test_all_non_english_catalogs_cover_the_complete_gui_and_tui_surface():
    dynamic_update_keys = {
        "Built-in updates require the Windows standalone EXE",
        "Checking for updates",
        "You are up to date",
        "Update available: {tag}",
        "Downloading update",
        "Verifying update",
        "Update ready to install",
        "Restarting to install",
        "Update failed",
        "Built-in updater",
        "Windows EXE",
        "Unavailable in this runtime",
    }
    required = _constant_translation_keys() | dynamic_update_keys

    for path in sorted((ROOT / "src/lang").glob("*.py")):
        if path.name in {"__init__.py", "en.py"}:
            continue
        strings = runpy.run_path(str(path))["STRINGS"]
        missing = required - strings.keys()
        assert not missing, f"{path.name} is missing {sorted(missing)}"
