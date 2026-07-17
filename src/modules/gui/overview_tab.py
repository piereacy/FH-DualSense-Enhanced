"""At-a-glance status and shortcuts shared by the GUI shell."""
from __future__ import annotations

import logging
import queue
import threading
import time

import customtkinter as ctk

from lang import t
from modules.config import preferences, profiles
from modules.forzahorizon import (
    FH6Install,
    discover_fh6_install,
    is_fh6_running,
    is_windows_steam_supported,
    launch_fh6_via_steam,
)
from . import theme as T
from . import widgets as W
from .overview_status import (
    controller_status,
    fh6_launch_button_status,
    profile_status,
    telemetry_status,
    update_status,
)

log = logging.getLogger("fhds.gui.overview")

FH6_SCAN_INTERVAL_S = 5.0
FH6_LAUNCH_TIMEOUT_S = 20.0


class OverviewTab(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.settings = app.settings
        self._fh6_install: FH6Install | None = None
        self._fh6_scan_busy = False
        self._fh6_launch_busy = False
        self._fh6_launch_deadline = 0.0
        self._fh6_last_scan = 0.0
        self._fh6_path_hint = self.settings.fh6_install_path
        self._fh6_scan_results: queue.SimpleQueue[FH6Install | None] = queue.SimpleQueue()
        self._fh6_launch_results: queue.SimpleQueue[str] = queue.SimpleQueue()
        self._build()
        app.register_refresh(self.refresh)
        self.refresh()

    def _build(self):
        W.PageHeader(
            self, t("Overview"),
            t("Controller, telemetry, profile, and update status at a glance."),
        ).pack(fill="x", pady=(0, T.PAD_MD))

        scroll = W.FastScroll(self)
        scroll.pack(fill="both", expand=True)

        status = ctk.CTkFrame(scroll, fg_color="transparent")
        status.pack(fill="x")
        for col in range(2):
            status.grid_columnconfigure(col, weight=1, uniform="overview")

        _, self.controller_value, self.controller_hint = self._status_card(
            status, 0, t("DualSense"), t("Waiting"), t("USB or Bluetooth")
        )
        _, self.telemetry_value, self.telemetry_hint = self._status_card(
            status, 1, t("Forza telemetry"), t("Waiting for packets"), t("UDP data out")
        )
        _, self.profile_value, self.profile_hint = self._status_card(
            status, 2, t("Active profile"), "-", t("Changes save instantly")
        )
        _, self.update_value, self.update_hint = self._status_card(
            status, 3, t("Updates"), t("Update status: idle"), t("Built-in updater")
        )

        quick = W.Card(scroll)
        quick.pack(fill="x", pady=(T.PAD_MD, 0))
        W.H2(quick, t("Quick access")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM)
        )
        row = ctk.CTkFrame(quick, fg_color="transparent")
        row.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        row.grid_columnconfigure((0, 1), weight=1, uniform="quick")
        W.PrimaryButton(
            row, text=t("Driving feedback"), command=lambda: self.app._select_nav("Driving")
        ).grid(row=0, column=0, sticky="ew", padx=(0, T.PAD_XS), pady=(0, T.PAD_XS))
        W.SecondaryButton(
            row, text=t("Grip haptics"), command=lambda: self.app._select_nav("Haptics")
        ).grid(row=0, column=1, sticky="ew", padx=(T.PAD_XS, 0), pady=(0, T.PAD_XS))
        W.SecondaryButton(
            row, text=t("System and updates"), command=lambda: self.app._select_nav("System")
        ).grid(row=1, column=0, sticky="ew", padx=(0, T.PAD_XS), pady=(T.PAD_XS, 0))
        W.DangerButton(
            row, text=t("Restore defaults"), command=self.app.request_factory_reset
        ).grid(row=1, column=1, sticky="ew", padx=(T.PAD_XS, 0), pady=(T.PAD_XS, 0))
        self._fh6_launch_button = W.PrimaryButton(
            row,
            text=t("Finding FH6..."),
            command=self._launch_fh6,
        )
        self._fh6_launch_button.grid(
            row=2,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(T.PAD_SM, 0),
        )
        self._fh6_launch_button.configure(state="disabled")

    @staticmethod
    def _status_card(parent, index, title, value, hint):
        row, column = divmod(index, 2)
        card = W.Card(parent)
        card.grid(row=row, column=column, sticky="nsew",
                  padx=(0 if column == 0 else T.PAD_SM // 2,
                        T.PAD_SM // 2 if column == 0 else 0),
                  pady=(0 if row == 0 else T.PAD_SM // 2,
                        T.PAD_SM // 2 if row == 0 else 0))
        W.Hint(card, title).pack(anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_XS))
        value_label = ctk.CTkLabel(
            card, text=value, anchor="w", text_color=T.TEXT,
            font=ctk.CTkFont(size=T.FS_H1, weight="bold"),
        )
        value_label.pack(fill="x", padx=T.PAD_MD)
        hint_label = W.Hint(card, hint)
        hint_label.pack(anchor="w", padx=T.PAD_MD, pady=(T.PAD_XS, T.PAD_MD))
        return card, value_label, hint_label

    def refresh(self):
        controller = controller_status(
            getattr(self.app, "_ds", None),
            self.settings,
            t,
            error=getattr(self.app, "_backend_error", ""),
        )
        telemetry = telemetry_status(
            getattr(self.app, "_listener", None),
            self.settings,
            t,
            error=getattr(self.app, "_udp_error", ""),
        )
        try:
            profile = profile_status(profiles.active_name(), t)
        except Exception as exc:
            profile = profile_status("", t, error=str(exc))
        update = update_status(self.app._update_service, self.settings, t)

        for value_widget, hint_widget, status in (
            (self.controller_value, self.controller_hint, controller),
            (self.telemetry_value, self.telemetry_hint, telemetry),
            (self.update_value, self.update_hint, update),
        ):
            value_widget.configure(text=status.value)
            hint_widget.configure(text=status.hint)
        self.profile_value.configure(text=profile.value)
        self.profile_hint.configure(text=profile.hint)
        self._refresh_fh6_launch()

    def _refresh_fh6_launch(self):
        if self.app._tearing_down:
            return
        self._drain_fh6_worker_results()
        now = time.monotonic()
        path_hint = self.settings.fh6_install_path
        if path_hint != self._fh6_path_hint and not self._fh6_scan_busy:
            self._fh6_path_hint = path_hint
            self._fh6_install = None
            self._fh6_last_scan = 0.0

        try:
            running = is_fh6_running(self._fh6_install)
        except Exception:
            running = False
            log.exception("FH6 process check failed")

        if self._fh6_launch_busy:
            if running:
                self._fh6_launch_busy = False
                self._fh6_launch_deadline = 0.0
            elif now >= self._fh6_launch_deadline:
                self._fh6_launch_busy = False
                self._fh6_launch_deadline = 0.0

        supported = is_windows_steam_supported()
        if (
            supported
            and self._fh6_install is None
            and not self._fh6_scan_busy
            and not self._fh6_launch_busy
            and now - self._fh6_last_scan >= FH6_SCAN_INTERVAL_S
        ):
            self._start_fh6_scan()

        status = fh6_launch_button_status(
            t,
            supported=supported,
            scanning=self._fh6_scan_busy,
            installed=self._fh6_install is not None,
            running=running,
            launching=self._fh6_launch_busy,
        )
        self._fh6_launch_button.configure(
            text=status.label,
            state="normal" if status.enabled else "disabled",
        )

    def _drain_fh6_worker_results(self):
        try:
            while True:
                self._apply_fh6_scan(self._fh6_scan_results.get_nowait())
        except queue.Empty:
            pass
        try:
            while True:
                self._finish_fh6_launch(self._fh6_launch_results.get_nowait())
        except queue.Empty:
            pass

    def _start_fh6_scan(self):
        if self._fh6_scan_busy or self.app._tearing_down:
            return
        self._fh6_scan_busy = True
        self._fh6_last_scan = time.monotonic()

        def worker():
            install = None
            try:
                install = discover_fh6_install(self.settings.fh6_install_path)
            except Exception:
                log.exception("FH6 launch discovery failed")
            self._fh6_scan_results.put(install)

        threading.Thread(
            target=worker,
            name="fhds-fh6-launch-scan",
            daemon=True,
        ).start()

    def _apply_fh6_scan(self, install: FH6Install | None):
        if self.app._tearing_down:
            return
        self._fh6_scan_busy = False
        self._fh6_install = install
        if install is not None:
            resolved = str(install.root)
            self._fh6_path_hint = resolved
            if self.settings.fh6_install_path != resolved:
                self.settings.fh6_install_path = resolved
                preferences.save(self.settings)

    def _launch_fh6(self):
        install = self._fh6_install
        if install is None or self._fh6_launch_busy or self.app._tearing_down:
            return
        self._fh6_launch_busy = True
        self._fh6_launch_deadline = time.monotonic() + FH6_LAUNCH_TIMEOUT_S
        self._refresh_fh6_launch()

        def worker():
            error = ""
            try:
                launch_fh6_via_steam(install)
            except Exception as exc:
                error = str(exc) or type(exc).__name__
                log.exception("Could not launch FH6 through Steam")
            self._fh6_launch_results.put(error)

        threading.Thread(
            target=worker,
            name="fhds-fh6-steam-launch",
            daemon=True,
        ).start()

    def _finish_fh6_launch(self, error: str):
        if self.app._tearing_down:
            return
        if error:
            self._fh6_launch_busy = False
            self._fh6_launch_deadline = 0.0
            self.app.toast(
                t("Could not launch FH6: {error}").format(error=error[:96])
            )
        else:
            self.app.toast(t("Sent FH6 launch request to Steam"))
