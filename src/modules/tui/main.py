"""Textual TUI app: wires tabs together and owns the backend (DualSense + UDP loop)."""
import logging
import threading
import webbrowser

from rich.markup import escape
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Header, Input, Select, Static, Switch, TabbedContent, TabPane

from lang import set_language, t
from modules.about import APP_NAME
from modules import loop, forzahorizon, make_backend
from modules.config import preferences, profiles
from modules.config.profile_session import ProfileSession
from modules.dualsense.presentation import controller_pill_status
from modules.config.preferences import _release_version
from modules.diagnostics import DiagnosticsCollector
from modules.haptics import HAPTICS_LAB_SCENES, HapticsLab, UsbAudioHaptics, UsbAudioLifecycle
from modules.haptics.trigger_pulse import TriggerPulse
from modules.runtime_logging import install_runtime_file_handler
from modules.update import UpdateService
from modules.update.install import cleanup_previous_update, self_update_supported
from modules.xinput.service import XInputBridgeService

from .about_tab import AboutTab
from .controls_tab import ControlsTab
from .dialogs import UnsavedProfileScreen
from .fh6_utilities_tab import FH6UtilitiesTab
from .lang_tab import LangTab
from .logs_tab import DEFAULT_LOG_LEVEL, LogsTab
from .lighting_tab import LightingTab
from .profiles_tab import ProfilesTab
from .settings_tab import SettingsTab
from .system_tab import SystemTab
from .widgets import RangeSlider
from .xinput_mapping_tab import XInputMappingTab

log = logging.getLogger("fhds")


class RuntimeLog(Message):
    def __init__(self, text: str):
        super().__init__()
        self.text = text


class BackendStopped(Message):
    def __init__(self, generation: int):
        super().__init__()
        self.generation = generation


class _LogHandler(logging.Handler):
    def __init__(self, app: "TriggerTUI"):
        super().__init__()
        self.app = app

    def emit(self, record):
        # Drop records once the UI has begun shutting down.
        if getattr(self.app, "_tearing_down", False):
            return
        msg = self.format(record)
        if threading.get_ident() == self.app._thread_id:
            self.app.write_log(msg)
        else:
            self.app.post_message(RuntimeLog(msg))


class TriggerTUI(App):
    CSS = """
    Screen { background: $surface; }

    #topbar { dock: top; height: 1; background: $boost; }
    #profile { width: auto; height: 1; padding: 0 2; color: $accent; text-style: bold; }
    #status { width: 1fr; height: 1; padding: 0 2; text-align: center; }
    #version { width: auto; height: 1; padding: 0 2; text-align: right; color: $text-muted; }
    #version:hover { color: $accent; text-style: underline; }

    TabbedContent { height: 1fr; }
    Tabs { align-horizontal: center; }
    TabPane { padding: 0; }
    #tab-logs { padding: 0; align-horizontal: left; }

    #bottombar { dock: bottom; height: 1; background: $boost; padding: 0; }
    #bb-spacer { width: 1fr; height: 1; background: transparent; }
    .bb-btn {
        height: 1; min-height: 1; width: auto; min-width: 0;
        padding: 0 2; margin: 0;
        border: none; background: transparent; color: $text-muted;
    }
    .bb-btn:hover { background: $accent 30%; color: $text; }
    #bb-changelog { color: $accent; text-style: bold; }
    #bb-changelog:hover { background: $accent 30%; color: $text; }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (80, "-normal"), (120, "-wide")]

    def __init__(self, settings, *, on_ready=None):
        super().__init__()
        self.settings = settings
        self._on_ready = on_ready
        set_language(settings.language)
        self._stop = threading.Event()
        self._thread = None
        self._backend_generation = 0
        self._backend_restart_lock = threading.Lock()
        self._ds = None
        self._listener_cm = None
        self._listener = None
        self._backend_error = ""
        self._udp_error = ""
        self._status_timer = None
        self._tearing_down = False
        self._close_prompt_open = False
        self._pending_before_exit = None
        self._usb_audio = UsbAudioHaptics()
        self._usb_audio_lifecycle = UsbAudioLifecycle(self._usb_audio)
        self._usb_audio_gate_active = False
        self._usb_audio_sync_requested = threading.Event()
        self._update_service = UpdateService(
            settings,
            supported=self_update_supported(),
        )
        self._xinput_service = XInputBridgeService(settings)
        self._haptics_lab = HapticsLab()
        self._trigger_pulse = TriggerPulse()
        self._diagnostics = DiagnosticsCollector(
            settings,
            controller_provider=lambda: self._ds,
            listener_provider=lambda: self._listener,
            xinput_service=self._xinput_service,
            usb_audio=self._usb_audio,
            haptics_lab=self._haptics_lab,
            error_provider=lambda: {
                "controller": self._backend_error,
                "udp": self._udp_error,
            },
            runtime_mode="tui",
        )
        self._profile_session = ProfileSession(settings)
        cleanup_previous_update()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="topbar"):
            yield Static("", id="profile")
            yield Static("", id="status")
            yield Static(_release_version() or "?", id="version")
        with TabbedContent(initial="tab-controls"):
            with TabPane(t("Trigger feedback"), id="tab-controls"):
                yield ControlsTab(self.settings)
            with TabPane(t("Profiles"), id="tab-profiles"):
                yield ProfilesTab(self.settings)
            with TabPane(t("Grip haptics"), id="tab-settings"):
                yield SettingsTab(self.settings)
            with TabPane(t("Controller lighting"), id="tab-lighting"):
                yield LightingTab(self.settings)
            with TabPane(t("Custom Xbox button mapping"), id="tab-xinput-mapping"):
                yield XInputMappingTab(self.settings)
            with TabPane(t("System and updates"), id="tab-system"):
                yield SystemTab(self.settings)
            with TabPane(t("FH6 utilities"), id="tab-fh6-utilities"):
                yield FH6UtilitiesTab(self.settings)
            with TabPane(t("Language"), id="tab-lang"):
                yield LangTab(self.settings)
            with TabPane(t("Logs"), id="tab-logs"):
                yield LogsTab()
            with TabPane(t("About and licenses"), id="tab-about"):
                yield AboutTab()
        with Horizontal(id="bottombar"):
            yield Button(f"q  {t('Quit')}", id="bb-quit", classes="bb-btn")
            yield Static(id="bb-spacer")

    def on_app_blur(self, _event: events.AppBlur) -> None:
        if (
            not self._haptics_lab.snapshot().active
            and not self._xinput_service.preview_requested
        ):
            return
        self._haptics_lab.stop("app_blurred")
        self._xinput_service.request_preview_runtime(False)
        self._request_usb_audio_eligibility_sync()

    # --- lifecycle ----------------------------------------------------------

    def on_mount(self):
        self.title = APP_NAME
        self.sub_title = f"UDP {self.settings.udp_host}:{self.settings.udp_port}"

        root = logging.getLogger()
        root.handlers.clear()
        install_runtime_file_handler()
        handler = _LogHandler(self)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
        root.addHandler(handler)
        root.setLevel(getattr(logging, DEFAULT_LOG_LEVEL))

        self.refresh_status()
        self.refresh_profile()
        # MARK: keep handle so on_unmount can stop the poller before backend teardown
        self._status_timer = self.set_interval(1.0, self.refresh_status)
        self._update_service.start_background()
        log.info("Starting controller and telemetry listener...")
        self.call_after_refresh(self._start_backend)

    def on_unmount(self):
        # Detach our log handler before tearing down: backend shutdown emits
        # log records, and routing those into the unmounted widgets raises.
        self._tearing_down = True
        if self._status_timer is not None:
            self._status_timer.stop()
            self._status_timer = None
        root = logging.getLogger()
        for h in list(root.handlers):
            if isinstance(h, _LogHandler):
                root.removeHandler(h)
        self._update_service.stop()
        with self._backend_restart_lock:
            self._haptics_lab.stop("shutdown")
            self._stop.set()
            if self._thread:
                self._thread.join(timeout=2.0)
            self._xinput_service.stop()
            self._usb_audio_lifecycle.close()
            if self._listener_cm:
                self._listener_cm.__exit__(None, None, None)
            if self._ds:
                self._ds.close()

    def _start_backend(self):
        self._backend_generation += 1
        s = self.settings
        try:
            # main already loaded preferences and applied CLI overrides. Profile
            # actions update this same settings object before deferred startup.
            self._ds = make_backend(
                s,
                s.enable_startup_pulse and s.enable_trigger_feedback,
            )
            self._xinput_service.prepare_controller_access(self._ds)
            self._ds.open()
            self._xinput_service.sync(self._ds)
            self._backend_error = ""
        except Exception as exc:
            self._backend_error = str(exc) or type(exc).__name__
            log.exception("Backend startup failed")
            self.query_one("#status", Static).update(
                t("Backend failed: {error}").format(error=escape(str(exc)))
            )
            return
        try:
            self._listener_cm = forzahorizon.UDPListener(
                s.udp_host, s.udp_port, s.udp_timeout, s.udp_forward_to, s.udp_forward)
            self._listener = self._listener_cm.__enter__()
            self._udp_error = ""
            log.info("Listening on %s:%d", s.udp_host, s.udp_port)
            log.info("In game: HUD & Gameplay -> Data Out: ON, IP %s, Port %d", s.udp_host, s.udp_port)
            if s.use_dsx:
                log.info("DSX mode: sending triggers to %s:%d", s.dsx_host, s.dsx_port)
            self._thread = threading.Thread(
                target=self._run_loop, args=(self._backend_generation,), daemon=True,
            )
            self._thread.start()
        except OSError as exc:
            self._udp_error = str(exc) or type(exc).__name__
            # MARK: friendly UDP bind error - usually port in use
            log.exception("UDP bind failed on %s:%d", s.udp_host, s.udp_port)
            msg = t("UDP port {port} is in use. Close the other listener or change the port in the System tab.").format(port=s.udp_port)
            self.query_one("#status", Static).update(msg)
            try:
                self._notify_ready()
            except Exception:
                self._backend_error = "Update startup health confirmation failed"
                log.exception(self._backend_error)
                self.exit(return_code=1)
        except Exception as exc:
            self._udp_error = str(exc) or type(exc).__name__
            log.exception("Telemetry listener startup failed")
            self.query_one("#status", Static).update(
                t("Backend failed: {error}").format(error=escape(str(exc)))
            )
        else:
            try:
                self._notify_ready()
            except Exception:
                self._backend_error = "Update startup health confirmation failed"
                log.exception(self._backend_error)
                self.exit(return_code=1)

    def _notify_ready(self) -> None:
        """Confirm update health once the TUI backend can receive telemetry."""
        callback, self._on_ready = self._on_ready, None
        if callback is not None:
            callback()

    def _run_loop(self, generation: int):
        try:
            loop.run(
                self._ds,
                self._listener,
                self.settings,
                stop_event=self._stop,
                usb_audio=self._usb_audio,
                haptics_lab=getattr(self, "_haptics_lab", None),
                trigger_pulse=getattr(self, "_trigger_pulse", None),
                diagnostics=getattr(self, "_diagnostics", None),
            )
        except Exception:
            # An unexpected error here would otherwise kill the backend thread
            log.exception("Telemetry loop crashed")
        finally:
            if not self._stop.is_set():
                self.post_message(BackendStopped(generation))

    def on_runtime_log(self, message: RuntimeLog) -> None:
        if not self._tearing_down:
            self.write_log(message.text)

    def on_backend_stopped(self, message: BackendStopped) -> None:
        if (
            message.generation == self._backend_generation
            and not self._tearing_down
            and not self._stop.is_set()
        ):
            self.request_close()

    def _restart_backend(self, *, restart_listener: bool = False):
        """Swap the backend, optionally reopening the listener after a reset.
        Called when use_dsx is toggled live so the change takes effect immediately."""
        with self._backend_restart_lock:
            if self._tearing_down:
                return
            # Invalidate queued exits before clearing the reused stop event.
            self._backend_generation += 1
            # MARK: stop old loop + backend, then reuse the listener
            self._haptics_lab.stop("backend_restart")
            self._stop.set()
            old_thread = self._thread
            if old_thread:
                old_thread.join(timeout=2.0)
            if old_thread is not None and old_thread.is_alive():
                error = RuntimeError("telemetry loop did not stop within 2 seconds")
                self._backend_error = str(error)
                log.error("Backend restart aborted: %s", error)
                return
            self._thread = None
            self._xinput_service.stop()
            s = self.settings
            try:
                if self._ds and self._ds.close() is False:
                    raise RuntimeError("controller I/O worker has not stopped")
                if restart_listener:
                    if self._listener_cm is not None:
                        self._listener_cm.__exit__(None, None, None)
                    self._listener_cm = None
                    self._listener = None
                self._stop.clear()
                # MARK: suppress pulse on hot-swap - avoid confusing the user mid-session
                self._ds = make_backend(s, False)
                self._xinput_service.prepare_controller_access(self._ds)
                self._ds.open()
                self._xinput_service.sync(self._ds)
                self._backend_error = ""
                if s.use_dsx:
                    log.info("DSX mode: sending triggers to %s:%d", s.dsx_host, s.dsx_port)
                else:
                    log.info("HID mode: writing direct to DualSense")
                if restart_listener:
                    self._listener_cm = forzahorizon.UDPListener(
                        s.udp_host, s.udp_port, s.udp_timeout,
                        s.udp_forward_to, s.udp_forward,
                    )
                    self._listener = self._listener_cm.__enter__()
                    self._udp_error = ""
                if self._listener is not None:
                    self._thread = threading.Thread(
                        target=self._run_loop, args=(self._backend_generation,), daemon=True,
                    )
                    self._thread.start()
            except Exception as exc:
                self._backend_error = str(exc) or type(exc).__name__
                log.exception("Backend restart failed")


    @staticmethod
    def _open_url(url: str) -> None:
        # webbrowser.open() can block while a browser cold-starts
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

    # --- topbar / logs bridge -----------------------------------------------

    def refresh_status(self):
        request = getattr(self, "_usb_audio_sync_requested", None)
        if request is not None:
            request.clear()
        self._sync_usb_audio_eligibility_safely()
        if self._backend_error:
            self.query_one("#status", Static).update(
                f"[bold red]{t('Controller backend error')}[/]"
            )
            return

        connected = bool(self._ds and self._ds.connected)
        if self.settings.use_dsx:
            state = (f"[bold dodgerblue]{t('DSX: active')}[/]" if connected
                     else f"[bold red]{t('DSX: off')}[/]")
        elif self._ds and callable(getattr(self._ds, "snapshot", None)):
            snapshot = self._ds.snapshot()
            presentation = controller_pill_status(snapshot, t)
            if snapshot.connected:
                state = f"[bold green]{presentation.state}[/]"
                if presentation.detail:
                    detail_color = "red" if presentation.low_battery else "green"
                    state += f" · [bold {detail_color}]{presentation.detail}[/]"
            elif snapshot.phase.value in {
                "available",
                "connecting",
                "switching",
                "reconnecting",
            }:
                state = f"[bold yellow]{presentation.state}[/]"
            else:
                state = f"[bold red]{presentation.state}[/]"
        else:
            state = (f"[bold green]{t('connected')}[/]" if connected
                     else f"[bold red]{t('waiting')}[/]")
        self.query_one("#status", Static).update(f"DualSense: {state}")

    def _request_usb_audio_eligibility_sync(self) -> None:
        request = getattr(self, "_usb_audio_sync_requested", None)
        if request is None:
            return
        request.set()
        try:
            self.call_later(self._drain_requested_usb_audio_sync)
        except RuntimeError:
            pass

    def _drain_requested_usb_audio_sync(self) -> None:
        request = getattr(self, "_usb_audio_sync_requested", None)
        if request is None or not request.is_set():
            return
        request.clear()
        self._sync_usb_audio_eligibility_safely()

    def _sync_usb_audio_eligibility_safely(self) -> None:
        try:
            self._sync_usb_audio_eligibility()
        except Exception:
            log.exception("USB audio eligibility sync failed")

    def _sync_usb_audio_eligibility(self):
        controller = self._ds if self._listener is not None else None
        lab_snapshot = self._haptics_lab.snapshot()
        body_scene_keys = {
            scene.key for scene in HAPTICS_LAB_SCENES if scene.body_haptics
        }
        lab_body_active = (
            lab_snapshot.active and lab_snapshot.scene in body_scene_keys
        )
        self._usb_audio_lifecycle.sync(
            controller,
            self.settings,
            runtime_active=True,
            force_body_haptics=lab_body_active,
        )

    def export_diagnostics(self):
        return self._diagnostics.export()

    def refresh_profile(self):
        """Update the active profile label. Cheap path is called only on profile
        mutations / app mount — avoids hitting disk on the per-second timer."""
        try:
            active = profiles.load_profiles(self.settings).get("active") or t("(none)")
        except Exception:
            active = t("(none)")
        self.query_one("#profile", Static).update(
            t("Profile: {name}").format(name=escape(str(active)))
        )

    def report_save_failure(self) -> None:
        message = t(preferences.save_failure_message(self.settings))
        self.notify(message, severity="error")

    def mark_default_saved(self) -> None:
        self._profile_session.accept_current_default(self.settings)

    def request_close(self, before_exit=None) -> None:
        """Route every graceful TUI exit through the named-profile prompt."""
        if self._tearing_down or self._close_prompt_open:
            return
        if self._profile_session.needs_named_save(self.settings):
            self._close_prompt_open = True
            self._pending_before_exit = before_exit

            def _save(name: str) -> bool:
                final = profiles.save_profile(name, self.settings)
                if not final:
                    return False
                self._profile_session.accept_current_default(self.settings)
                self.refresh_profile()
                return True

            self.push_screen(
                UnsavedProfileScreen(
                    suggested_name=profiles.next_profile_name(),
                    on_save=_save,
                ),
                self._finish_close_prompt,
            )
            return
        self._finish_close(before_exit)

    def _finish_close_prompt(self, result: str | None) -> None:
        before_exit = self._pending_before_exit
        self._pending_before_exit = None
        self._close_prompt_open = False
        if result == "exit":
            self._finish_close(before_exit)

    def _finish_close(self, before_exit=None) -> None:
        if not preferences.save_pending(self.settings):
            self.report_save_failure()
            return
        if before_exit is not None:
            try:
                before_exit()
            except Exception as exc:
                log.warning("Pre-exit action failed: %s", exc)
                self.notify(
                    t("Could not start update: {error}").format(error=exc),
                    severity="error",
                )
                return
        self.exit()

    def _logs_tab(self) -> LogsTab | None:
        try:
            return self.query_one(LogsTab)
        except Exception:
            return None

    def write_log(self, msg: str) -> None:
        tab = self._logs_tab()
        if tab:
            tab.write(msg)

    # --- shared helpers used by tabs ----------------------------------------

    def refresh_setting_widgets(self) -> None:
        """Called by tabs after profile load / settings reset."""
        # MARK: guard programmatic Switch/Input writes so tab handlers skip save churn
        self._refreshing = True
        try:
            for sw in self.query(Switch):
                if sw.id and hasattr(self.settings, sw.id):
                    sw.value = getattr(self.settings, sw.id)
            for inp in self.query(Input):
                if inp.id and inp.id.startswith("set-"):
                    attr = inp.id[4:]
                    if hasattr(self.settings, attr):
                        inp.value = str(getattr(self.settings, attr))
            for sld in self.query(RangeSlider):
                if sld.id and sld.id.startswith("slider-"):
                    attr = sld.id[len("slider-"):]
                    if hasattr(self.settings, attr):
                        sld.value = float(getattr(self.settings, attr))
            for select in self.query(Select):
                if select.id and hasattr(self.settings, select.id):
                    select.value = getattr(self.settings, select.id)
            refresh_mapping = getattr(
                self._xinput_service,
                "refresh_button_mapping",
                None,
            )
            if callable(refresh_mapping):
                refresh_mapping()
        finally:
            self._refreshing = False

    def haptic(self, on: bool) -> None:
        controller = self._ds
        if self.settings.enable_trigger_feedback and controller and controller.connected:
            self._trigger_pulse.request(on)

    # --- bottombar / bindings -----------------------------------------------

    async def action_quit(self) -> None:
        self.request_close()

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "bb-quit":
            self.request_close()
