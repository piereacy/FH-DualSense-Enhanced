"""Controls tab: trigger and shared haptic effect on/off switches."""
import logging

import customtkinter as ctk

from lang import t
from modules.config import preferences

from . import theme as T
from . import widgets as W

log = logging.getLogger("fhds")

TRIGGER_CONTROLS = [
    ("L2 - Brake", [
        ("enable_gear_shift_brake",  "Shift thump"),
        ("enable_abs",               "ABS rumble"),
        ("enable_brake_static_wall", "Static brake wall"),
        ("enable_brake_resistance",  "Brake stiffness"),
        ("enable_handbrake_bonus",   "Handbrake stiffness bonus"),
    ]),
    ("R2 - Throttle", [
        ("enable_gear_shift",          "Shift thump"),
        ("enable_idle_buzz",           "Idle buzz"),
        ("enable_rev_limiter",         "R2 trigger redline vibration"),
        ("enable_throttle_resistance", "Throttle stiffness"),
    ]),
    ("Shared feedback", [
        ("enable_wheelspin_buzz", "Traction/grip feedback"),
    ]),
    ("Grip feedback", [
        ("enable_grip_gear_shift_haptics", "Grip gear-shift thump"),
    ]),
    ("Redline feedback", [
        ("enable_grip_redline_haptics", "Grip redline vibration"),
        ("grip_redline_left",           "Left grip"),
        ("grip_redline_right",          "Right grip"),
    ]),
]


class ControlsTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.settings = app.settings
        self._switches: dict[str, ctk.CTkSwitch] = {}
        self._build()
        app.register_refresh(self._refresh_widgets)

    def _build(self):
        W.PageHeader(self, t("Controls"),
                     t("Toggle individual trigger effects. Changes save instantly.")
                     ).pack(fill="x", pady=(0, T.PAD_MD))

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        for col in range(2):
            grid.grid_columnconfigure(col, weight=1, uniform="cols")
        row_count = (len(TRIGGER_CONTROLS) + 1) // 2
        for row in range(row_count):
            grid.grid_rowconfigure(row, weight=1)

        for index, (title, toggles) in enumerate(TRIGGER_CONTROLS):
            row, col = divmod(index, 2)
            card = W.Card(grid)
            card.grid(row=row, column=col,
                      padx=(0 if col == 0 else T.PAD_MD // 2,
                            T.PAD_MD // 2 if col == 0 else 0),
                      pady=(0 if row == 0 else T.PAD_MD // 2,
                            T.PAD_MD // 2 if row == 0 else 0),
                      sticky="nsew")
            W.H2(card, t(title)).pack(anchor="w", padx=T.PAD_MD,
                                      pady=(T.PAD_MD, T.PAD_SM))
            for attr, label in toggles:
                sw = ctk.CTkSwitch(card, text=t(label),
                                   command=lambda a=attr: self._on_toggle(a))
                if getattr(self.settings, attr):
                    sw.select()
                sw.pack(anchor="w", padx=T.PAD_MD, pady=T.PAD_XS)
                self._switches[attr] = sw
            ctk.CTkFrame(card, fg_color="transparent", height=T.PAD_SM
                         ).pack()  # bottom breathing room

    def _on_toggle(self, attr: str):
        if self.app._refreshing:
            return
        sw = self._switches[attr]
        value = bool(sw.get())
        if hasattr(self.settings, attr) and getattr(self.settings, attr) != value:
            setattr(self.settings, attr, value)
            preferences.save(self.settings)
            log.info("%s = %s", attr, value)
        self.app.haptic(value)

    def _refresh_widgets(self):
        for attr, sw in self._switches.items():
            if not hasattr(self.settings, attr):
                continue
            want = bool(getattr(self.settings, attr))
            if bool(sw.get()) != want:
                if want:
                    sw.select()
                else:
                    sw.deselect()
