"""System tab: controller selection, built-in updates, and app settings."""
import logging
import threading

import customtkinter as ctk

from lang import t
from modules.config import preferences
from modules.dualsense.main import _enumerate_dualsenses, _is_bluetooth, identify_pulse
from modules.update import UpdatePhase
from modules.update.presentation import (
    UpdateStatusPresentation,
    update_status_presentation,
)

from . import theme as T
from . import widgets as W
from .settings_tab import SYSTEM_SECTIONS, SettingsTab

log = logging.getLogger("fhds")

class SystemTab(SettingsTab):
    SWITCH_SECTIONS: tuple = ()
    SECTIONS: list = SYSTEM_SECTIONS
    EXPERIMENTAL_SECTIONS: tuple = ()
    SHOW_RESET = False
    SHOW_EXPERIMENTAL = False
    PAGE_TITLE = "System and updates"
    PAGE_SUBTITLE = "Controller, updates, and app-level options."

    def __init__(self, parent, app):
        self._devices: list[dict] = []
        self._lock_var: ctk.StringVar | None = None
        self._radio_holder: "W.FastScroll | None" = None
        self._radio_buttons: list[ctk.CTkRadioButton] = []
        self._update_switch: ctk.CTkSwitch | None = None
        self._auto_download_switch: ctk.CTkSwitch | None = None
        self._update_status: ctk.CTkLabel | None = None
        self._update_progress: ctk.CTkProgressBar | None = None
        self._update_action: ctk.CTkButton | None = None
        self._release_button: ctk.CTkButton | None = None
        self._update_presentation: UpdateStatusPresentation | None = None
        self._controller_card: "W.Card | None" = None
        self._dsx_note: "W.Hint | None" = None
        self._display_card: "W.Card | None" = None
        self._dpi_status: ctk.CTkLabel | None = None
        self._dpi_warning: ctk.CTkLabel | None = None
        self._updates_card: "W.Card | None" = None
        super().__init__(parent, app)
        threading.Thread(target=self._enumerate_async, daemon=True).start()
        self.app.root.after(250, self._refresh_update_status)

    def _build(self):
        self._build_controller_card()
        self._build_dsx_note()
        self._build_display_card()
        self._build_updates_card()
        # Standard sections from SYSTEM_SECTIONS
        super()._build()
        # Run after every card exists so the DSX/controller swap can reference them.
        self._sync_controller_visibility()

    # MARK: controller card -------------------------------------------------

    def _build_controller_card(self):
        card = self._controller_card = W.Card(self._scroll)
        card.pack(fill="x", pady=(0, T.PAD_MD))
        W.H2(card, t("Controller")).pack(anchor="w", padx=T.PAD_MD,
                                         pady=(T.PAD_MD, T.PAD_XS))
        W.Hint(card, t("Lock the app to a specific DualSense, or let it pick the first one.")
               ).pack(anchor="w", padx=T.PAD_MD, pady=(0, T.PAD_SM))

        self._lock_var = ctk.StringVar(value=self.settings.controller_lock_serial or "")
        self._radio_holder = W.FastScroll(card, height=140,
                                                    fg_color=T.BG_INPUT,
                                                    corner_radius=6)
        self._radio_holder.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        self._render_radio_buttons()

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        W.SecondaryButton(actions, t("Rescan"), self._on_rescan, width=120
                          ).pack(side="left", padx=(0, T.PAD_SM))
        W.SecondaryButton(
            actions,
            t("Reconnect now"),
            self._on_reconnect_now,
            width=150,
        ).pack(side="left")

    def _build_dsx_note(self):
        # Shown in place of the controller card while DSX owns the controller.
        self._dsx_note = W.Hint(
            self._scroll,
            t("DSX is active - controller managed by DSX. "
              "Disable DSX to select a controller here."),
            wrap=self.app.px(640),
        )

    def _sync_controller_visibility(self):
        """Controller picking is meaningless while DSX owns the device, so swap the
        controller card for an explanatory note when DSX is on."""
        if self._controller_card is None or self._dsx_note is None:
            return
        anchor = self._display_card or self._updates_card
        if anchor is None:
            anchor = next(
                (widget for widget in self._scroll.pack_slaves()
                 if widget not in (self._controller_card, self._dsx_note)),
                None,
            )
        pack_options = {"fill": "x", "pady": (0, T.PAD_MD)}
        if anchor is not None:
            pack_options["before"] = anchor
        if self.settings.use_dsx:
            self._controller_card.pack_forget()
            self._dsx_note.pack(padx=T.PAD_MD, **pack_options)
        else:
            self._dsx_note.pack_forget()
            self._controller_card.pack(**pack_options)

    def _build_updates_card(self):
        card = self._updates_card = W.Card(self._scroll)
        card.pack(fill="x", pady=(0, T.PAD_MD))
        W.H2(card, t("Updates")).pack(anchor="w", padx=T.PAD_MD,
                                      pady=(T.PAD_MD, T.PAD_SM))
        supported = self.app._update_service.supported
        self._update_switch = ctk.CTkSwitch(card,
                                            text=t("Automatically check for updates"),
                                            command=self._on_update_toggle,
                                            state="normal" if supported else "disabled")
        if self.settings.check_for_updates:
            self._update_switch.select()
        self._update_switch.pack(anchor="w", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._auto_download_switch = ctk.CTkSwitch(
            card,
            text=t("Download updates in the background"),
            command=self._on_auto_download_toggle,
            state="normal" if supported else "disabled",
        )
        if self.settings.auto_download_updates:
            self._auto_download_switch.select()
        self._auto_download_switch.pack(anchor="w", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        W.Hint(
            card,
            t(
                "The standalone EXE can update itself. Background download never restarts the app without confirmation."
                if supported else
                "Built-in updates require the Windows standalone EXE"
            ),
            wrap=self.app.px(640),
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))

        self._update_status = W.Body(card, t("Update status: idle"))
        self._update_status.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._update_progress = ctk.CTkProgressBar(card, height=8)
        self._update_progress.set(0)
        self._update_progress.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        check_button = W.SecondaryButton(
            actions, t("Check now"), self._on_check_update, width=120
        )
        if not supported:
            check_button.configure(state="disabled")
        check_button.pack(side="left", padx=(0, T.PAD_SM))
        self._update_action = W.PrimaryButton(
            actions, t("Download update"), self._on_update_action, width=150
        )
        self._release_button = W.GhostButton(
            actions, t("View release"), self._open_update_release, width=120
        )

    def _build_display_card(self):
        card = self._display_card = W.Card(self._scroll)
        card.pack(fill="x", pady=(0, T.PAD_MD))
        W.H2(card, t("Display scaling")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_SM)
        )
        self._dpi_status = W.Body(card, "")
        self._dpi_status.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._dpi_warning = W.Warning(card, "", wrap=self.app.px(640))
        self._dpi_warning.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        self.set_dpi_snapshot(self.app.dpi_snapshot)

    def set_dpi_snapshot(self, snapshot):
        if self._dpi_status is not None:
            self._dpi_status.configure(text=self.app.dpi_status_text(snapshot))
        if self._dpi_warning is not None:
            warning = "" if snapshot.per_monitor_v2 else t(
                "Per-Monitor v2 is not active. Check the EXE compatibility high-DPI override."
            )
            self._dpi_warning.configure(text=warning)

    # MARK: controller list -------------------------------------------------

    def _attached_serial(self) -> str:
        ds = getattr(self.app, "_ds", None)
        if ds is None or not ds.connected:
            return ""
        return getattr(ds, "dev_serial", "") or ""

    def _render_radio_buttons(self):
        if self._radio_holder is None or self._lock_var is None:
            return
        for rb in self._radio_buttons:
            rb.destroy()
        self._radio_buttons.clear()
        attached = self._attached_serial()

        rb = ctk.CTkRadioButton(self._radio_holder, text=t("Auto (first found)"),
                                variable=self._lock_var, value="",
                                command=self._on_lock_changed)
        rb.pack(anchor="w", padx=T.PAD_SM, pady=2)
        self._radio_buttons.append(rb)

        for d in self._devices:
            sn = d.get("serial_number") or ""
            transport = "BT" if _is_bluetooth(d) else "USB"
            if sn:
                marker = f"  < {t('attached now')}" if sn == attached else ""
                rb = ctk.CTkRadioButton(self._radio_holder,
                                        text=f"[{transport}] {sn}{marker}",
                                        variable=self._lock_var, value=sn,
                                        command=self._on_lock_changed)
            else:
                rb = ctk.CTkRadioButton(self._radio_holder,
                                        text=f"[{transport}] {t('(no serial - not selectable)')}",
                                        variable=self._lock_var,
                                        value=f"__noserial_{id(d)}__",
                                        state="disabled")
            rb.pack(anchor="w", padx=T.PAD_SM, pady=2)
            self._radio_buttons.append(rb)

    def _on_rescan(self):
        threading.Thread(target=self._enumerate_async, daemon=True).start()

    def _on_reconnect_now(self):
        controller = getattr(self.app, "_ds", None)
        reconnect = getattr(controller, "force_reconnect", None)
        if callable(reconnect):
            reconnect()
            log.info("Immediate DualSense reconnect requested")

    def _enumerate_async(self):
        try:
            devs = _enumerate_dualsenses()
        except Exception:
            log.exception("controller enumeration failed")
            devs = []
        try:
            self.app.root.after(0, lambda: self._apply_devices(devs))
        except Exception:
            pass

    def _apply_devices(self, devices: list[dict]):
        self._devices = devices
        if self._lock_var is not None:
            self._lock_var.set(self.settings.controller_lock_serial or "")
        self._render_radio_buttons()

    def _on_lock_changed(self):
        if self._lock_var is None:
            return
        new = self._lock_var.get()
        if new.startswith("__noserial_"):
            return
        if new:
            info = next((d for d in self._devices
                         if (d.get("serial_number") or "") == new), None)
            if info is not None:
                threading.Thread(
                    target=identify_pulse, args=(info,),
                    kwargs={"force": self.settings.startup_pulse_force},
                    daemon=True,
                ).start()
        if self.settings.controller_lock_serial != new:
            self.settings.controller_lock_serial = new
            preferences.save(self.settings)
            log.info("controller_lock_serial = %r", new)
        ds = getattr(self.app, "_ds", None)
        if ds is not None:
            ds.set_selection(new)
            if new and new != self._attached_serial():
                ds.force_reconnect()
        threading.Thread(target=self._enumerate_async, daemon=True).start()

    # MARK: updates ---------------------------------------------------------

    def _on_switch(self, attr: str):
        super()._on_switch(attr)
        if attr == "use_dsx":
            self._sync_controller_visibility()

    def _on_update_toggle(self):
        if self._update_switch is None:
            return
        value = bool(self._update_switch.get())
        if self.settings.check_for_updates != value:
            self.settings.check_for_updates = value
            preferences.save(self.settings)
            log.info("check_for_updates = %s", value)

    def _on_auto_download_toggle(self):
        if self._auto_download_switch is None:
            return
        value = bool(self._auto_download_switch.get())
        if self.settings.auto_download_updates != value:
            self.settings.auto_download_updates = value
            preferences.save(self.settings)
            log.info("auto_download_updates = %s", value)

    def _on_check_update(self):
        self.app._update_service.check_now()

    def _on_update_action(self):
        snapshot = self.app._update_service.snapshot()
        if snapshot.phase is UpdatePhase.AVAILABLE:
            self.app._update_service.download()
        elif snapshot.phase is UpdatePhase.READY:
            self.app.request_close(
                "update",
                before_exit=self.app._update_service.install_on_exit,
            )

    def _open_update_release(self):
        release = self.app._update_service.snapshot().release
        if release is not None and release.html_url:
            self.app._open_url(release.html_url)

    def _refresh_update_status(self):
        if self.app._tearing_down:
            return
        snapshot = self.app._update_service.snapshot()
        current = update_status_presentation(snapshot, t)
        previous = self._update_presentation
        if current != previous:
            self._update_presentation = current
            if (
                self._update_status is not None
                and (previous is None or current.status != previous.status)
            ):
                self._update_status.configure(text=current.status)
            if (
                self._update_progress is not None
                and (previous is None or current.progress != previous.progress)
            ):
                self._update_progress.set(current.progress)
            if self._update_action is not None and (
                previous is None or current.action != previous.action
            ):
                if current.action is None:
                    if previous is not None and previous.action is not None:
                        self._update_action.pack_forget()
                else:
                    action_text = (
                        "Download update"
                        if current.action == "download"
                        else "Restart and install"
                    )
                    self._update_action.configure(text=t(action_text), state="normal")
                    if previous is None or previous.action is None:
                        self._update_action.pack(side="left", padx=(0, T.PAD_SM))
            if self._release_button is not None and (
                previous is None
                or current.release_visible != previous.release_visible
            ):
                if current.release_visible:
                    self._release_button.pack(side="left")
                elif previous is not None and previous.release_visible:
                    self._release_button.pack_forget()
        self.app.root.after(250, self._refresh_update_status)

    def _refresh_widgets(self):
        super()._refresh_widgets()
        if self._update_switch is not None:
            want = bool(self.settings.check_for_updates)
            if bool(self._update_switch.get()) != want:
                if want:
                    self._update_switch.select()
                else:
                    self._update_switch.deselect()
        if self._auto_download_switch is not None:
            want_download = bool(self.settings.auto_download_updates)
            if bool(self._auto_download_switch.get()) != want_download:
                if want_download:
                    self._auto_download_switch.select()
                else:
                    self._auto_download_switch.deselect()
        if self._lock_var is not None:
            self._lock_var.set(self.settings.controller_lock_serial or "")
            self._render_radio_buttons()
