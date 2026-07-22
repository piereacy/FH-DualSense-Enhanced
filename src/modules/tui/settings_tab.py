"""Settings tab: plain-language labels, draggable sliders, live save."""
import logging
import threading

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Collapsible, Input, Label, Switch

from lang import t
from modules.config import preferences
from modules.feedback_schema import (
    GRIP_EXPERIMENTAL_SECTIONS,
    GRIP_SETTING_SECTIONS,
    GRIP_SWITCH_SECTIONS,
    TRIGGER_EXPERIMENTAL_SECTIONS,
    TRIGGER_SETTING_SECTIONS,
    field_names,
)
from modules.tui.widgets import RangeSlider

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

SETTING_SECTIONS = GRIP_SETTING_SECTIONS
EXPERIMENTAL_SECTIONS = GRIP_EXPERIMENTAL_SECTIONS

# MARK: clamp table, ignores boolean rows
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


class SettingsTab(VerticalScroll):
    DEFAULT_CSS = """
    SettingsTab, SystemTab { width: 1fr; height: 1fr; padding: 1 2; }
    SettingsTab Label.section, SystemTab Label.section {
        text-style: bold;
        color: $accent;
        padding: 1 0 0 1;
        border-bottom: hkey $accent 30%;
    }
    SettingsTab .row, SystemTab .row {
        height: 3;
        width: 1fr;
        align-vertical: middle;
        padding: 0 1;
    }
    SettingsTab .row Label.field, SystemTab .row Label.field {
        width: 32;
        height: 3;
        content-align: left middle;
    }
    SettingsTab .row Switch, SystemTab .row Switch { margin-right: 2; }
    SettingsTab .row Label.spacer, SystemTab .row Label.spacer {
        width: 1fr;
        height: 1;
    }
    SettingsTab .row RangeSlider, SystemTab .row RangeSlider {
        width: 1fr;
        min-width: 20;
        height: 1;
        padding: 0;
        margin: 1 1;
    }
    SettingsTab .row Input, SystemTab .row Input {
        width: 10;
        min-width: 8;
        max-width: 14;
        height: 3;
    }
    SettingsTab #set-dsx_host, SystemTab #set-dsx_host {
        width: 16;
        max-width: 16;
    }
    SettingsTab Label.hint, SystemTab Label.hint {
        width: 1fr;
        height: auto;
        color: $text-muted;
        padding: 0 1 1 3;
    }
    SettingsTab #experimental-settings { height: auto; margin: 1 0; }
    SettingsTab #experimental-settings > Contents { height: auto; }
    SettingsTab #reset-settings { width: 1fr; margin: 2 0 1 0; }
    SystemTab Label.error { width: 1fr; height: auto; color: $error; padding: 1; text-style: bold; }
    """

    SWITCH_SECTIONS: tuple = GRIP_SWITCH_SECTIONS
    SECTIONS: list = SETTING_SECTIONS
    EXPERIMENTAL_SECTIONS: tuple = GRIP_EXPERIMENTAL_SECTIONS
    SHOW_RESET = True
    SHOW_EXPERIMENTAL = True

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        # MARK: two-click reset confirmation
        self._reset_armed = False

    def _compose_sections(self, sections):
        for section, fields in sections:
            yield Label(t(section), classes="section")
            for entry in fields:
                attr, label, lo, hi, *rest = entry
                hint = rest[0] if rest else ""
                value = getattr(self.settings, attr, None)
                if value is None:
                    continue
                if isinstance(value, bool):
                    with Horizontal(classes="row"):
                        yield Switch(value=value, id=attr)
                        yield Label(t(label), classes="field")
                elif isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
                    input_type = "integer" if isinstance(value, int) else "number"
                    # MARK: integer sliders snap to 5; float sliders snap to span/200
                    step = 5.0 if isinstance(value, int) else None
                    # MARK: ports have no meaningful "tune by feel" - skip the slider
                    if attr in ("udp_port", "dsx_port"):
                        with Horizontal(classes="row"):
                            yield Label(t(label), classes="field")
                            # MARK: flex spacer keeps the input aligned with the slider column
                            yield Label("", classes="spacer")
                            yield Input(
                                value=_format_value(value),
                                id=f"set-{attr}",
                                type=input_type,
                            )
                    else:
                        with Horizontal(classes="row"):
                            yield Label(t(label), classes="field")
                            yield RangeSlider(
                                float(value),
                                float(lo),
                                float(hi),
                                step=step,
                                id=f"slider-{attr}",
                            )
                            yield Input(
                                value=_format_value(value),
                                id=f"set-{attr}",
                                type=input_type,
                            )
                else:
                    with Horizontal(classes="row"):
                        yield Label(t(label), classes="field")
                        # Flex spacer right-aligns the host box like the port box above it.
                        if attr == "dsx_host":
                            yield Label("", classes="spacer")
                        yield Input(value=_format_value(value), id=f"set-{attr}")
                if hint:
                    yield Label(t(hint), classes="hint")

    def compose(self) -> ComposeResult:
        yield from self._compose_sections(self.SWITCH_SECTIONS)
        yield from self._compose_sections(self.SECTIONS)
        if self.SHOW_EXPERIMENTAL:
            with Collapsible(
                title=t("Experimental features"),
                collapsed=True,
                id="experimental-settings",
            ):
                yield Label(
                    t("Not recommended for manual adjustment."),
                    classes="hint",
                )
                yield from self._compose_sections(self.EXPERIMENTAL_SECTIONS)
        if self.SHOW_RESET:
            yield Button(t("Reset to defaults"), id="reset-settings", variant="error")

    # ---- Switch -----------------------------------------------------------

    def on_switch_changed(self, event: Switch.Changed):
        # MARK: ignore events fired by programmatic widget refresh (profile/reset)
        if getattr(self.app, "_refreshing", False):
            return
        attr = event.switch.id
        if not attr or not hasattr(self.settings, attr):
            return
        if getattr(self.settings, attr) != event.value:
            setattr(self.settings, attr, event.value)
            preferences.save(self.settings)
            log.info("%s = %s", attr, event.value)
        # Push live every time - profile-load/reset sets widget values after
        # the settings object is already mutated, so I'd otherwise miss
        # propagating to the running DualSense instance.
        self._push_live(attr, event.value)
        if attr in field_names(self.SWITCH_SECTIONS):
            self.app.haptic(event.value)

    # ---- Slider -----------------------------------------------------------

    def on_range_slider_changed(self, event: RangeSlider.Changed) -> None:
        # MARK: drag handler; ignore programmatic refresh
        if getattr(self.app, "_refreshing", False):
            return
        sid = event.slider.id or ""
        if not sid.startswith("slider-"):
            return
        attr = sid[len("slider-"):]
        if not hasattr(self.settings, attr):
            return
        current = getattr(self.settings, attr)
        new = int(round(event.value)) if isinstance(current, int) else float(event.value)
        if new != current:
            setattr(self.settings, attr, new)
            preferences.save(self.settings)
            log.info("%s = %s", attr, new)
        try:
            inp = self.query_one(f"#set-{attr}", Input)
            text = _format_value(new)
            if inp.value != text:
                inp.value = text
        except Exception:
            pass
        self._push_live(attr, new)

    # ---- Input ------------------------------------------------------------

    def on_input_submitted(self, event: Input.Submitted):
        self._commit(event.input, strict=True)

    def on_input_changed(self, event: Input.Changed):
        # Live-save on every keystroke that parses cleanly; partial input is ignored.
        if getattr(self.app, "_refreshing", False):
            return
        self._commit(event.input, strict=False)

    def _commit(self, widget: Input, strict: bool) -> None:
        if not widget.id or not widget.id.startswith("set-"):
            return
        attr = widget.id[4:]
        if not hasattr(self.settings, attr):
            return
        current = getattr(self.settings, attr)
        raw = widget.value.strip()
        if not raw:
            return
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
                widget.value = _format_value(current)
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
                    widget.value = _format_value(new)
                else:
                    return
        if new != current:
            setattr(self.settings, attr, new)
            preferences.save(self.settings)
            log.info("%s = %s", attr, new)
            # MARK: keep sibling slider in sync when user types a value
            try:
                sld = self.query_one(f"#slider-{attr}", RangeSlider)
                target = float(new)
                if abs(sld.value - target) > 1e-9:
                    sld.value = target
            except Exception:
                pass
        # Always push live (see on_switch_changed for the profile-load reason).
        self._push_live(attr, new)

    # ---- Reset (two-click confirm) ---------------------------------------

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "reset-settings":
            return
        if not self._reset_armed:
            self._reset_armed = True
            event.button.label = t("Click again to confirm reset")
            return
        self._reset_armed = False
        event.button.label = t("Reset to defaults")
        if not preferences.reset(self.settings):
            log.warning("Could not restore factory defaults.")
            self.app.notify(
                t("Could not restore defaults. Check the log and try again."),
                severity="error",
            )
            return
        if hasattr(self.app, "mark_default_saved"):
            self.app.mark_default_saved()
        self.app.refresh_setting_widgets()
        log.info("Settings reset to defaults.")

    # ---- Live propagation -------------------------------------------------

    def _push_live(self, attr: str, value) -> None:
        """Push settings that DualSense captures at construction to the running
        instance so the toggle takes effect without restarting the backend."""
        ds = getattr(self.app, "_ds", None)
        if ds is None:
            return
        # MARK: use_dsx swap - restart backend immediately so the user doesn't
        # have to manually quit and relaunch after toggling DSX on/off.
        if attr == "use_dsx":
            threading.Thread(target=self.app._restart_backend, daemon=True).start()
            return
        # DSXClient implements these as no-ops, so calling unconditionally is safe.
        if attr == "enable_reconnect":
            ds.set_reconnect_enabled(value)
        elif attr == "reconnect_interval_s":
            ds.set_reconnect_interval(value)
