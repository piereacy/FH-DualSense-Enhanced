"""Textual TUI: animation toggles on the left, live logs on the right.

Toggles mutate the live Settings instance the loop reads each frame, so changes
take effect immediately without a restart. Tunable values (forces, curves,
deadzones, etc.) still live in settings.py.
"""
import logging
import threading
import time

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Label, RichLog, Switch

from modules import dualsense, loop, preferences, udplistener
from modules.dualsense.triggers import off, vibration
from modules.update_check import log_latest_commit_age

# Haptic feedback played on the controller when a switch is toggled.
HAPTIC_FREQ_HZ = 40
HAPTIC_AMP_ON = 200    # firmer pulse when enabling
HAPTIC_AMP_OFF = 120   # softer pulse when disabling
HAPTIC_DURATION_S = 0.10

log = logging.getLogger("fh5ds")

# (settings attribute, display label)
TOGGLES = [
    ("enable_brake_resistance",     "Brake resistance"),
    ("enable_handbrake_bonus",      "Handbrake bonus"),
    ("enable_abs",                  "ABS pulse"),
    ("enable_throttle_resistance",  "Throttle resistance"),
    ("enable_rev_limiter",          "Rev limiter"),
    ("enable_gear_shift",           "Gear shift thump"),
]


# MARK: Log handler — routes log records into the TUI RichLog widget
class _LogToWidget(logging.Handler):
    def __init__(self, app: "TriggerTUI"):
        super().__init__()
        self._app = app

    def emit(self, record):
        try:
            self._app.call_from_thread(self._app.write_log, self.format(record))
        except Exception:
            pass


class TriggerTUI(App):
    CSS = """
    Horizontal { height: 1fr; }
    #left { width: 38; padding: 1 2; border: round $accent; }
    #right { width: 1fr; border: round $accent; }
    .row { height: 3; }
    Switch { margin-right: 2; }
    Label.title { text-style: bold; padding-bottom: 1; }
    Label.note { color: $text-muted; padding-top: 1; text-style: italic; }
    """
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._stop = threading.Event()
        self._thread = None
        self._ds = None
        self._listener_cm = None
        self._listener = None
        self._started = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="left"):
                yield Label("Animations", classes="title")
                for attr, label in TOGGLES:
                    with Horizontal(classes="row"):
                        yield Switch(value=getattr(self.settings, attr), id=attr)
                        yield Label(label)
                yield Label("Unofficial fan project.", classes="note")
            yield RichLog(id="right", highlight=False, markup=False, wrap=True, max_lines=2000)
        yield Footer()

    # MARK: Mount — wire logging, open hardware, start loop
    def on_mount(self):
        self.title = "FH5 DualSense"
        self.sub_title = f"UDP {self.settings.udp_host}:{self.settings.udp_port}"

        # Replace all handlers with our TUI widget handler.
        root = logging.getLogger()
        root.handlers.clear()
        handler = _LogToWidget(self)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
        root.addHandler(handler)
        root.setLevel(logging.INFO)

        log_latest_commit_age()
        log.info("Starting controller and telemetry listener...")

        # Let Textual paint the UI before HID startup runs. This avoids a blank
        # alternate screen if controller/socket startup is slow or fails.
        self.call_after_refresh(self._start_backend)

        # Focus the log pane so PageUp/PageDown/scroll work without a click.
        self.set_focus(self.query_one(RichLog))

    def _start_backend(self):
        if self._started:
            return
        self._started = True
        # Open hardware + listener and start the loop in a background thread.
        try:
            s = self.settings
            self._ds = dualsense.DualSense(
                startup_pulse_force=s.startup_pulse_force,
                enable_startup_pulse=s.enable_startup_pulse,
            )
            self._ds.open()
            self._listener_cm = udplistener.UDPListener(s.udp_host, s.udp_port, s.udp_timeout)
            self._listener = self._listener_cm.__enter__()
            log.info("Listening on %s:%d", s.udp_host, s.udp_port)
            log.info("In FH5: HUD & Gameplay -> Data Out: ON, IP 127.0.0.1, Port %d", s.udp_port)

            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
        except Exception as exc:
            log.exception("TUI startup failed")
            self.exit(
                return_code=1,
                message=f"TUI startup failed: {exc}\nTry running with --no-tui to use console logs.",
            )

    def _run_loop(self) -> None:
        try:
            loop.run(self._ds, self._listener, self.settings, stop_event=self._stop)
        finally:
            # If the loop exited on its own (e.g. ProcessWatcher saw the game
            # close), bring the TUI down too instead of leaving an empty window.
            if not self._stop.is_set():
                self.call_from_thread(self.exit)

    def on_unmount(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._listener_cm:
            self._listener_cm.__exit__(None, None, None)
        if self._ds:
            self._ds.close()

    def write_log(self, msg: str) -> None:
        self.query_one(RichLog).write(msg)

    # MARK: Toggle switch — mutate settings + haptic feedback
    def on_switch_changed(self, event: Switch.Changed) -> None:
        attr = event.switch.id
        if attr and hasattr(self.settings, attr):
            setattr(self.settings, attr, event.value)
            preferences.save(self.settings)
            log.info("%s = %s", attr, event.value)
            self._haptic_pulse(event.value)

    def _haptic_pulse(self, on: bool) -> None:
        if not self._ds:
            return
        threading.Thread(target=self._do_haptic, args=(on,), daemon=True).start()

    def _do_haptic(self, on: bool) -> None:
        amp = HAPTIC_AMP_ON if on else HAPTIC_AMP_OFF
        v = vibration(HAPTIC_FREQ_HZ, amp)
        self._ds.set(v, v)
        time.sleep(HAPTIC_DURATION_S)
        self._ds.set(off(), off())
