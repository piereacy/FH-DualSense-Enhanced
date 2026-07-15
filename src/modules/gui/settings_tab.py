"""Settings tab: switches, sliders, entries with live save.

Each top-level section becomes a Card. Inside, rows use FieldRow for
label-control alignment.
"""
import logging
import threading

import customtkinter as ctk

from lang import t
from modules.about import ATTRIBUTION, SOURCE_URL, SPONSOR_URL
from modules.config import preferences

from . import theme as T
from . import widgets as W

log = logging.getLogger("fhds")

# Mirrors src/modules/tui/settings_tab.py exactly.
SETTING_SECTIONS = [
    ("Pedal dead zones", [
        ("accel_deadzone", "Gas trigger dead zone", 0, 255, ""),
        ("brake_deadzone", "Brake trigger dead zone", 0, 255, ""),
    ]),
    ("Left trigger - Brake force", [
        ("brake_baseline_force", "Resting stiffness", 0, 255, ""),
        ("brake_max_force", "Hard-press stiffness", 0, 255, ""),
        ("brake_curve", "Stiffness curve shape", 0.1, 20.0, ""),
        ("handbrake_bonus", "Handbrake extra stiffness", 0, 255, ""),
    ]),
    ("Left trigger - Static wall (optional)", [
        ("brake_static_wall_at", "Wall position on the trigger", 0, 255, ""),
        ("brake_static_wall_force", "Wall hardness", 0, 255, ""),
    ]),
    ("Right trigger - Gas force", [
        ("throttle_baseline_force", "Resting stiffness", 0, 255, ""),
        ("throttle_max_force", "Hard-press stiffness", 0, 255, ""),
        ("throttle_curve", "Stiffness curve shape", 0.1, 20.0, ""),
    ]),
    ("ABS (anti-lock brake) rumble", [
        ("abs_amp", "Rumble strength", 0, 255, ""),
        ("abs_sensitivity", "Sensitivity", 0.1, 3.0, ""),
    ]),
    ("R2 trigger redline vibration", [
        ("rev_limit_ratio", "Trigger near redline at", 0.0, 1.0, ""),
        ("rev_limit_freq", "Trigger vibration frequency (Hz)", 1, 255, ""),
        ("rev_limit_amp", "Trigger vibration strength", 0, 255, ""),
        ("rev_limit_hold_ms", "Trigger hold time (ms)", 0.0, 1000.0, ""),
    ]),
    ("Grip redline vibration", [
        ("grip_redline_ratio", "Grip trigger near redline at", 0.0, 1.0, ""),
        ("grip_redline_freq", "Grip pulse rate (Hz)", 1, 20, ""),
        ("grip_redline_amp", "Grip pulse strength", 0, 255, ""),
    ]),
    ("Traction/grip feedback", [
        ("wheelspin_amp", "Grip feedback strength", 0, 255, ""),
        ("wheelspin_sensitivity", "Sensitivity", 0.1, 3.0, ""),
    ]),
    ("Idle buzz", [
        ("idle_amp_high", "Idle strength", 0, 255, ""),
    ]),
    ("Gear shift thump", [
        ("gear_shift_freq", "Thump speed (Hz)", 0, 255, ""),
        ("gear_shift_amp", "Thump strength", 0, 255, ""),
        ("gear_shift_duration_ms", "Thump length (ms)", 0.0, 2000.0, ""),
    ]),
    ("Body haptics", [
        ("enable_body_haptics", "Enable body haptics", None, None,
         "Uses the same haptic mix over USB and Bluetooth; only the transport path differs. "
         "Disable in-game vibration only if you feel competing or doubled output."),
        ("body_haptics_intensity", "Master intensity", 0.0, 2.0, ""),
        ("engine_haptics_intensity", "Engine intensity", 0.0, 2.0, ""),
        ("road_haptics_intensity", "Road texture intensity", 0.0, 2.0, ""),
        ("impact_haptics_intensity", "Impact and suspension intensity", 0.0, 2.0, ""),
        ("slip_haptics_intensity", "Slip and ABS intensity", 0.0, 2.0, ""),
        ("slip_haptics_threshold", "Slip threshold", 0.0, 5.0, ""),
    ]),
]

EXPERIMENTAL_SECTIONS = [
    ("ABS advanced tuning", [
        ("abs_brake_threshold", "Minimum brake input", 0, 255, ""),
        ("abs_min_speed_kmh", "Minimum speed (km/h)", 0.0, 500.0, ""),
        ("abs_slip_ratio_threshold", "Longitudinal slip threshold", 0.0, 10.0, ""),
        ("abs_combined_slip_threshold", "Combined slip threshold", 0.0, 10.0, ""),
        ("abs_combined_slip_weight", "Combined slip influence", 0.0, 1.0, ""),
        ("abs_slip_full_scale", "Slip at maximum feedback", 0.1, 10.0, ""),
        ("abs_freq_min", "Minimum frequency (Hz)", 0, 255, ""),
        ("abs_freq", "Maximum frequency (Hz)", 0, 255, ""),
        ("abs_amp_min", "Minimum strength", 0, 255, ""),
        ("abs_hold_ms", "Feedback hold (ms)", 0.0, 500.0, ""),
        ("abs_wall_zones", "Top wall zones", 1, 9, ""),
    ]),
    ("Traction/grip advanced tuning", [
        ("wheelspin_slip_threshold", "Longitudinal slip threshold", 0.0, 10.0, ""),
        ("wheelspin_hysteresis", "Slip hysteresis", 0.0, 0.9, ""),
        ("wheelspin_slip_full_scale", "Slip at maximum feedback", 0.1, 10.0, ""),
        ("wheelspin_attack_ms", "Attack smoothing (ms)", 1.0, 500.0, ""),
        ("wheelspin_release_ms", "Release smoothing (ms)", 1.0, 1000.0, ""),
        ("wheelspin_g_damping", "G-force damping", 0.0, 1.0, ""),
        ("wheelspin_burnout_rotation_threshold", "Burnout rotation threshold", 0.0, 300.0, ""),
        ("wheelspin_burnout_rotation_full_scale", "Burnout rotation at maximum feedback", 1.0, 1000.0, ""),
        ("wheelspin_tarmac_freq_min", "Tarmac minimum frequency (Hz)", 0, 255, ""),
        ("wheelspin_tarmac_freq_max", "Tarmac maximum frequency (Hz)", 0, 255, ""),
        ("wheelspin_water_freq_min", "Water minimum frequency (Hz)", 0, 255, ""),
        ("wheelspin_water_freq_max", "Water maximum frequency (Hz)", 0, 255, ""),
        ("wheelspin_dirt_freq_min", "Dirt minimum frequency (Hz)", 0, 255, ""),
        ("wheelspin_dirt_freq_max", "Dirt maximum frequency (Hz)", 0, 255, ""),
        ("wheelspin_gravel_freq_min", "Gravel minimum frequency (Hz)", 0, 255, ""),
        ("wheelspin_gravel_freq_max", "Gravel maximum frequency (Hz)", 0, 255, ""),
    ]),
    ("Grip redline advanced tuning", [
        ("grip_redline_release_ratio", "Grip release below redline at", 0.0, 1.0, ""),
        ("grip_redline_low_ratio", "Low-frequency pulse ratio", 0.0, 1.0, ""),
        ("grip_redline_background_duck", "Redline background level", 0.0, 1.0, ""),
    ]),
    ("Collision haptics advanced tuning", [
        ("collision_haptics_jerk_threshold", "Collision jerk threshold", 0.0, 50.0, ""),
        ("collision_haptics_duration_ms", "Collision duration (ms)", 0.0, 1000.0, ""),
        ("collision_haptics_cooldown_ms", "Collision cooldown (ms)", 0.0, 2000.0, ""),
        ("collision_haptics_rebound_ratio", "Collision rebound strength", 0.0, 1.0, ""),
        ("collision_haptics_weak_side_ratio", "Collision weak-side strength", 0.0, 1.0, ""),
        ("collision_background_duck", "Collision background level", 0.0, 1.0, ""),
    ]),
]

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
    ("Reconnect", [
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

SETTING_RANGES = {a: (lo, hi)
                  for sections in (SETTING_SECTIONS, EXPERIMENTAL_SECTIONS, SYSTEM_SECTIONS)
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


class SettingsTab(ctk.CTkFrame):
    """Header + scrollable sectioned list. System tab subclasses this."""
    SECTIONS = SETTING_SECTIONS
    SHOW_RESET = True
    SHOW_ABOUT = True
    SHOW_EXPERIMENTAL = True
    PAGE_TITLE = "Settings"
    PAGE_SUBTITLE = "All changes save instantly."

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.settings = app.settings
        self._switches: dict[str, ctk.CTkSwitch] = {}
        self._sliders: dict[str, ctk.CTkSlider] = {}
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._reset_armed = False
        self._reset_btn: ctk.CTkButton | None = None
        self._experimental_open = False
        self._experimental_btn: ctk.CTkButton | None = None
        self._experimental_body: ctk.CTkFrame | None = None

        W.PageHeader(self, t(self.PAGE_TITLE), t(self.PAGE_SUBTITLE)
                     ).pack(fill="x", pady=(0, T.PAD_MD))
        self._scroll = W.FastScroll(self)
        self._scroll.pack(fill="both", expand=True)

        self._build()
        app.register_refresh(self._refresh_widgets)

    # MARK: build -----------------------------------------------------------

    def _build(self):
        for section, fields in self.SECTIONS:
            self._build_section_card(section, fields)
        if self.SHOW_EXPERIMENTAL:
            self._build_experimental_card()
        if self.SHOW_ABOUT:
            self._build_about_card()
        if self.SHOW_RESET:
            self._reset_btn = W.DangerButton(self._scroll, t("Reset to defaults"),
                                             command=self._on_reset)
            self._reset_btn.pack(fill="x", pady=(T.PAD_MD, T.PAD_SM))

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
        for section, fields in EXPERIMENTAL_SECTIONS:
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

    def _build_about_card(self):
        card = W.Card(self._scroll)
        card.pack(fill="x", pady=(0, T.PAD_MD))
        W.H2(card, t("About and licenses")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM)
        )
        W.Body(card, ATTRIBUTION, wraplength=self.app.px(620)).pack(
            anchor="w", fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM)
        )
        W.GhostButton(
            card,
            text=f"Source: {SOURCE_URL}",
            command=lambda: self.app._open_url(SOURCE_URL),
            anchor="w",
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        W.GhostButton(
            card,
            text=f"Sponsor: {SPONSOR_URL}",
            command=lambda: self.app._open_url(SPONSOR_URL),
            anchor="w",
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))

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
        if not self._reset_armed:
            self._reset_armed = True
            if self._reset_btn:
                self._reset_btn.configure(text=t("Click again to confirm reset"))
            return
        self._reset_armed = False
        if self._reset_btn:
            self._reset_btn.configure(text=t("Reset to defaults"))
        preferences.reset(self.settings)
        self.app.refresh_setting_widgets()
        log.info("Settings reset to defaults.")

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
