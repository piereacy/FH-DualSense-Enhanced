import asyncio
from pathlib import Path
import runpy

import pytest

from modules.config.settings import Settings
from modules.xinput.mapping import (
    DEFAULT_BUTTON_MAPPING,
    MAPPING_SETTING_FIELDS,
    MAPPING_SOURCE_GROUPS,
    MAPPING_SOURCES,
    MAPPING_TARGETS,
    XInputButtonMapping,
    active_mapping_from_settings,
    configured_mapping_from_settings,
    normalize_mapping_settings,
    normalize_mapping_target,
    reset_mapping_settings,
)
from modules.xinput.gyro import (
    GYRO_ACTIVATION_OPTIONS,
    GYRO_HORIZONTAL_OPTIONS,
    GYRO_MODE_OPTIONS,
    GYRO_OUTPUT_OPTIONS,
)


ROOT = Path(__file__).resolve().parents[2]


def test_default_mapping_defines_every_source_once():
    settings = Settings()
    assert len(MAPPING_SETTING_FIELDS) == len(MAPPING_SOURCES)
    assert len(DEFAULT_BUTTON_MAPPING.targets) == len(MAPPING_SOURCES)
    assert all(
        getattr(settings, source.setting) == source.default_target
        for source in MAPPING_SOURCES
    )
    assert DEFAULT_BUTTON_MAPPING.target_for("create") == "back"
    assert DEFAULT_BUTTON_MAPPING.target_for("options") == "start"
    assert DEFAULT_BUTTON_MAPPING.target_for("touchpad_left") == "back"
    assert DEFAULT_BUTTON_MAPPING.target_for("touchpad_right") == "start"


def test_mapping_value_validation_is_strict_and_source_specific():
    assert normalize_mapping_target("Y", "a") == "y"
    assert normalize_mapping_target("not-an-xbox-button", "back") == "back"

    with pytest.raises(ValueError, match="every button source"):
        XInputButtonMapping(("a",))
    with pytest.raises(ValueError, match="Unknown XInput mapping target"):
        XInputButtonMapping(tuple("invalid" for _source in MAPPING_SOURCES))


def test_custom_values_are_dormant_until_experimental_opt_in():
    settings = Settings(xinput_mapping_cross="y")

    assert configured_mapping_from_settings(settings).target_for("cross") == "y"
    assert active_mapping_from_settings(settings).target_for("cross") == "a"

    settings.enable_custom_xinput_mapping = True
    assert active_mapping_from_settings(settings).target_for("cross") == "y"


def test_invalid_saved_value_falls_back_without_poisoning_other_sources():
    settings = Settings(
        enable_custom_xinput_mapping=True,
        xinput_mapping_cross="future_button",
        xinput_mapping_circle="x",
    )

    mapping = active_mapping_from_settings(settings)

    assert mapping.target_for("cross") == "a"
    assert mapping.target_for("circle") == "x"

    assert normalize_mapping_settings(settings) is True
    assert settings.xinput_mapping_cross == "a"
    assert settings.xinput_mapping_circle == "x"
    assert normalize_mapping_settings(settings) is False


def test_restore_defaults_keeps_opt_in_state_and_is_idempotent():
    settings = Settings(
        enable_custom_xinput_mapping=True,
        xinput_mapping_cross="off",
        xinput_mapping_touchpad_right="guide",
    )

    assert reset_mapping_settings(settings) is True
    assert settings.enable_custom_xinput_mapping is True
    assert active_mapping_from_settings(settings) == DEFAULT_BUTTON_MAPPING
    assert reset_mapping_settings(settings) is False


def test_gui_and_tui_render_the_shared_mapping_schema_and_live_refresh_service():
    for relative in (
        "src/modules/gui/xinput_mapping_tab.py",
        "src/modules/tui/xinput_mapping_tab.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "MAPPING_SOURCE_GROUPS" in source
        assert "enable_custom_xinput_mapping" in source
        assert "reset_mapping_settings" in source
        assert "refresh_button_mapping" in source
        assert "refresh_gyro_mapping" in source
        assert "custom_xinput_mapping_available" in source


def test_mapping_is_a_standalone_top_level_page_in_both_frontends():
    gui_main = (ROOT / "src/modules/gui/main.py").read_text(encoding="utf-8")
    tui_main = (ROOT / "src/modules/tui/main.py").read_text(encoding="utf-8")
    gui_system = (ROOT / "src/modules/gui/system_tab.py").read_text(encoding="utf-8")
    tui_system = (ROOT / "src/modules/tui/system_tab.py").read_text(encoding="utf-8")

    assert '"XboxMapping": "Custom Xbox button mapping"' in gui_main
    assert '"XboxMapping": self.xinput_mapping_tab' in gui_main
    assert 'id="tab-xinput-mapping"' in tui_main
    assert "XInputMappingTab" in gui_main
    assert "XInputMappingTab" in tui_main
    assert "MAPPING_SOURCE_GROUPS" not in gui_system
    assert "MAPPING_SOURCE_GROUPS" not in tui_system
    assert "xinput_mapping" not in gui_system
    assert "xinput_mapping" not in tui_system
    assert "xinput-mapping-settings" not in gui_system
    assert "xinput-mapping-settings" not in tui_system


def test_standalone_tui_mapping_page_mounts_directly_and_tracks_platform_gate():
    from textual.app import App, ComposeResult
    from textual.widgets import Button, Select, Switch

    from modules.tui.xinput_mapping_tab import XInputMappingTab

    class Service:
        def __init__(self):
            self.button_refreshes = 0
            self.gyro_refreshes = 0

        def refresh_button_mapping(self):
            self.button_refreshes += 1

        def refresh_gyro_mapping(self):
            self.gyro_refreshes += 1

    class MappingHarness(App):
        def __init__(self, settings):
            super().__init__()
            self.settings = settings
            self._xinput_service = Service()
            self._refreshing = False

        def compose(self) -> ComposeResult:
            yield XInputMappingTab(self.settings)

        def refresh_setting_widgets(self):
            pass

    async def check():
        settings = Settings(preferred_forza_platform="steam")
        app = MappingHarness(settings)
        async with app.run_test():
            page = app.query_one(XInputMappingTab)
            assert len(list(page.query(Select))) == len(MAPPING_SOURCES) + 4
            assert page.query_one("#enable_custom_xinput_mapping", Switch).disabled
            assert page.query_one("#xinput-mapping-restore", Button).disabled

            settings.preferred_forza_platform = "xbox_app"
            page.on_show()

            assert not page.query_one("#enable_custom_xinput_mapping", Switch).disabled
            assert not page.query_one("#xinput-mapping-restore", Button).disabled
            assert page.query_one("#enable_xinput_gyro", Switch).disabled
            assert page.query_one("#xinput_gyro_mode", Select).disabled
            assert all(
                page.query_one(f"#{source.setting}", Select).disabled
                for source in MAPPING_SOURCES
            )

            settings.enable_custom_xinput_mapping = True
            page.on_show()

            assert all(
                not page.query_one(f"#{source.setting}", Select).disabled
                for source in MAPPING_SOURCES
            )
            assert not page.query_one("#enable_xinput_gyro", Switch).disabled
            assert page.query_one("#xinput_gyro_mode", Select).disabled
            assert page.query_one("#xinput_gyro_output_stick", Select).disabled

            settings.enable_xinput_gyro = True
            page.on_show()

            assert not page.query_one("#xinput_gyro_mode", Select).disabled
            assert not page.query_one("#xinput_gyro_output_stick", Select).disabled
            assert app._xinput_service.button_refreshes >= 1
            assert app._xinput_service.gyro_refreshes >= 1

    asyncio.run(check())


def test_every_non_english_catalog_translates_xinput_mapping_surface():
    required = {
        "Custom Xbox button mapping",
        (
            "Customize the buttons and Steam Input-style motion sent by the "
            "Xbox App bridge. L2/R2 remain unchanged."
        ),
        "Enable custom Xbox mapping",
        "Restore Steam defaults",
        "Gyro behavior",
        "Enable gyro",
        (
            "Enable custom Xbox mapping first; gyro is controlled by that "
            "master switch."
        ),
        "Gyro mode",
        "Output joystick",
        "Gyro activation",
        "Horizontal motion axis",
        "Full-stick camera speed (deg/s)",
        "Full-stick deflection angle (deg)",
        "Gyro deadzone (deg/s)",
        "Gyro smoothing (ms)",
        "Enable vertical gyro output",
        "Invert horizontal gyro",
        "Invert vertical gyro",
        (
            "Virtual Xbox 360 controllers have no motion channel, so FHDS "
            "converts DualSense motion into additive joystick output."
        ),
        (
            "Select Xbox App as the Forza platform to customize buttons here. "
            "If you use the Steam version, change your controller mapping in Steam."
        ),
        "Keyboard and mouse active",
        "Virtual Xbox input is neutral; move or press the DualSense to resume",
    }
    required.update(group for group, _sources in MAPPING_SOURCE_GROUPS)
    required.update(source.label for source in MAPPING_SOURCES)
    required.update(target.label for target in MAPPING_TARGETS)
    required.update(
        option.label
        for options in (
            GYRO_MODE_OPTIONS,
            GYRO_OUTPUT_OPTIONS,
            GYRO_ACTIVATION_OPTIONS,
            GYRO_HORIZONTAL_OPTIONS,
        )
        for option in options
    )

    for path in sorted((ROOT / "src/lang").glob("*.py")):
        if path.name in {"__init__.py", "en.py"}:
            continue
        strings = runpy.run_path(str(path))["STRINGS"]
        assert required <= strings.keys(), path.name
        assert all(strings[key] for key in required), path.name
        target_labels = [strings[target.label] for target in MAPPING_TARGETS]
        assert len(target_labels) == len(set(target_labels)), path.name
