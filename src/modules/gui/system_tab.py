"""System tab: controller selection, built-in updates, and app settings."""
import logging
import threading
from tkinter import filedialog

import customtkinter as ctk

from lang import t
from modules.config import preferences
from modules.dualsense.main import _enumerate_dualsenses, _is_bluetooth, identify_pulse
from modules.forzahorizon.fh6_language import (
    FH6Install,
    FH6LanguageError,
    LanguageInspection,
    discover_fh6_install,
    enable_chinese_text_english_voice,
    inspect_language_state,
    is_fh6_running,
    repair_native_language,
    restore_native_language,
    validate_game_root,
)
from modules.forzahorizon.fh6_language_presentation import LanguageView, language_view
from modules.update import UpdatePhase
from modules.update.presentation import localized_status

from . import theme as T
from . import widgets as W
from .dialogs import ConfirmationDialog
from .settings_tab import SYSTEM_SECTIONS, SettingsTab

log = logging.getLogger("fhds")

class SystemTab(SettingsTab):
    SECTIONS = SYSTEM_SECTIONS
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
        self._controller_card: "W.Card | None" = None
        self._dsx_note: "W.Hint | None" = None
        self._updates_card: "W.Card | None" = None
        self._fh6_install: FH6Install | None = None
        self._fh6_inspection = inspect_language_state(None)
        self._fh6_game_running = False
        self._fh6_scan_busy = False
        self._fh6_operation_busy = False
        self._fh6_error = ""
        self._fh6_status: ctk.CTkLabel | None = None
        self._fh6_detail: ctk.CTkLabel | None = None
        self._fh6_path: ctk.CTkLabel | None = None
        self._fh6_steam_language: ctk.CTkLabel | None = None
        self._fh6_action: ctk.CTkButton | None = None
        self._fh6_view: LanguageView | None = None
        super().__init__(parent, app)
        threading.Thread(target=self._enumerate_async, daemon=True).start()
        self.app.root.after(250, self._refresh_update_status)
        self.app.root.after(100, lambda: self._start_fh6_scan(rediscover=True))
        self.app.root.after(5000, self._tick_fh6_status)

    def _build(self):
        self._build_controller_card()
        self._build_dsx_note()
        self._build_updates_card()
        self._build_fh6_language_card()
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
        anchor = self._updates_card
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

    # MARK: FH6 language archives -----------------------------------------

    def _build_fh6_language_card(self):
        card = W.Card(self._scroll)
        card.pack(fill="x", pady=(0, T.PAD_MD))
        W.H2(card, t("FH6 Chinese text + English voice")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_XS)
        )
        W.Hint(
            card,
            t(
                "Windows Steam only. Detection is automatic, but files change only after you press a button and confirm."
            ),
            wrap=self.app.px(640),
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        self._fh6_status = W.Body(card, t("Scanning for FH6"))
        self._fh6_status.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._fh6_detail = W.Hint(card, "", wrap=self.app.px(640))
        self._fh6_detail.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._fh6_path = W.Hint(card, t("Install folder: not found"), wrap=self.app.px(640))
        self._fh6_path.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._fh6_steam_language = W.Hint(card, t("Steam language: unknown"))
        self._fh6_steam_language.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        self._fh6_action = W.PrimaryButton(
            actions,
            t("Enable Chinese text + English voice"),
            self._request_fh6_action,
            width=230,
        )
        W.SecondaryButton(
            actions,
            t("Rescan"),
            lambda: self._start_fh6_scan(rediscover=True),
            width=100,
        ).pack(side="left", padx=(0, T.PAD_SM))
        W.GhostButton(
            actions,
            t("Choose folder"),
            self._choose_fh6_folder,
            width=120,
        ).pack(side="left")

    def _tick_fh6_status(self):
        if self.app._tearing_down:
            return
        self._start_fh6_scan(rediscover=False)
        self.app.root.after(5000, self._tick_fh6_status)

    def _start_fh6_scan(self, *, rediscover: bool, manual_path: str = ""):
        if self._fh6_scan_busy or self._fh6_operation_busy or self.app._tearing_down:
            return
        self._fh6_scan_busy = True
        self._fh6_error = ""
        self._render_fh6_status()

        def worker():
            error = ""
            try:
                if manual_path:
                    install = validate_game_root(manual_path, source="Manual")
                elif self._fh6_install is not None and not rediscover:
                    install = self._fh6_install
                else:
                    install = discover_fh6_install(self.settings.fh6_install_path)
                inspection = inspect_language_state(install)
                running = is_fh6_running(install) if install is not None else False
            except Exception as exc:
                install = None
                inspection = inspect_language_state(None)
                running = False
                error = str(exc) or type(exc).__name__
                log.exception("FH6 language status scan failed")
            try:
                self.app.root.after(
                    0,
                    lambda: self._apply_fh6_scan(install, inspection, running, error),
                )
            except Exception:
                pass

        threading.Thread(target=worker, name="fhds-fh6-language-scan", daemon=True).start()

    def _apply_fh6_scan(self, install, inspection, running, error):
        self._fh6_scan_busy = False
        self._fh6_install = install
        self._fh6_inspection = inspection
        self._fh6_game_running = running
        self._fh6_error = error
        if install is not None:
            resolved = str(install.root)
            if self.settings.fh6_install_path != resolved:
                self.settings.fh6_install_path = resolved
                preferences.save(self.settings)
        self._render_fh6_status()

    def _render_fh6_status(self):
        if self._fh6_status is None:
            return
        view = language_view(
            self._fh6_inspection,
            game_running=self._fh6_game_running,
            translate=t,
        )
        self._fh6_view = view
        status = t("Scanning for FH6") if self._fh6_scan_busy else view.status
        detail = self._fh6_error or view.detail
        if self._fh6_operation_busy:
            status = t("Changing FH6 language files")
            detail = t("Please wait. Do not start FH6 until the operation finishes.")
        self._fh6_status.configure(text=status)
        self._fh6_detail.configure(text=detail)
        install = self._fh6_inspection.install
        self._fh6_path.configure(
            text=(
                t("Install folder: {path}").format(path=install.root)
                if install is not None
                else t("Install folder: not found")
            )
        )
        language = install.steam_language if install and install.steam_language else t("unknown")
        self._fh6_steam_language.configure(
            text=t("Steam language: {language}").format(language=language)
        )
        self._fh6_action.pack_forget()
        if view.action:
            self._fh6_action.configure(
                text=view.action_label,
                state=(
                    "normal"
                    if view.action_enabled and not self._fh6_scan_busy and not self._fh6_operation_busy
                    else "disabled"
                ),
            )
            self._fh6_action.pack(side="left", padx=(0, T.PAD_SM))

    def _choose_fh6_folder(self):
        selected = filedialog.askdirectory(
            parent=self.app.root,
            title=t("Choose the Forza Horizon 6 install folder"),
            mustexist=True,
        )
        if selected:
            self._start_fh6_scan(rediscover=False, manual_path=selected)

    def _request_fh6_action(self):
        view = self._fh6_view
        if view is None or not view.action or not view.action_enabled:
            return
        headings = {
            "enable": t("Enable Chinese text + English voice?"),
            "restore": t("Restore original FH6 language files?"),
            "repair": t("Repair interrupted FH6 language swap?"),
        }
        messages = {
            "enable": t(
                "FHDS will exchange the names of CHS.zip and EN.zip. Close FH6 first. "
                "Steam updates or file verification may restore the original files."
            ),
            "restore": t(
                "FHDS will exchange the archive names again and restore Chinese to CHS.zip "
                "and English to EN.zip. Close FH6 first."
            ),
            "repair": t(
                "FHDS found an interrupted two-file swap. It will only move the identified "
                "Chinese and English archives back to their original names."
            ),
        }
        message = messages[view.action]
        if view.unknown_language_warning:
            message += " " + t(
                "Steam language could not be verified as English. Continue only if FH6 is set to English in Steam."
            )
        ConfirmationDialog(
            self.app.root,
            heading=headings[view.action],
            message=message,
            confirm_label=view.action_label,
            on_confirm=lambda: self._run_fh6_action(
                view.action,
                allow_unknown=view.unknown_language_warning,
            ),
        )

    def _run_fh6_action(self, action: str, *, allow_unknown: bool):
        if self._fh6_install is None or self._fh6_operation_busy:
            return
        install = self._fh6_install
        self._fh6_operation_busy = True
        self._fh6_error = ""
        self._render_fh6_status()

        def worker():
            try:
                if action == "enable":
                    result = enable_chinese_text_english_voice(
                        install,
                        allow_unknown_steam_language=allow_unknown,
                    )
                elif action == "restore":
                    result = restore_native_language(install)
                elif action == "repair":
                    result = repair_native_language(install)
                else:
                    raise FH6LanguageError(f"Unknown FH6 language action: {action}")
                error = ""
            except Exception as exc:
                result = inspect_language_state(install)
                error = str(exc) or type(exc).__name__
                log.exception("FH6 language action failed")
            try:
                self.app.root.after(0, lambda: self._finish_fh6_action(result, error))
            except Exception:
                pass

        threading.Thread(target=worker, name="fhds-fh6-language-action", daemon=True).start()

    def _finish_fh6_action(self, inspection: LanguageInspection, error: str):
        self._fh6_operation_busy = False
        self._fh6_inspection = inspection
        # Every operation checks that FH6 is closed immediately before each
        # rename. The periodic background scan will refresh this flag again.
        self._fh6_game_running = False
        self._fh6_error = error
        self._render_fh6_status()
        self.app.toast(
            t("FH6 language change failed") if error else t("FH6 language files updated")
        )

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
        if self._update_status is not None:
            self._update_status.configure(text=localized_status(snapshot, t))
        if self._update_progress is not None:
            self._update_progress.set(snapshot.progress)
        if self._update_action is not None:
            self._update_action.pack_forget()
            if snapshot.phase is UpdatePhase.AVAILABLE:
                self._update_action.configure(text=t("Download update"), state="normal")
                self._update_action.pack(side="left", padx=(0, T.PAD_SM))
            elif snapshot.phase is UpdatePhase.READY:
                self._update_action.configure(text=t("Restart and install"), state="normal")
                self._update_action.pack(side="left", padx=(0, T.PAD_SM))
        if self._release_button is not None:
            self._release_button.pack_forget()
            if snapshot.release is not None:
                self._release_button.pack(side="left")
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
