"""Standalone Xbox App button-mapping page."""

import logging

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Input, Label, Select, Switch

from lang import t
from modules.config import preferences
from modules.xinput.gyro import (
    GYRO_ACTIVATION_OPTIONS,
    GYRO_HORIZONTAL_OPTIONS,
    GYRO_MODE_OPTIONS,
    GYRO_OUTPUT_OPTIONS,
    normalize_gyro_settings,
    reset_gyro_settings,
)
from modules.xinput.mapping import (
    MAPPING_SOURCE_BY_SETTING,
    MAPPING_SOURCE_GROUPS,
    MAPPING_TARGETS,
    normalize_mapping_target,
    reset_mapping_settings,
)
from modules.xinput.service import custom_xinput_mapping_available

from .settings_tab import SettingsTab

log = logging.getLogger("fhds")


class XInputMappingTab(SettingsTab):
    """Render every digital mapping directly on its own top-level tab."""

    SWITCH_SECTIONS: tuple = ()
    SECTIONS: list = []
    EXPERIMENTAL_SECTIONS: tuple = ()
    SHOW_RESET = False
    SHOW_EXPERIMENTAL = False

    DEFAULT_CSS = """
    XInputMappingTab { width: 1fr; height: 1fr; padding: 1 2; }
    XInputMappingTab Label.section {
        text-style: bold;
        color: $accent;
        padding: 1 0 0 1;
        border-bottom: hkey $accent 30%;
    }
    XInputMappingTab Label.hint {
        width: 1fr;
        height: auto;
        color: $text-muted;
        padding: 0 1 1 1;
    }
    XInputMappingTab .row {
        height: 3;
        width: 1fr;
        align-vertical: middle;
        padding: 0 1;
    }
    XInputMappingTab .row Label.field {
        width: 32;
        height: 3;
        content-align: left middle;
    }
    XInputMappingTab .row Switch { margin-right: 2; }
    XInputMappingTab .row Select { width: 32; }
    XInputMappingTab .row Input { width: 14; }
    XInputMappingTab #xinput-mapping-restore { width: 1fr; margin: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Label(
            t(
                "Customize the buttons and Steam Input-style motion sent by the "
                "Xbox App bridge. L2/R2 remain unchanged."
            ),
            classes="hint",
        )
        yield Label(
            t(
                "Select Xbox App as the Forza platform to customize buttons here. "
                "If you use the Steam version, change your controller mapping in Steam."
            ),
            classes="hint",
        )
        mapping_available = self._customization_allowed()
        with Horizontal(classes="row"):
            yield Switch(
                value=self.settings.enable_custom_xinput_mapping,
                id="enable_custom_xinput_mapping",
                disabled=not mapping_available,
            )
            yield Label(t("Enable custom Xbox mapping"), classes="field")

        yield Label(t("Gyro behavior"), classes="section")
        yield Label(
            t(
                "Virtual Xbox 360 controllers have no motion channel, so FHDS "
                "converts DualSense motion into additive joystick output."
            ),
            classes="hint",
        )
        with Horizontal(classes="row"):
            yield Switch(
                value=bool(self.settings.enable_xinput_gyro),
                disabled=(
                    not mapping_available
                    or not self.settings.enable_custom_xinput_mapping
                ),
                id="enable_xinput_gyro",
            )
            yield Label(t("Enable gyro"), classes="field")
        yield Label(
            t(
                "Enable custom Xbox mapping first; gyro is controlled by that "
                "master switch."
            ),
            classes="hint",
        )
        for attr, label, values in (
            ("xinput_gyro_mode", "Gyro mode", GYRO_MODE_OPTIONS),
            ("xinput_gyro_output_stick", "Output joystick", GYRO_OUTPUT_OPTIONS),
            ("xinput_gyro_activation", "Gyro activation", GYRO_ACTIVATION_OPTIONS),
            ("xinput_gyro_horizontal_axis", "Horizontal motion axis", GYRO_HORIZONTAL_OPTIONS),
        ):
            with Horizontal(classes="row"):
                yield Label(t(label), classes="field")
                yield Select(
                    tuple((t(option.label), str(option.key)) for option in values),
                    value=str(getattr(self.settings, attr)),
                    allow_blank=False,
                    disabled=(
                        not mapping_available
                        or not self.settings.enable_custom_xinput_mapping
                        or not self.settings.enable_xinput_gyro
                    ),
                    id=attr,
                )
        for attr, label in (
            ("xinput_gyro_sensitivity_dps", "Full-stick camera speed (deg/s)"),
            ("xinput_gyro_deflection_angle", "Full-stick deflection angle (deg)"),
            ("xinput_gyro_deadzone_dps", "Gyro deadzone (deg/s)"),
            ("xinput_gyro_smoothing_ms", "Gyro smoothing (ms)"),
        ):
            with Horizontal(classes="row"):
                yield Label(t(label), classes="field")
                yield Input(
                    value=f"{float(getattr(self.settings, attr)):g}",
                    type="number",
                    disabled=(
                        not mapping_available
                        or not self.settings.enable_custom_xinput_mapping
                        or not self.settings.enable_xinput_gyro
                    ),
                    id=attr,
                )
        for attr, label in (
            ("xinput_gyro_vertical_enabled", "Enable vertical gyro output"),
            ("xinput_gyro_invert_horizontal", "Invert horizontal gyro"),
            ("xinput_gyro_invert_vertical", "Invert vertical gyro"),
        ):
            with Horizontal(classes="row"):
                yield Switch(
                    value=bool(getattr(self.settings, attr)),
                    disabled=(
                        not mapping_available
                        or not self.settings.enable_custom_xinput_mapping
                        or not self.settings.enable_xinput_gyro
                    ),
                    id=attr,
                )
                yield Label(t(label), classes="field")

        options = tuple((t(target.label), target.key) for target in MAPPING_TARGETS)
        for group, sources in MAPPING_SOURCE_GROUPS:
            yield Label(t(group), classes="section")
            for source in sources:
                target = normalize_mapping_target(
                    getattr(self.settings, source.setting),
                    source.default_target,
                )
                with Horizontal(classes="row"):
                    yield Label(t(source.label), classes="field")
                    yield Select(
                        options,
                        value=target,
                        allow_blank=False,
                        disabled=(
                            not mapping_available
                            or not self.settings.enable_custom_xinput_mapping
                        ),
                        id=source.setting,
                    )

        yield Button(
            t("Restore Steam defaults"),
            id="xinput-mapping-restore",
            disabled=not mapping_available,
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id and event.select.id.startswith("xinput_gyro_"):
            self._on_gyro_select(event)
            return
        source = MAPPING_SOURCE_BY_SETTING.get(event.select.id or "")
        if source is None:
            return
        if (
            getattr(self.app, "_refreshing", False)
            or not self._customization_allowed()
        ):
            self._sync_controls()
            return
        target = normalize_mapping_target(event.value, source.default_target)
        if getattr(self.settings, source.setting) != target:
            setattr(self.settings, source.setting, target)
            preferences.save(self.settings)
            log.info("%s = %s", source.setting, target)
        self._push_mapping()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        switch_id = event.switch.id or ""
        if (
            switch_id == "enable_custom_xinput_mapping"
            and not self._customization_allowed()
        ):
            event.switch.value = bool(self.settings.enable_custom_xinput_mapping)
            self._sync_controls()
            return
        gyro_switch = switch_id == "enable_xinput_gyro" or switch_id.startswith(
            "xinput_gyro_"
        )
        if gyro_switch and not self._gyro_control_allowed(switch_id):
            event.switch.value = bool(getattr(self.settings, switch_id))
            self._sync_controls()
            return
        super().on_switch_changed(event)
        if gyro_switch:
            self._push_gyro_mapping()
            self._sync_controls()
            return
        if switch_id == "enable_custom_xinput_mapping":
            self._sync_controls()
            if not getattr(self.app, "_refreshing", False):
                self._push_mapping()
                self._push_gyro_mapping()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "xinput-mapping-restore":
            return
        if not self._customization_allowed():
            self._sync_controls()
            return
        if reset_mapping_settings(self.settings) | reset_gyro_settings(self.settings):
            preferences.save(self.settings)
            log.info("Custom XInput mapping restored to Steam defaults")
        self.app.refresh_setting_widgets()
        self._sync_controls()
        self._push_mapping()
        self._push_gyro_mapping()

    def on_show(self) -> None:
        self._sync_controls()
        self._push_mapping()
        self._push_gyro_mapping()

    def _customization_allowed(self) -> bool:
        return custom_xinput_mapping_available(
            self.settings.preferred_forza_platform
        )

    def _gyro_control_allowed(self, attr: str) -> bool:
        if not self._customization_allowed():
            return False
        if not bool(self.settings.enable_custom_xinput_mapping):
            return False
        return attr == "enable_xinput_gyro" or bool(self.settings.enable_xinput_gyro)

    def _gyro_settings_enabled(self) -> bool:
        return bool(
            self._customization_allowed()
            and self.settings.enable_custom_xinput_mapping
            and self.settings.enable_xinput_gyro
        )

    def _sync_controls(self) -> None:
        available = self._customization_allowed()
        enabled = bool(self.settings.enable_custom_xinput_mapping)
        try:
            switch = self.query_one("#enable_custom_xinput_mapping", Switch)
            if switch.value != enabled:
                switch.value = enabled
            switch.disabled = not available
            self.query_one("#xinput-mapping-restore", Button).disabled = not available
        except Exception:
            return
        for setting, source in MAPPING_SOURCE_BY_SETTING.items():
            try:
                control = self.query_one(f"#{setting}", Select)
                control.value = normalize_mapping_target(
                    getattr(self.settings, setting),
                    source.default_target,
                )
                control.disabled = not (available and enabled)
            except Exception:
                pass
        normalize_gyro_settings(self.settings)
        gyro_enabled = bool(self.settings.enable_xinput_gyro)
        motion_enabled = available and enabled and gyro_enabled
        try:
            control = self.query_one("#enable_xinput_gyro", Switch)
            control.value = gyro_enabled
            control.disabled = not (available and enabled)
        except Exception:
            pass
        for attr in (
            "xinput_gyro_mode",
            "xinput_gyro_output_stick",
            "xinput_gyro_activation",
            "xinput_gyro_horizontal_axis",
        ):
            try:
                control = self.query_one(f"#{attr}", Select)
                control.value = str(getattr(self.settings, attr))
                control.disabled = not motion_enabled
            except Exception:
                pass
        for attr in (
            "xinput_gyro_sensitivity_dps",
            "xinput_gyro_deflection_angle",
            "xinput_gyro_deadzone_dps",
            "xinput_gyro_smoothing_ms",
        ):
            try:
                control = self.query_one(f"#{attr}", Input)
                control.value = f"{float(getattr(self.settings, attr)):g}"
                control.disabled = not motion_enabled
            except Exception:
                pass
        for attr in (
            "xinput_gyro_vertical_enabled",
            "xinput_gyro_invert_horizontal",
            "xinput_gyro_invert_vertical",
        ):
            try:
                control = self.query_one(f"#{attr}", Switch)
                control.value = bool(getattr(self.settings, attr))
                control.disabled = not motion_enabled
            except Exception:
                pass

    def _push_mapping(self) -> None:
        refresh = getattr(self.app._xinput_service, "refresh_button_mapping", None)
        if callable(refresh):
            refresh()

    def _push_gyro_mapping(self) -> None:
        refresh = getattr(self.app._xinput_service, "refresh_gyro_mapping", None)
        if callable(refresh):
            refresh()

    def _on_gyro_select(self, event: Select.Changed) -> None:
        attr = event.select.id or ""
        if getattr(self.app, "_refreshing", False) or not self._gyro_settings_enabled():
            self._sync_controls()
            return
        value = str(event.value)
        if getattr(self.settings, attr) != value:
            setattr(self.settings, attr, value)
            preferences.save(self.settings)
        self._push_gyro_mapping()
        self._sync_controls()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._commit_gyro_input(event.input, strict=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        self._commit_gyro_input(event.input, strict=False)

    def _commit_gyro_input(self, widget: Input, *, strict: bool) -> None:
        attr = widget.id or ""
        if not attr.startswith("xinput_gyro_") or not hasattr(self.settings, attr):
            return
        if getattr(self.app, "_refreshing", False) or not self._gyro_settings_enabled():
            self._sync_controls()
            return
        try:
            value = float(widget.value)
        except ValueError:
            if strict:
                widget.value = f"{float(getattr(self.settings, attr)):g}"
            return
        setattr(self.settings, attr, value)
        normalize_gyro_settings(self.settings)
        normalized = float(getattr(self.settings, attr))
        if strict or normalized == value:
            widget.value = f"{normalized:g}"
        preferences.save(self.settings)
        self._push_gyro_mapping()
