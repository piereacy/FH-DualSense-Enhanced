"""Standalone Xbox App button-mapping page."""

import logging

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Label, Select, Switch

from lang import t
from modules.config import preferences
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
    XInputMappingTab #xinput-mapping-restore { width: 1fr; margin: 1; }
    """

    def compose(self) -> ComposeResult:
        yield Label(
            t(
                "Customize the digital buttons sent by the Xbox App bridge. "
                "Sticks and L2/R2 remain unchanged."
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
        if (
            event.switch.id == "enable_custom_xinput_mapping"
            and not self._customization_allowed()
        ):
            event.switch.value = bool(self.settings.enable_custom_xinput_mapping)
            self._sync_controls()
            return
        super().on_switch_changed(event)
        if event.switch.id == "enable_custom_xinput_mapping":
            self._sync_controls()
            if not getattr(self.app, "_refreshing", False):
                self._push_mapping()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "xinput-mapping-restore":
            return
        if not self._customization_allowed():
            self._sync_controls()
            return
        if reset_mapping_settings(self.settings):
            preferences.save(self.settings)
            log.info("Custom XInput mapping restored to Steam defaults")
        self.app.refresh_setting_widgets()
        self._sync_controls()
        self._push_mapping()

    def on_show(self) -> None:
        self._sync_controls()
        self._push_mapping()

    def _customization_allowed(self) -> bool:
        return custom_xinput_mapping_available(
            self.settings.preferred_forza_platform
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

    def _push_mapping(self) -> None:
        refresh = getattr(self.app._xinput_service, "refresh_button_mapping", None)
        if callable(refresh):
            refresh()
