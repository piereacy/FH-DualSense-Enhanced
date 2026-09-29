import ast
import runpy
from pathlib import Path

from modules.gui.controls_tab import responsive_column_count
from modules.gui.settings_tab import logical_widget_width
from modules.gui.settings_tab import responsive_hint_wraplength
from modules.gui.settings_tab import responsive_switch_placements
from modules.gui.widgets import wrapped_label_height


ROOT = Path(__file__).resolve().parents[2]


def _constant_translation_keys() -> set[str]:
    keys = set()
    sources = list((ROOT / "src/modules/gui").glob("*.py"))
    sources.extend((ROOT / "src/modules/tui").glob("*.py"))
    sources.append(ROOT / "src/modules/xinput/service.py")
    sources.append(
        ROOT / "src/modules/forzahorizon/fh6_language_presentation.py"
    )
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"t", "translate"}
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                keys.add(node.args[0].value)
    return keys


def test_single_gui_shell_and_windows_asset_are_canonical():
    main = (ROOT / "src/modules/gui/main.py").read_text(encoding="utf-8")
    overview = (ROOT / "src/modules/gui/overview_tab.py").read_text(encoding="utf-8")
    spec = (ROOT / "packaging/windows/fhds.spec").read_text(encoding="utf-8")
    build = (ROOT / "packaging/windows/build_exe.bat").read_text(encoding="utf-8")

    assert not (ROOT / "src/modules/gui/variants.py").exists()
    assert "self.root.title(APP_NAME)" in main
    assert '"Logs", "About"' in main
    assert "workspace" not in overview.lower()
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


def test_trigger_master_and_shared_cards_span_full_width_around_pedal_pair():
    titles = (
        "Trigger feedback",
        "L2 - Brake",
        "R2 - Throttle",
        "Shared trigger feedback",
    )
    full_width = frozenset({"Trigger feedback", "Shared trigger feedback"})

    assert responsive_switch_placements(titles, 2, full_width) == (
        (0, 0, 2),
        (1, 0, 1),
        (1, 1, 1),
        (2, 0, 2),
    )
    assert responsive_switch_placements(titles, 1, full_width) == (
        (0, 0, 1),
        (1, 0, 1),
        (2, 0, 1),
        (3, 0, 1),
    )


def test_feedback_helper_text_wraps_to_each_card_interior():
    assert logical_widget_width(590, 1.25) == 472
    assert logical_widget_width(468, 1.0) == 468
    assert responsive_hint_wraplength(468, 20) == 428
    assert responsive_hint_wraplength(700, 20) == 660
    assert responsive_hint_wraplength(1, 20) == 1

    source = (ROOT / "src/modules/gui/settings_tab.py").read_text(encoding="utf-8")
    assert 'card.bind(' in source
    assert '"<Configure>"' in source
    assert "hint.configure(wraplength=wrap)" in source
    assert 'fill="x"' in source
    assert "self.app.px(520)" not in source


def test_wrapped_helper_text_grows_tall_enough_for_every_line():
    assert wrapped_label_height(46, 1.0) == 46
    assert wrapped_label_height(46, 2.0) == 28
    assert wrapped_label_height(70, 2.0, minimum_height=30) == 35

    source = (ROOT / "src/modules/gui/widgets.py").read_text(encoding="utf-8")
    assert "self.after_idle(self._fit_wrapped_height)" in source
    assert "self._label.winfo_reqheight()" in source


def test_feedback_resize_is_debounced_and_reuses_existing_grid_items():
    source = (ROOT / "src/modules/gui/settings_tab.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    settings_tab = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SettingsTab"
    )
    resize_debounce = next(
        node.value
        for node in settings_tab.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "RESIZE_DEBOUNCE_MS"
            for target in node.targets
        )
    )
    layout = next(
        node
        for node in settings_tab.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_apply_responsive_layout"
    )
    calls = {
        node.func.attr
        for node in ast.walk(layout)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert ast.literal_eval(resize_debounce) == 80
    assert "grid" in calls
    assert "grid_forget" not in calls


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


def test_lab_and_hidhide_backend_lifetime_messages_are_translated():
    required = {
        (
            "The lab never starts virtual Xbox input, Raw Input, or HidHide. "
            "Live game telemetry takes priority, and every preview stops automatically."
        ),
        "Connect or reconnect the DualSense to apply isolation",
    }
    removed = {
        "Controller output is off unless FH4, FH5, or FH6 is in the foreground",
        "Isolation starts only while FH4, FH5, or FH6 is in the foreground",
    }

    for locale in ("de", "ja", "ru", "tr", "zh", "zh_tw"):
        strings = runpy.run_path(str(ROOT / f"src/lang/{locale}.py"))["STRINGS"]
        assert required <= strings.keys()
        assert removed.isdisjoint(strings)



def test_hidhide_help_covers_one_click_installation_in_every_language():
    keys = _constant_translation_keys()
    install_help = next(key for key in keys if key.startswith("Xbox App only. Install HidHide"))
    assert "signed driver" in install_help
    assert "configures the current DualSense automatically" in install_help
    for locale in ("de", "ja", "ru", "tr", "zh", "zh_tw"):
        strings = runpy.run_path(str(ROOT / f"src/lang/{locale}.py"))["STRINGS"]
        assert strings[install_help]
        assert strings["Install HidHide and enable isolation"]
