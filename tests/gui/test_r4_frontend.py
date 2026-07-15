import ast
import runpy
from pathlib import Path

from modules.gui.variants import VARIANTS, current_variant


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


def test_three_frontend_variants_share_one_runtime_selector(monkeypatch):
    assert tuple(VARIANTS) == ("console", "stage", "studio")
    assert VARIANTS["console"].navigation == "side"
    assert VARIANTS["stage"].navigation == "top"
    assert VARIANTS["studio"].compact_nav is True

    for key, expected in VARIANTS.items():
        monkeypatch.setenv("FHDS_UI_VARIANT", key)
        assert current_variant() == expected

    monkeypatch.setenv("FHDS_UI_VARIANT", "unknown")
    assert current_variant() == VARIANTS["console"]


def test_windows_spec_bundles_variant_marker_and_update_helper_once_per_exe():
    spec = (ROOT / "packaging/windows/fhds.spec").read_text(encoding="utf-8")

    assert "FHDS_BUILD_VARIANT" in spec
    assert "ui_variant.txt" in spec
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
