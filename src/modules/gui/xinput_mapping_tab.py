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
from modules.xinput.gyro import (
    GYRO_ACTIVATION_OPTIONS,
    GYRO_HORIZONTAL_OPTIONS,
    GYRO_MODE_OPTIONS,
    GYRO_OUTPUT_OPTIONS,
    normalize_gyro_settings,
    reset_gyro_settings,
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
        self._gyro_menus: dict[str, ctk.CTkOptionMenu] = {}
        self._gyro_value_by_label: dict[str, dict[str, str]] = {}
        self._gyro_sliders: dict[str, ctk.CTkSlider] = {}
        self._gyro_entries: dict[str, ctk.CTkEntry] = {}
        self._gyro_switches: dict[str, ctk.CTkSwitch] = {}
        super().__init__(parent, app)

    def _build(self):
        controls = W.Card(self._scroll)
        controls.pack(fill="x", pady=(0, T.PAD_MD))
        description = W.Hint(
            controls,
            t(
                "Customize the buttons and Steam Input-style motion sent by the "
                "Xbox App bridge. L2/R2 remain unchanged."
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

        self._build_gyro_card()

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

    def _build_gyro_card(self):
        card = W.Card(self._scroll)
        card.pack(fill="x", pady=(0, T.PAD_MD))
        W.H2(card, t("Gyro behavior")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM)
        )
        W.Hint(
            card,
            t(
                "Virtual Xbox 360 controllers have no motion channel, so FHDS "
                "converts DualSense motion into additive joystick output."
            ),
            wrap=self.app.px(640),
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        gyro_switch = ctk.CTkSwitch(
            card,
            text=t("Enable gyro"),
            command=lambda: self._on_gyro_switch("enable_xinput_gyro"),
        )
        if bool(getattr(self.settings, "enable_xinput_gyro", False)):
            gyro_switch.select()
        gyro_switch.pack(anchor="w", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        self._gyro_switches["enable_xinput_gyro"] = gyro_switch
        W.Hint(
            card,
            t(
                "Enable custom Xbox mapping first; gyro is controlled by that "
                "master switch."
            ),
            wrap=self.app.px(640),
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        select_rows = (
            ("xinput_gyro_mode", "Gyro mode", GYRO_MODE_OPTIONS),
            ("xinput_gyro_output_stick", "Output joystick", GYRO_OUTPUT_OPTIONS),
            ("xinput_gyro_activation", "Gyro activation", GYRO_ACTIVATION_OPTIONS),
            ("xinput_gyro_horizontal_axis", "Horizontal motion axis", GYRO_HORIZONTAL_OPTIONS),
        )
        for attr, label, options in select_rows:
            row = W.FieldRow(card, t(label))
            row.pack(fill="x", padx=T.PAD_MD, pady=T.PAD_XS)
            values = {t(option.label): str(option.key) for option in options}
            menu = ctk.CTkOptionMenu(
                row.controls,
                values=list(values),
                width=280,
                command=lambda selected, field=attr: self._on_gyro_select(field, selected),
            )
            reverse = {value: label_text for label_text, value in values.items()}
            menu.set(reverse.get(str(getattr(self.settings, attr)), next(iter(values))))
            menu.pack(side="right")
            self._gyro_value_by_label[attr] = values
            self._gyro_menus[attr] = menu

        numeric_rows = (
            ("xinput_gyro_sensitivity_dps", "Full-stick camera speed (deg/s)", 30.0, 720.0),
            ("xinput_gyro_deflection_angle", "Full-stick deflection angle (deg)", 5.0, 90.0),
            ("xinput_gyro_deadzone_dps", "Gyro deadzone (deg/s)", 0.0, 30.0),
            ("xinput_gyro_smoothing_ms", "Gyro smoothing (ms)", 0.0, 200.0),
        )
        for attr, label, minimum, maximum in numeric_rows:
            row = W.FieldRow(card, t(label))
            row.pack(fill="x", padx=T.PAD_MD, pady=T.PAD_XS)
            slider = ctk.CTkSlider(
                row.controls,
                from_=minimum,
                to=maximum,
                number_of_steps=round(maximum - minimum),
                command=lambda value, field=attr: self._on_gyro_slider(field, value),
            )
            slider.set(float(getattr(self.settings, attr)))
            slider.pack(side="left", fill="x", expand=True, padx=(0, T.PAD_SM))
            entry = ctk.CTkEntry(row.controls, width=80)
            entry.insert(0, f"{float(getattr(self.settings, attr)):g}")
            entry.bind("<Return>", lambda _event, field=attr: self._on_gyro_entry(field))
            entry.bind("<FocusOut>", lambda _event, field=attr: self._on_gyro_entry(field))
            entry.pack(side="right")
            self._gyro_sliders[attr] = slider
            self._gyro_entries[attr] = entry

        for attr, label in (
            ("xinput_gyro_vertical_enabled", "Enable vertical gyro output"),
            ("xinput_gyro_invert_horizontal", "Invert horizontal gyro"),
            ("xinput_gyro_invert_vertical", "Invert vertical gyro"),
        ):
            switch = ctk.CTkSwitch(
                card,
                text=t(label),
                command=lambda field=attr: self._on_gyro_switch(field),
            )
            if bool(getattr(self.settings, attr)):
                switch.select()
            switch.pack(anchor="w", padx=T.PAD_MD, pady=T.PAD_XS)
            self._gyro_switches[attr] = switch
        ctk.CTkFrame(card, fg_color="transparent", height=T.PAD_SM).pack()

    def _on_gyro_select(self, attr: str, selected_label: str):
        if self.app._refreshing or not self._gyro_settings_enabled():
            self._refresh_mapping_controls()
            return
        value = self._gyro_value_by_label[attr].get(selected_label)
        if value is not None and getattr(self.settings, attr) != value:
            setattr(self.settings, attr, value)
            preferences.save(self.settings)
        self._push_gyro_mapping()
        self._refresh_mapping_controls()

    def _on_gyro_slider(self, attr: str, raw: float):
        if self.app._refreshing or not self._gyro_settings_enabled():
            return
        value = float(raw)
        if getattr(self.settings, attr) != value:
            setattr(self.settings, attr, value)
            preferences.save(self.settings)
        entry = self._gyro_entries[attr]
        entry.delete(0, "end")
        entry.insert(0, f"{value:g}")
        self._push_gyro_mapping()

    def _on_gyro_entry(self, attr: str):
        if self.app._refreshing or not self._gyro_settings_enabled():
            self._refresh_mapping_controls()
            return
        entry = self._gyro_entries[attr]
        try:
            value = float(entry.get())
        except ValueError:
            value = float(getattr(self.settings, attr))
        setattr(self.settings, attr, value)
        normalize_gyro_settings(self.settings)
        value = float(getattr(self.settings, attr))
        entry.delete(0, "end")
        entry.insert(0, f"{value:g}")
        self._gyro_sliders[attr].set(value)
        preferences.save(self.settings)
        self._push_gyro_mapping()

    def _on_gyro_switch(self, attr: str):
        if self.app._refreshing or not self._gyro_control_allowed(attr):
            self._refresh_mapping_controls()
            return
        setattr(self.settings, attr, bool(self._gyro_switches[attr].get()))
        preferences.save(self.settings)
        self._push_gyro_mapping()
        self._refresh_mapping_controls()

    def _on_switch(self, attr: str):
        if attr == "enable_custom_xinput_mapping" and not self._customization_allowed():
            self._refresh_mapping_controls()
            return
        super()._on_switch(attr)
        if attr == "enable_custom_xinput_mapping":
            self._refresh_mapping_controls()
            self._push_mapping()
            self._push_gyro_mapping()

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
        if reset_mapping_settings(self.settings) | reset_gyro_settings(self.settings):
            preferences.save(self.settings)
            log.info("Custom XInput mapping restored to Steam defaults")
        self._refresh_mapping_controls()
        self._push_mapping()
        self._push_gyro_mapping()

    def _customization_allowed(self) -> bool:
        return custom_xinput_mapping_available(
            getattr(self.settings, "preferred_forza_platform", "")
        )

    def _gyro_control_allowed(self, attr: str) -> bool:
        if not self._customization_allowed():
            return False
        if not bool(getattr(self.settings, "enable_custom_xinput_mapping", False)):
            return False
        return attr == "enable_xinput_gyro" or self._gyro_settings_enabled()

    def _gyro_settings_enabled(self) -> bool:
        return bool(
            self._customization_allowed()
            and getattr(self.settings, "enable_custom_xinput_mapping", False)
            and getattr(self.settings, "enable_xinput_gyro", False)
        )

    def _push_mapping(self):
        service = getattr(self.app, "_xinput_service", None)
        refresh = getattr(service, "refresh_button_mapping", None)
        if callable(refresh):
            refresh()

    def _push_gyro_mapping(self):
        service = getattr(self.app, "_xinput_service", None)
        refresh = getattr(service, "refresh_gyro_mapping", None)
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
        normalize_gyro_settings(self.settings)
        gyro_enabled = bool(getattr(self.settings, "enable_xinput_gyro", False))
        motion_enabled = available and enabled and gyro_enabled
        for attr, menu in self._gyro_menus.items():
            values = self._gyro_value_by_label[attr]
            current = str(getattr(self.settings, attr))
            label = next((key for key, value in values.items() if value == current), next(iter(values)))
            if menu.get() != label:
                menu.set(label)
            menu.configure(state="normal" if motion_enabled else "disabled")
        for attr, slider in self._gyro_sliders.items():
            slider.set(float(getattr(self.settings, attr)))
            slider.configure(state="normal" if motion_enabled else "disabled")
            entry = self._gyro_entries[attr]
            entry.configure(state="normal" if motion_enabled else "disabled")
        for attr, switch in self._gyro_switches.items():
            want = bool(getattr(self.settings, attr))
            if want:
                switch.select()
            else:
                switch.deselect()
            switch.configure(
                state=(
                    "normal"
                    if available
                    and enabled
                    and (attr == "enable_xinput_gyro" or gyro_enabled)
                    else "disabled"
                )
            )

    def _refresh_widgets(self):
        super()._refresh_widgets()
        self._refresh_mapping_controls()

    def on_show(self):
        super().on_show()
        self._refresh_mapping_controls()
        self._push_mapping()
        self._push_gyro_mapping()
