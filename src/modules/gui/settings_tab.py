"""Settings tab: switches, sliders, entries with live save.

Each top-level section becomes a Card. Inside, rows use FieldRow for
label-control alignment.
"""
import logging
import threading

import customtkinter as ctk

from lang import t
from modules.config import preferences
from modules.feedback_schema import (
    GRIP_EXPERIMENTAL_SECTIONS,
    GRIP_SETTING_SECTIONS,
    GRIP_SWITCH_SECTIONS,
    TRIGGER_EXPERIMENTAL_SECTIONS,
    TRIGGER_SETTING_SECTIONS,
)

from . import theme as T
from . import widgets as W

log = logging.getLogger("fhds")

SYSTEM_SECTIONS = [
    ("DSX", [
        ("use_dsx", "DSX integration", None, None,
         "Send triggers to DualSenseX over UDP. Takes effect immediately."),
        ("dsx_host", "Host", None, None,
         "Default 127.0.0.1. Match the host in DSX settings."),
        ("dsx_port", "Port", 1, 65535,
         "Default 6969. Match the port in DSX settings."),
    ]),
    ("Forza telemetry (applies on next launch)", [
        ("udp_port", "UDP port", 1, 65535,
         "In Forza HUD: host 127.0.0.1 (try ::1 if it fails)."),
        ("udp_forward", "Forward telemetry", None, None,
         "Mirror every received packet to another app (e.g. SimHub) without taking the port from it."),
        ("udp_forward_to", "Forward to", None, None,
         "host:port targets, comma-separated. Default 127.0.0.1:5301."),
    ]),
    ("Startup pulse", [
        ("startup_pulse_force", "Startup buzz strength", 0, 255, ""),
    ]),
    ("Connection and reconnect", [
        ("enable_reconnect", "Auto-reconnect when controller drops", None, None, ""),
        ("reconnect_interval_s", "Reconnect check interval (s)", 0.1, 60.0, ""),
    ]),
    ("Application behavior", [
        ("exit_on_game_close", "Close the app when the game closes", None, None, ""),
        ("minimize_to_tray", "Move the app to the tray when minimized", None, None, ""),
    ]),
    ("Game detection", [
        ("game_poll_interval_s", "Game-watch check interval (s)", 0.1, 60.0, ""),
    ]),
]

# Feedback classification is shared with the Console frontend.  The legacy
# constants above remain aliases during the R7 worktree migration; renderers
# and range validation must use the shared schema below.
SETTING_SECTIONS = GRIP_SETTING_SECTIONS
EXPERIMENTAL_SECTIONS = GRIP_EXPERIMENTAL_SECTIONS

SETTING_RANGES = {a: (lo, hi)
                  for sections in (
                      TRIGGER_SETTING_SECTIONS,
                      GRIP_SETTING_SECTIONS,
                      TRIGGER_EXPERIMENTAL_SECTIONS,
                      GRIP_EXPERIMENTAL_SECTIONS,
                      SYSTEM_SECTIONS,
                  )
                  for _, fields in sections
                  for a, _lbl, lo, hi, *_rest in fields
                  if lo is not None and hi is not None}


def _format_value(v) -> str:
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def responsive_column_count(width: int, threshold: int = 720) -> int:
    return 2 if width >= threshold else 1


class SettingsTab(ctk.CTkFrame):
    """Header + scrollable sectioned list. System tab subclasses this."""
    RESIZE_DEBOUNCE_MS = 80
    SWITCH_SECTIONS: tuple = GRIP_SWITCH_SECTIONS
    SECTIONS: list = SETTING_SECTIONS
    EXPERIMENTAL_SECTIONS: tuple = GRIP_EXPERIMENTAL_SECTIONS
    SHOW_RESET = True
    SHOW_EXPERIMENTAL = True
    PAGE_TITLE = "Grip haptics"
    PAGE_SUBTITLE = "Grip switches and tuning. Changes save instantly."

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.settings = app.settings
        self._switches: dict[str, ctk.CTkSwitch] = {}
        self._sliders: dict[str, ctk.CTkSlider] = {}
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._reset_btn: ctk.CTkButton | None = None
        self._experimental_open = False
        self._experimental_btn: ctk.CTkButton | None = None
        self._experimental_body: ctk.CTkFrame | None = None
        self._switch_grid: ctk.CTkFrame | None = None
        self._switch_cards: list[ctk.CTkFrame] = []
        self._switch_columns = 0
        self._layout_after = None

        W.PageHeader(self, t(self.PAGE_TITLE), t(self.PAGE_SUBTITLE)
                     ).pack(fill="x", pady=(0, T.PAD_MD))
        self._scroll = W.FastScroll(self)
        self._scroll.pack(fill="both", expand=True)

        self._build()
        app.register_refresh(self._refresh_widgets)

    # MARK: build -----------------------------------------------------------

    def _build(self):
        if self.SWITCH_SECTIONS:
            self._build_switch_grid()
        for section, fields in self.SECTIONS:
            self._build_section_card(section, fields)
        if self.SHOW_EXPERIMENTAL:
            self._build_experimental_card()
        if self.SHOW_RESET:
            self._reset_btn = W.DangerButton(self._scroll, t("Reset to defaults"),
                                             command=self._on_reset)
            self._reset_btn.pack(fill="x", pady=(T.PAD_MD, T.PAD_SM))

    def _build_switch_grid(self):
        self._switch_grid = ctk.CTkFrame(self._scroll, fg_color="transparent")
        self._switch_grid.pack(fill="x", expand=True)
        self._switch_grid.bind("<Configure>", self._schedule_layout)
        for title, fields in self.SWITCH_SECTIONS:
            card = W.Card(self._switch_grid)
            self._switch_cards.append(card)
            W.H2(card, t(title)).pack(
                anchor="w",
                padx=T.PAD_MD,
                pady=(T.PAD_MD, T.PAD_SM),
            )
            for attr, label, _lo, _hi, *rest in fields:
                hint = rest[0] if rest else ""
                self._add_quick_switch(card, attr, label, hint)
            ctk.CTkFrame(card, fg_color="transparent", height=T.PAD_SM).pack()
        self._schedule_layout()

    def _add_quick_switch(self, parent, attr: str, label: str, hint: str):
        switch = ctk.CTkSwitch(
            parent,
            text=t(label),
            command=lambda a=attr: self._on_quick_switch(a),
        )
        if bool(getattr(self.settings, attr)):
            switch.select()
        switch.pack(anchor="w", padx=T.PAD_MD, pady=T.PAD_XS)
        self._switches[attr] = switch
        if hint:
            W.Hint(parent, t(hint), wrap=self.app.px(520)).pack(
                anchor="w",
                padx=T.PAD_MD,
                pady=(0, T.PAD_SM),
            )

    def _schedule_layout(self, _event=None):
        if self._switch_grid is None:
            return
        if not bool(getattr(self._scroll, "_layout_active", True)):
            return
        if self._layout_after is not None:
            try:
                self.after_cancel(self._layout_after)
            except Exception:
                pass
        self._layout_after = self.after(
            self.RESIZE_DEBOUNCE_MS,
            self._apply_responsive_layout,
        )

    def _apply_responsive_layout(self):
        self._layout_after = None
        if self._switch_grid is None:
            return
        if not bool(getattr(self._scroll, "_layout_active", True)):
            return
        width = max(self._switch_grid.winfo_width(), self.winfo_width())
        columns = responsive_column_count(width, self.app.px(720))
        if columns == self._switch_columns:
            return
        self._switch_columns = columns
        self._switch_grid.grid_columnconfigure(0, weight=1, uniform="feedback")
        self._switch_grid.grid_columnconfigure(
            1,
            weight=1 if columns == 2 else 0,
            uniform="feedback" if columns == 2 else "",
        )
        for index, card in enumerate(self._switch_cards):
            row, column = divmod(index, columns)
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=(0, T.PAD_MD // 2)
                if columns == 2 and column == 0
                else ((T.PAD_MD // 2, 0) if columns == 2 else (0, 0)),
                pady=(0, T.PAD_MD),
            )

    def on_show(self):
        self._schedule_layout()

    def on_hide(self):
        if self._layout_after is None:
            return
        try:
            self.after_cancel(self._layout_after)
        except Exception:
            pass
        self._layout_after = None

    def _build_experimental_card(self):
        card = W.Card(self._scroll)
        card.pack(fill="x", pady=(0, T.PAD_MD))
        self._experimental_btn = W.GhostButton(
            card,
            text=f"▶ {t('Experimental features')}",
            command=self._toggle_experimental,
            anchor="w",
        )
        self._experimental_btn.pack(fill="x", padx=T.PAD_SM, pady=(T.PAD_SM, 0))
        W.Hint(card, t("Not recommended for manual adjustment.")).pack(
            anchor="w", padx=T.PAD_MD, pady=(0, T.PAD_SM)
        )
        self._experimental_body = ctk.CTkFrame(card, fg_color="transparent")
        for section, fields in self.EXPERIMENTAL_SECTIONS:
            self._build_section_card(section, fields, parent=self._experimental_body)

    def _toggle_experimental(self):
        if self._experimental_body is None or self._experimental_btn is None:
            return
        self._experimental_open = not self._experimental_open
        marker = "▼" if self._experimental_open else "▶"
        self._experimental_btn.configure(text=f"{marker} {t('Experimental features')}")
        if self._experimental_open:
            self._experimental_body.pack(fill="x", padx=T.PAD_SM, pady=(0, T.PAD_SM))
        else:
            self._experimental_body.pack_forget()

    def _build_section_card(self, section_title: str, fields: list, parent=None):
        card = W.Card(parent or self._scroll)
        card.pack(fill="x", pady=(0, T.PAD_MD))
        W.H2(card, t(section_title)).pack(anchor="w",
                                          padx=T.PAD_MD,
                                          pady=(T.PAD_MD, T.PAD_SM))
        for entry in fields:
            attr, label, lo, hi, *rest = entry
            hint = rest[0] if rest else ""
            value = getattr(self.settings, attr, None)
            if value is None:
                continue
            if isinstance(value, bool):
                self._add_switch_row(card, attr, label, hint)
            elif isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
                if attr in ("udp_port", "dsx_port"):
                    self._add_entry_only_row(card, attr, label, value, hint)
                else:
                    self._add_slider_row(card, attr, label, value, lo, hi, hint)
            else:
                self._add_entry_only_row(card, attr, label, value, hint)
        ctk.CTkFrame(card, fg_color="transparent", height=T.PAD_SM).pack()

    # MARK: row helpers -----------------------------------------------------

    def _add_switch_row(self, parent, attr: str, label: str, hint: str):
        # The DSX toggle has a multi-line hint; wrap it so it doesn't clip.
        hint_wrap = self.app.px(500) if attr == "use_dsx" else 0
        row = W.FieldRow(parent, t(label), hint=t(hint) if hint else "", hint_wrap=hint_wrap)
        row.pack(fill="x", padx=T.PAD_MD, pady=T.PAD_XS)
        sw = ctk.CTkSwitch(row.controls, text="",
                           command=lambda a=attr: self._on_switch(a))
        if getattr(self.settings, attr):
            sw.select()
        sw.pack(side="left", anchor="w")
        self._switches[attr] = sw

    def _add_entry_only_row(self, parent, attr: str, label: str, value, hint: str):
        row = W.FieldRow(parent, t(label), hint=t(hint) if hint else "")
        row.pack(fill="x", padx=T.PAD_MD, pady=T.PAD_XS)
        entry = ctk.CTkEntry(row.controls, width=120)
        entry.insert(0, _format_value(value))
        entry.pack(side="right")
        self._bind_entry(entry, attr)
        self._entries[attr] = entry

    def _add_slider_row(self, parent, attr: str, label: str, value, lo, hi, hint: str):
        row = W.FieldRow(parent, t(label), hint=t(hint) if hint else "")
        row.pack(fill="x", padx=T.PAD_MD, pady=T.PAD_XS)
        if isinstance(value, int):
            steps = max(1, int(hi - lo))
        else:
            steps = 200
        sld = ctk.CTkSlider(row.controls, from_=float(lo), to=float(hi),
                            number_of_steps=steps,
                            command=lambda v, a=attr: self._on_slider(a, v))
        sld.set(float(value))
        sld.pack(side="left", fill="x", expand=True, padx=(0, T.PAD_SM))
        entry = ctk.CTkEntry(row.controls, width=80)
        entry.insert(0, _format_value(value))
        entry.pack(side="right")
        self._bind_entry(entry, attr)
        self._sliders[attr] = sld
        self._entries[attr] = entry

    def _bind_entry(self, entry: ctk.CTkEntry, attr: str):
        entry.bind("<KeyRelease>", lambda _e, a=attr: self._on_entry_change(a, strict=False))
        entry.bind("<Return>", lambda _e, a=attr: self._on_entry_change(a, strict=True))
        entry.bind("<FocusOut>", lambda _e, a=attr: self._on_entry_change(a, strict=True))

    # MARK: handlers --------------------------------------------------------

    def _on_switch(self, attr: str):
        if self.app._refreshing:
            return
        if not hasattr(self.settings, attr):
            return
        value = bool(self._switches[attr].get())
        if getattr(self.settings, attr) != value:
            setattr(self.settings, attr, value)
            preferences.save(self.settings)
            log.info("%s = %s", attr, value)
        self._push_live(attr, value)

    def _on_quick_switch(self, attr: str):
        self._on_switch(attr)
        self.app.haptic(bool(getattr(self.settings, attr)))

    def _on_slider(self, attr: str, raw: float):
        if self.app._refreshing:
            return
        if not hasattr(self.settings, attr):
            return
        current = getattr(self.settings, attr)
        new = int(round(raw)) if isinstance(current, int) else float(raw)
        if new != current:
            setattr(self.settings, attr, new)
            preferences.save(self.settings)
            log.info("%s = %s", attr, new)
        entry = self._entries.get(attr)
        if entry is not None:
            text = _format_value(new)
            if entry.get() != text:
                entry.delete(0, "end")
                entry.insert(0, text)
        self._push_live(attr, new)

    def _on_entry_change(self, attr: str, strict: bool):
        if self.app._refreshing:
            return
        if not hasattr(self.settings, attr):
            return
        entry = self._entries[attr]
        raw = entry.get().strip()
        if not raw:
            return
        current = getattr(self.settings, attr)
        try:
            if isinstance(current, bool):
                new = raw.lower() in ("1", "true", "yes", "on")
            elif isinstance(current, int):
                new = int(float(raw))
            elif isinstance(current, float):
                new = float(raw)
            else:
                new = raw
        except ValueError:
            if strict:
                entry.delete(0, "end")
                entry.insert(0, _format_value(current))
            return
        rng = SETTING_RANGES.get(attr)
        if rng and isinstance(new, (int, float)) and not isinstance(new, bool):
            lo, hi = rng
            clamped = max(lo, min(hi, new))
            if isinstance(current, int):
                clamped = int(clamped)
            if clamped != new:
                if strict:
                    new = clamped
                    entry.delete(0, "end")
                    entry.insert(0, _format_value(new))
                else:
                    return
        if new != current:
            setattr(self.settings, attr, new)
            preferences.save(self.settings)
            log.info("%s = %s", attr, new)
            sld = self._sliders.get(attr)
            if sld is not None and abs(float(sld.get()) - float(new)) > 1e-9:
                sld.set(float(new))
        self._push_live(attr, new)

    def _on_reset(self):
        self.app.request_factory_reset()

    def _push_live(self, attr: str, value):
        ds = getattr(self.app, "_ds", None)
        if ds is None:
            return
        # MARK: use_dsx swap - restart backend immediately on toggle
        if attr == "use_dsx":
            threading.Thread(target=self.app._restart_backend, daemon=True).start()
            return
        # DSXClient implements these as no-ops, so calling unconditionally is safe.
        if attr == "enable_reconnect":
            ds.set_reconnect_enabled(value)
        elif attr == "reconnect_interval_s":
            ds.set_reconnect_interval(value)

    # MARK: refresh ---------------------------------------------------------

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
        for attr, sld in self._sliders.items():
            if not hasattr(self.settings, attr):
                continue
            want = float(getattr(self.settings, attr))
            if abs(float(sld.get()) - want) > 1e-9:
                sld.set(want)
        for attr, entry in self._entries.items():
            if not hasattr(self.settings, attr):
                continue
            text = _format_value(getattr(self.settings, attr))
            if entry.get() != text:
                entry.delete(0, "end")
                entry.insert(0, text)
