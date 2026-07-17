"""CustomTkinter GUI app.

Layout:
  +-----------------------------------------------------------+
  |  header  [* status]  [Profile: name]            v1.2.3   |
  +---------+-------------------------------------------------+
  | sidebar |  main content (active tab frame)                |
  |  nav    |                                                 |
  | items   |                                                 |
  |         |                                                 |
  | footer  |                                                 |
  | links   |                                                 |
  +---------+-------------------------------------------------+

Threading: backend runs in a worker thread; logs are queued and drained on
the Tk main thread via root.after. Tk widgets are never touched off-thread.
"""
import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser

import customtkinter as ctk

from lang import set_language, t
from modules import forzahorizon, loop, make_backend
from modules.about import APP_NAME
from modules.config import preferences, profiles
from modules.config.profile_session import ProfileSession
from modules.config.preferences import _release_version
from modules.dualsense.adaptive_trigger import off, vibrate
from modules.haptics import UsbAudioHaptics, UsbAudioLifecycle
from modules.update import UpdateService
from modules.update.install import cleanup_previous_update, self_update_supported

from . import theme as T
from . import widgets as W
from .about_tab import AboutTab
from .controls_tab import ControlsTab
from .dialogs import FactoryResetDialog, UnsavedProfileDialog
from .lang_tab import LangTab
from .logs_tab import DEFAULT_LOG_LEVEL, LogsTab
from .lighting_tab import LightingTab
from .overview_tab import OverviewTab
from .profiles_tab import ProfilesTab
from .settings_tab import SettingsTab
from .system_tab import SystemTab
from .tray import TrayController

log = logging.getLogger("fhds")

HAPTIC_FREQ_HZ = 40
HAPTIC_AMP_ON = 200
HAPTIC_AMP_OFF = 120
HAPTIC_DURATION_S = 0.10

NAV_ITEMS = (
    "Overview", "Driving", "Haptics", "Lighting", "Profiles",
    "System", "Language", "Logs", "About",
)
NAV_LABELS = {
    "Overview": "Overview",
    "Driving": "Driving feedback",
    "Haptics": "Grip haptics",
    "Lighting": "Controller lighting",
    "Profiles": "Profiles",
    "System": "System and updates",
    "Language": "Language",
    "Logs": "Logs",
    "About": "About and licenses",
}
class _QueueLogHandler(logging.Handler):
    """Worker threads push records here; the Tk loop drains them."""

    def __init__(self, q: queue.Queue):
        super().__init__()
        self._q = q

    def emit(self, record):
        try:
            self._q.put_nowait((record.levelname, self.format(record)))
        except queue.Full:
            pass


class TriggerGUI:
    def __init__(self, settings):
        self.settings = settings
        set_language(settings.language)

        # Runtime state
        self._stop = threading.Event()
        self._thread = None
        self._ds = None
        self._listener_cm = None
        self._listener = None
        self._backend_error = ""
        self._udp_error = ""
        self._tearing_down = False
        self._close_dialog = None
        self._reset_dialog = None
        self._refreshing = False
        self._refresh_callbacks: list = []
        self._log_queue: queue.Queue = queue.Queue(maxsize=4000)
        self._usb_audio = UsbAudioHaptics()
        self._usb_audio_lifecycle = UsbAudioLifecycle(self._usb_audio)
        self._update_service = UpdateService(
            settings,
            supported=self_update_supported(),
        )
        self._profile_session = ProfileSession(settings)
        cleanup_previous_update()

        # Theme + DPI
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self._apply_theme()
        # Make Windows treat us as Per-Monitor v2 BEFORE Tk is created so
        # CTk's auto-DPI reads the right monitor DPI.
        self._enable_process_dpi_awareness()
        self.scale = 1.0

        # Window
        self.root = ctk.CTk()
        self._wheel_router = W.install_wheel_router(self.root)
        self.root.title(APP_NAME)
        self._set_window_icon()
        self._center_window()
        self._tray = TrayController(
            self.root,
            on_show=self._show_window,
            on_quit=lambda: self.request_close("tray"),
        )
        self.root.protocol("WM_DELETE_WINDOW", lambda: self.request_close("window"))
        self.root.bind("<Unmap>", self._on_unmap)

        # Layout
        self._build_header()
        self._build_body()

        # Final wiring
        self._install_log_handler()
        self._refresh_status()
        self._refresh_profile()

    # MARK: theme / dpi -----------------------------------------------------

    @staticmethod
    def _apply_theme():
        from customtkinter import ThemeManager
        th = ThemeManager.theme
        th["CTk"]["fg_color"] = list(T.BG_MAIN)
        th["CTkToplevel"]["fg_color"] = list(T.BG_MAIN)
        th["CTkFrame"]["fg_color"] = list(T.BG_PANEL)
        th["CTkFrame"]["top_fg_color"] = list(T.BG_HOVER)
        th["CTkFrame"]["border_color"] = list(T.BORDER)
        th["CTkButton"]["fg_color"] = [T.ACCENT, T.ACCENT]
        th["CTkButton"]["hover_color"] = [T.ACCENT_HOVER, T.ACCENT_HOVER]
        th["CTkSwitch"]["progress_color"] = [T.ACCENT, T.ACCENT]
        th["CTkSlider"]["progress_color"] = [T.ACCENT, T.ACCENT]
        th["CTkSlider"]["button_color"] = [T.ACCENT, T.ACCENT]
        th["CTkSlider"]["button_hover_color"] = [T.ACCENT_HOVER, T.ACCENT_HOVER]
        th["CTkSegmentedButton"]["selected_color"] = [T.ACCENT, T.ACCENT]
        th["CTkSegmentedButton"]["selected_hover_color"] = [T.ACCENT_HOVER, T.ACCENT_HOVER]
        th["CTkProgressBar"]["progress_color"] = [T.ACCENT, T.ACCENT]
        th["CTkCheckBox"]["fg_color"] = [T.ACCENT, T.ACCENT]
        th["CTkCheckBox"]["hover_color"] = [T.ACCENT_HOVER, T.ACCENT_HOVER]
        th["CTkRadioButton"]["fg_color"] = [T.ACCENT, T.ACCENT]
        th["CTkRadioButton"]["hover_color"] = [T.ACCENT_HOVER, T.ACCENT_HOVER]
        th["CTkEntry"]["border_color"] = list(T.BORDER)
        th["CTkEntry"]["fg_color"] = list(T.BG_INPUT)
        th["CTkOptionMenu"]["fg_color"] = [T.ACCENT, T.ACCENT]
        th["CTkOptionMenu"]["button_color"] = [T.ACCENT_HOVER, T.ACCENT_HOVER]
        th["CTkOptionMenu"]["button_hover_color"] = [T.ACCENT_HOVER, T.ACCENT_HOVER]

    @staticmethod
    def _enable_process_dpi_awareness():
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
        except Exception:
            pass

    def px(self, n: int) -> int:
        return max(1, int(round(n * self.scale)))

    def font_size(self, base: int) -> int:
        return max(8, int(round(base * self.scale)))

    def toast(self, message: str, ms: int = 2500):
        """Show a transient banner at the top of the window. Cross-platform."""
        top = ctk.CTkToplevel(self.root)
        top.overrideredirect(True)
        try:
            top.attributes("-topmost", True)
            top.attributes("-alpha", 0.95)
        except tk.TclError:
            pass
        lbl = ctk.CTkLabel(
            top, text=message,
            fg_color=T.ACCENT, text_color="white",
            corner_radius=8,
            font=ctk.CTkFont(size=T.FS_BODY, weight="bold"),
        )
        lbl.pack(ipadx=18, ipady=10)
        top.update_idletasks()
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        rw = self.root.winfo_width()
        tw = top.winfo_width()
        top.geometry(f"+{rx + (rw - tw) // 2}+{ry + 24}")
        top.after(ms, top.destroy)

    def _set_window_icon(self):
        from modules.config import paths
        ico = paths.ICON_ICO
        png = paths.ICON_PNG
        # iconphoto with a large PNG gives Windows a high-DPI source it can
        # downscale crisply for the taskbar; iconbitmap alone tends to pick
        # the 32x32 entry of the .ico for the taskbar (Tk limitation).
        if png.exists():
            try:
                self._icon_img = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, self._icon_img)
            except Exception:
                pass
        if sys.platform.startswith("win") and ico.exists():
            try:
                self.root.iconbitmap(default=str(ico))
            except Exception:
                pass

    def _center_window(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        # CTk scales width/height in geometry strings by the monitor DPI, but
        # leaves +x+y position unscaled. So: w,h in logical units, x,y in
        # physical pixels.
        try:
            from customtkinter import ScalingTracker
            dpi = float(ScalingTracker.get_window_dpi_scaling(self.root)) or 1.0
        except Exception:
            dpi = 1.0
        sw_u = sw / dpi
        sh_u = sh / dpi
        base_w, base_h = 1040, 700
        w_u = int(min(base_w, sw_u * 0.85))
        h_u = int(min(base_h, sh_u * 0.85))
        w_phys = int(w_u * dpi)
        h_phys = int(h_u * dpi)
        x = max(0, (sw - w_phys) // 2)
        y = max(0, (sh - h_phys) // 2 - int(sh * 0.04))
        self.root.geometry(f"{w_u}x{h_u}+{x}+{y}")
        self.root.minsize(640, 440)

    # MARK: layout ----------------------------------------------------------

    def _build_header(self):
        bar = ctk.CTkFrame(self.root, height=T.HEADER_H, corner_radius=0,
                           fg_color=T.BG_PANEL)
        bar.pack(side="top", fill="x")
        bar.grid_columnconfigure(0, weight=1, uniform="hdr")
        bar.grid_columnconfigure(1, weight=0)
        bar.grid_columnconfigure(2, weight=1, uniform="hdr")
        bar.grid_propagate(False)

        self.profile_pill = W.Pill(bar, label="-", prefix=t("Profile"))
        self.profile_pill.grid(row=0, column=0, padx=(T.PAD_MD, T.PAD_SM),
                               pady=T.PAD_SM, sticky="w")

        self.status_pill = W.Pill(bar, label=t("waiting"),
                                  prefix="DualSense", dot_color=T.RED)
        self.status_pill.grid(row=0, column=1, padx=T.PAD_SM, pady=T.PAD_SM)

        self.lbl_version = ctk.CTkLabel(
            bar, text=_release_version() or "?",
            text_color=T.TEXT_FAINT, cursor="hand2",
            font=ctk.CTkFont(size=T.FS_TINY),
        )
        self.lbl_version.grid(row=0, column=2, padx=(T.PAD_SM, T.PAD_MD),
                              pady=T.PAD_SM, sticky="e")

        ctk.CTkFrame(self.root, height=1, corner_radius=0,
                     fg_color=T.BORDER).pack(side="top", fill="x")

    def _build_body(self):
        body = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        body.pack(side="top", fill="both", expand=True)

        nav_host = ctk.CTkFrame(
            body, width=T.SIDEBAR_W, corner_radius=0, fg_color=T.BG_DEEP,
        )
        nav_host.pack(side="left", fill="y")
        nav_host.pack_propagate(False)
        nav_box = ctk.CTkFrame(nav_host, fg_color="transparent")
        nav_box.pack(side="top", fill="x", pady=(T.PAD_MD, 0))

        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._nav_badges: dict[str, ctk.CTkLabel] = {}
        for key in NAV_ITEMS:
            label = t(NAV_LABELS[key])
            holder = ctk.CTkFrame(nav_box, fg_color="transparent")
            holder.pack(side="top", fill="x", padx=T.PAD_XS, pady=2)
            btn = ctk.CTkButton(
                holder, text=f"  {T.ICON[key]}   {label}", anchor="w", width=0,
                height=36, corner_radius=6,
                fg_color="transparent", hover_color=T.BG_HOVER,
                text_color=T.TEXT_MUTED,
                font=ctk.CTkFont(size=T.FS_BODY),
                command=lambda k=key: self._select_nav(k),
            )
            btn.pack(fill="x")
            self._nav_buttons[key] = btn
            if key == "System":
                badge = ctk.CTkLabel(
                    holder, text="●", width=12, height=12,
                    text_color="white", font=ctk.CTkFont(size=8), cursor="hand2",
                )
                badge.bind("<Button-1>", lambda _event: self._select_nav("System"))
                badge.place_forget()
                self._nav_badges[key] = badge

        self._content = ctk.CTkFrame(body, corner_radius=0, fg_color=T.BG_MAIN)
        self._content.pack(side="left", fill="both", expand=True)

        self.overview_tab = OverviewTab(self._content, self)
        self.controls_tab = ControlsTab(self._content, self)
        self.profiles_tab = ProfilesTab(self._content, self)
        self.settings_tab = SettingsTab(self._content, self)
        self.lighting_tab = LightingTab(self._content, self)
        self.system_tab = SystemTab(self._content, self)
        self.lang_tab = LangTab(self._content, self)
        self.logs_tab = LogsTab(self._content, self)
        self.about_tab = AboutTab(self._content, self)
        self._tab_frames = {
            "Overview": self.overview_tab,
            "Driving": self.controls_tab,
            "Haptics": self.settings_tab,
            "Lighting": self.lighting_tab,
            "Profiles": self.profiles_tab,
            "System":   self.system_tab,
            "Language": self.lang_tab,
            "Logs":     self.logs_tab,
            "About":    self.about_tab,
        }
        self._active_nav: str | None = None
        self._select_nav("Overview")

    def _select_nav(self, key: str):
        if key == self._active_nav:
            return
        if self._active_nav:
            self._tab_frames[self._active_nav].pack_forget()
            prev = self._nav_buttons[self._active_nav]
            prev.configure(fg_color="transparent", text_color=T.TEXT_MUTED)
        self._tab_frames[key].pack(fill="both", expand=True,
                                   padx=T.PAD_LG, pady=T.PAD_LG)
        btn = self._nav_buttons[key]
        btn.configure(fg_color=T.BG_ACTIVE, text_color=T.TEXT)
        self._active_nav = key

    # MARK: lifecycle -------------------------------------------------------

    def run(self):
        self.root.after(0, self._start_backend)
        self._update_service.start_background()
        self.root.after(100, self._tick_usb_audio)
        self.root.after(1000, self._tick_status)
        self.root.after(100, self._drain_logs)
        try:
            self.root.mainloop()
        finally:
            self._teardown()

    def _on_close(self):
        # Kept for backend-triggered shutdown (e.g. exit-detection).
        self.request_close("backend")

    def _hide_to_tray(self):
        if not self._tray.start():
            return
        try:
            self.root.withdraw()
        except tk.TclError:
            pass

    def _on_unmap(self, event):
        if event.widget is not self.root:
            return
        if not self.settings.minimize_to_tray:
            return
        try:
            if self.root.state() == "iconic":
                self._hide_to_tray()
        except tk.TclError:
            pass

    def _show_window(self):
        try:
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.focus_force()
        except tk.TclError:
            pass

    def request_close(self, reason: str = "user", before_exit=None):
        """Route every graceful GUI exit through the named-profile prompt."""
        if self._tearing_down or self._close_dialog is not None:
            return
        self._show_window()
        if self._profile_session.needs_named_save(self.settings):
            def _save(name: str) -> bool:
                final = profiles.save_profile(name, self.settings)
                if not final:
                    return False
                self._profile_session.accept_current_default(self.settings)
                self._close_dialog = None
                self._refresh_profile()
                self._finish_close(before_exit)
                return True

            def _discard():
                self._close_dialog = None
                self._finish_close(before_exit)

            def _cancel():
                self._close_dialog = None

            self._close_dialog = UnsavedProfileDialog(
                self.root,
                suggested_name=profiles.next_profile_name(),
                on_save=_save,
                on_discard=_discard,
                on_cancel=_cancel,
            )
            return
        self._finish_close(before_exit)

    def _finish_close(self, before_exit=None):
        if before_exit is not None:
            try:
                before_exit()
            except Exception as exc:
                log.warning("Pre-exit action failed: %s", exc)
                self.toast(t("Could not start update: {error}").format(error=exc))
                return
        self._perform_quit()

    def _quit(self):
        """Compatibility entry point for callers outside the window protocol."""
        self.request_close("legacy")

    def _perform_quit(self):
        try:
            self._tray.stop()
        except Exception:
            pass
        self._teardown()
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def mark_default_saved(self):
        self._profile_session.accept_current_default(self.settings)

    def request_factory_reset(self):
        if self._tearing_down or self._reset_dialog is not None:
            return
        self._show_window()

        def _confirm() -> bool:
            if not preferences.restore_factory(self.settings):
                return False
            self._profile_session.accept_current_default(self.settings)
            set_language(self.settings.language)
            self.refresh_setting_widgets()
            self._refresh_profile()
            self._reset_dialog = None
            log.info("All settings restored to factory defaults.")
            self.toast(t("Factory defaults restored. Restart to refresh the interface language."))
            return True

        def _cancel():
            self._reset_dialog = None

        self._reset_dialog = FactoryResetDialog(
            self.root, on_confirm=_confirm, on_cancel=_cancel
        )

    def _teardown(self):
        if self._tearing_down:
            return
        self._tearing_down = True
        root = logging.getLogger()
        for h in list(root.handlers):
            if isinstance(h, _QueueLogHandler):
                root.removeHandler(h)
        self._stop.set()
        self._update_service.stop()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._usb_audio_lifecycle.close()
        if self._listener_cm:
            try:
                self._listener_cm.__exit__(None, None, None)
            except Exception:
                pass
        if self._ds:
            try:
                self._ds.close()
            except Exception:
                pass

    def _install_log_handler(self):
        root = logging.getLogger()
        root.handlers.clear()
        h = _QueueLogHandler(self._log_queue)
        h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                          datefmt="%H:%M:%S"))
        root.addHandler(h)
        root.setLevel(getattr(logging, DEFAULT_LOG_LEVEL))

    def _drain_logs(self):
        if self._tearing_down:
            return
        for _ in range(200):
            try:
                level, msg = self._log_queue.get_nowait()
            except queue.Empty:
                break
            self.logs_tab.write(level, msg)
        self.root.after(100, self._drain_logs)

    def _start_backend(self):
        s = self.settings
        try:
            preferences.load(s)
            self._ds = make_backend(s, s.enable_startup_pulse)
            self._ds.open()
            self._backend_error = ""
        except Exception as exc:
            self._backend_error = str(exc) or type(exc).__name__
            log.exception("Controller backend startup failed")
            self._refresh_status()
            self.overview_tab.refresh()
            return
        try:
            self._listener_cm = forzahorizon.UDPListener(
                s.udp_host, s.udp_port, s.udp_timeout, s.udp_forward_to, s.udp_forward)
            self._listener = self._listener_cm.__enter__()
            self._udp_error = ""
            log.info("Listening on %s:%d", s.udp_host, s.udp_port)
            log.info("In game: HUD & Gameplay -> Data Out: ON, IP %s, Port %d",
                     s.udp_host, s.udp_port)
            if s.use_dsx:
                log.info("DSX mode: sending triggers to %s:%d", s.dsx_host, s.dsx_port)
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
        except OSError as exc:
            self._udp_error = str(exc) or type(exc).__name__
            log.exception("UDP bind failed on %s:%d", s.udp_host, s.udp_port)
            self._refresh_status()
            self.overview_tab.refresh()
        except Exception as exc:
            self._udp_error = str(exc) or type(exc).__name__
            log.exception("Telemetry listener startup failed")
            self._refresh_status()
            self.overview_tab.refresh()

    def _run_loop(self):
        try:
            loop.run(
                self._ds,
                self._listener,
                self.settings,
                stop_event=self._stop,
                usb_audio=self._usb_audio,
            )
        except Exception:
            log.exception("Telemetry loop crashed")
        finally:
            if not self._stop.is_set():
                try:
                    self.root.after(0, self._on_close)
                except (RuntimeError, tk.TclError):
                    pass

    def _restart_backend(self):
        """Swap the running backend without touching the UDP listener.
        Called off the Tk thread (via threading.Thread) so we can join the old loop."""
        # MARK: stop old loop + backend, reuse listener
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._ds:
            self._ds.close()
        self._stop.clear()
        s = self.settings
        try:
            # MARK: suppress pulse on hot-swap
            self._ds = make_backend(s, False)
            self._ds.open()
            self._backend_error = ""
            if s.use_dsx:
                log.info("DSX mode: sending triggers to %s:%d", s.dsx_host, s.dsx_port)
            else:
                log.info("HID mode: writing direct to DualSense")
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
        except Exception as exc:
            self._backend_error = str(exc) or type(exc).__name__
            log.exception("Backend restart failed")
            try:
                self.root.after(0, lambda error=exc: self.status_pill.set_label(
                    t("Backend failed: {error}").format(error=error)))
            except (RuntimeError, tk.TclError):
                pass

    # MARK: status / profile ------------------------------------------------

    def _tick_usb_audio(self):
        if self._tearing_down:
            return
        controller = self._ds if self._listener is not None else None
        self._usb_audio_lifecycle.sync(controller, self.settings)
        self.root.after(1000, self._tick_usb_audio)

    def _tick_status(self):
        if self._tearing_down:
            return
        self._refresh_status()
        self._refresh_update_badge()
        self.overview_tab.refresh()
        self.root.after(1000, self._tick_status)

    def _refresh_update_badge(self):
        from modules.update.presentation import has_update_notice

        badge = self._nav_badges.get("System")
        if badge is None:
            return
        if has_update_notice(self._update_service.snapshot()):
            badge.place(relx=1.0, rely=0.5, x=-12, anchor="e")
        else:
            badge.place_forget()

    def _refresh_status(self):
        if self._backend_error:
            self.status_pill.set_dot_color(T.RED)
            self.status_pill.set_label(t("Controller backend error"))
            return
        if self._udp_error:
            self.status_pill.set_dot_color(T.RED)
            self.status_pill.set_label(t("UDP port {port} in use").format(
                port=self.settings.udp_port
            ))
            return
        ds = self._ds
        if self.settings.use_dsx:
            if ds and ds.connected:
                color, label = T.BLUE, t("DSX: active")
            else:
                color, label = T.RED, t("DSX: off")
        elif ds and getattr(ds, "persistent", False):
            color, label = T.GREEN, f"{t('connected')} - {t('latched')}"
        elif ds and ds.connected:
            color, label = T.GREEN, t("connected")
        else:
            color, label = T.RED, t("waiting")
        self.status_pill.set_dot_color(color)
        self.status_pill.set_label(label)

    def _refresh_profile(self):
        try:
            active = profiles.load_profiles().get("active") or t("(none)")
        except Exception:
            active = t("(none)")
        self.profile_pill.set_label(active)

    refresh_profile = _refresh_profile
    refresh_status = _refresh_status

    # MARK: shared helpers --------------------------------------------------

    def register_refresh(self, fn):
        self._refresh_callbacks.append(fn)

    def refresh_setting_widgets(self):
        self._refreshing = True
        try:
            for fn in self._refresh_callbacks:
                try:
                    fn()
                except Exception:
                    log.exception("refresh callback failed")
        finally:
            self._refreshing = False

    def haptic(self, on_state: bool):
        if self._ds and self._ds.connected:
            threading.Thread(target=self._do_haptic, args=(on_state,), daemon=True).start()

    def _do_haptic(self, on_state: bool):
        amp = HAPTIC_AMP_ON if on_state else HAPTIC_AMP_OFF
        v = vibrate(HAPTIC_FREQ_HZ, amp)
        self._ds.set(v, v)
        time.sleep(HAPTIC_DURATION_S)
        self._ds.set(off(), off())

    @staticmethod
    def _open_url(url: str):
        threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
