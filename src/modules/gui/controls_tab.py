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
        ("enable_collision_trigger_l2", "Collision trigger jolt"),
        ("enable_trigger_surface_l2", "Idle road texture"),
    ]),
    ("R2 - Throttle", [
        ("enable_gear_shift",          "Shift thump"),
        ("enable_idle_buzz",           "Idle buzz"),
        ("enable_rev_limiter",         "R2 trigger redline vibration"),
        ("enable_throttle_resistance", "Throttle stiffness"),
        ("enable_boost_resistance",    "Turbo boost resistance"),
        ("enable_gforce_resistance",   "G-force resistance"),
        ("enable_collision_trigger_r2", "Collision trigger jolt"),
        ("enable_trigger_surface_r2",  "Idle road texture"),
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


def responsive_column_count(width: int, threshold: int = 720) -> int:
    return 2 if width >= threshold else 1


class ControlsTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.settings = app.settings
        self._switches: dict[str, ctk.CTkSwitch] = {}
        self._cards: list[ctk.CTkFrame] = []
        self._columns = 0
        self._layout_after = None
        self._build()
        app.register_refresh(self._refresh_widgets)

    def _build(self):
        W.PageHeader(self, t("Driving feedback"),
                     t("Toggle individual trigger effects. Changes save instantly.")
                     ).pack(fill="x", pady=(0, T.PAD_MD))

        self._scroll = W.FastScroll(self)
        self._scroll.pack(fill="both", expand=True)
        self._grid = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._grid.pack(fill="x", expand=True)
        self._grid.bind("<Configure>", self._schedule_layout)

        for title, toggles in TRIGGER_CONTROLS:
            card = W.Card(self._grid)
            self._cards.append(card)
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
        self.after_idle(self._apply_responsive_layout)

    def _schedule_layout(self, _event=None):
        if self._layout_after is not None:
            self.after_cancel(self._layout_after)
        self._layout_after = self.after_idle(self._apply_responsive_layout)

    def _apply_responsive_layout(self):
        self._layout_after = None
        width = max(self._grid.winfo_width(), self.winfo_width())
        columns = responsive_column_count(width, self.app.px(720))
        if columns == self._columns:
            return
        self._columns = columns
        self._grid.grid_columnconfigure(0, weight=1, uniform="controls")
        self._grid.grid_columnconfigure(1, weight=1 if columns == 2 else 0,
                                        uniform="controls" if columns == 2 else "")
        for index, card in enumerate(self._cards):
            card.grid_forget()
            row, col = divmod(index, columns)
            card.grid(
                row=row, column=col, sticky="nsew",
                padx=(0, T.PAD_MD // 2) if columns == 2 and col == 0
                else ((T.PAD_MD // 2, 0) if columns == 2 else (0, 0)),
                pady=(0, T.PAD_MD),
            )

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
