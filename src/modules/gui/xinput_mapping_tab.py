"""Standalone Xbox App button-mapping page."""

import logging

import customtkinter as ctk

from lang import t
from modules.config import preferences
from modules.xinput.mapping import (
    MAPPING_SOURCE_GROUPS,
    MAPPING_SOURCES,
    MAPPING_TARGET_BY_KEY,
    MAPPING_TARGETS,
    normalize_mapping_target,
    reset_mapping_settings,
)
from modules.xinput.service import custom_xinput_mapping_available

from . import theme as T
from . import widgets as W
from .settings_tab import SettingsTab

log = logging.getLogger("fhds")


class XInputMappingTab(SettingsTab):
    """Expose the complete digital mapping without a nested disclosure."""

    SWITCH_SECTIONS: tuple = ()
    SECTIONS: list = []
    EXPERIMENTAL_SECTIONS: tuple = ()
    SHOW_RESET = False
    SHOW_EXPERIMENTAL = False
    PAGE_TITLE = "Custom Xbox button mapping"
    PAGE_SUBTITLE = ""

    def __init__(self, parent, app):
        self._mapping_restore: ctk.CTkButton | None = None
        self._mapping_menus: dict[str, ctk.CTkOptionMenu] = {}
        self._target_by_label: dict[str, str] = {}
        super().__init__(parent, app)

    def _build(self):
        controls = W.Card(self._scroll)
        controls.pack(fill="x", pady=(0, T.PAD_MD))
        description = W.Hint(
            controls,
            t(
                "Customize the digital buttons sent by the Xbox App bridge. "
                "Sticks and L2/R2 remain unchanged."
            ),
            wrap=self.app.px(640),
        )
        description.pack(fill="x", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM))
        requirement = W.Hint(
            controls,
            t(
                "Select Xbox App as the Forza platform to customize buttons here. "
                "If you use the Steam version, change your controller mapping in Steam."
            ),
            wrap=self.app.px(640),
        )
        requirement.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        controls.bind(
            "<Configure>",
            lambda event, widgets=(description, requirement): self._resize_switch_hints(
                event.width,
                widgets,
            ),
        )

        attr = "enable_custom_xinput_mapping"
        switch = ctk.CTkSwitch(
            controls,
            text=t("Enable custom Xbox mapping"),
            command=lambda: self._on_switch(attr),
        )
        if bool(getattr(self.settings, attr)):
            switch.select()
        switch.pack(anchor="w", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        self._switches[attr] = switch

        self._mapping_restore = W.SecondaryButton(
            controls,
            t("Restore Steam defaults"),
            self._restore_defaults,
            width=190,
        )
        self._mapping_restore.pack(
            anchor="w",
            padx=T.PAD_MD,
            pady=(0, T.PAD_MD),
        )

        self._target_by_label = {
            t(target.label): target.key for target in MAPPING_TARGETS
        }
        target_labels = list(self._target_by_label)
        for group, sources in MAPPING_SOURCE_GROUPS:
            card = W.Card(self._scroll)
            card.pack(fill="x", pady=(0, T.PAD_MD))
            W.H2(card, t(group)).pack(
                anchor="w",
                padx=T.PAD_MD,
                pady=(T.PAD_MD, T.PAD_SM),
            )
            for source in sources:
                row = W.FieldRow(card, t(source.label))
                row.pack(fill="x", padx=T.PAD_MD, pady=T.PAD_XS)
                target = normalize_mapping_target(
                    getattr(self.settings, source.setting),
                    source.default_target,
                )
                menu = ctk.CTkOptionMenu(
                    row.controls,
                    values=target_labels,
                    width=240,
                    command=lambda value, item=source: self._on_mapping_changed(
                        item,
                        value,
                    ),
                )
                menu.set(t(MAPPING_TARGET_BY_KEY[target].label))
                menu.pack(side="right")
                self._mapping_menus[source.setting] = menu
            ctk.CTkFrame(card, fg_color="transparent", height=T.PAD_SM).pack()

        self._refresh_mapping_controls()

    def _on_switch(self, attr: str):
        if attr == "enable_custom_xinput_mapping" and not self._customization_allowed():
            self._refresh_mapping_controls()
            return
        super()._on_switch(attr)
        if attr == "enable_custom_xinput_mapping":
            self._refresh_mapping_controls()
            self._push_mapping()

    def _on_mapping_changed(self, source, selected_label: str):
        if self.app._refreshing or not self._customization_allowed():
            self._refresh_mapping_controls()
            return
        target = self._target_by_label.get(selected_label)
        if target is None:
            return
        if getattr(self.settings, source.setting) != target:
            setattr(self.settings, source.setting, target)
            preferences.save(self.settings)
            log.info("%s = %s", source.setting, target)
        self._push_mapping()

    def _restore_defaults(self):
        if not self._customization_allowed():
            self._refresh_mapping_controls()
            return
        if reset_mapping_settings(self.settings):
            preferences.save(self.settings)
            log.info("Custom XInput mapping restored to Steam defaults")
        self._refresh_mapping_controls()
        self._push_mapping()

    def _customization_allowed(self) -> bool:
        return custom_xinput_mapping_available(
            getattr(self.settings, "preferred_forza_platform", "")
        )

    def _push_mapping(self):
        service = getattr(self.app, "_xinput_service", None)
        refresh = getattr(service, "refresh_button_mapping", None)
        if callable(refresh):
            refresh()

    def _refresh_mapping_controls(self):
        available = self._customization_allowed()
        enabled = bool(getattr(self.settings, "enable_custom_xinput_mapping", False))
        switch = self._switches.get("enable_custom_xinput_mapping")
        if switch is not None:
            if bool(switch.get()) != enabled:
                if enabled:
                    switch.select()
                else:
                    switch.deselect()
            switch.configure(state="normal" if available else "disabled")
        if self._mapping_restore is not None:
            self._mapping_restore.configure(
                state="normal" if available else "disabled"
            )
        state = "normal" if available and enabled else "disabled"
        for source in MAPPING_SOURCES:
            menu = self._mapping_menus.get(source.setting)
            if menu is None:
                continue
            target = normalize_mapping_target(
                getattr(self.settings, source.setting, source.default_target),
                source.default_target,
            )
            label = t(MAPPING_TARGET_BY_KEY[target].label)
            if menu.get() != label:
                menu.set(label)
            menu.configure(state=state)

    def _refresh_widgets(self):
        super()._refresh_widgets()
        self._refresh_mapping_controls()

    def on_show(self):
        super().on_show()
        self._refresh_mapping_controls()
        self._push_mapping()
