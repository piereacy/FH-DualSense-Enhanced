"""FH6-only language and DualSense icon utilities for the GUI."""
from __future__ import annotations

import logging
import threading
import time
from tkinter import filedialog

import customtkinter as ctk

from lang import t
from modules.config import preferences
from modules.forzahorizon.controller_icons import (
    MOD_AUTHOR,
    MOD_URL,
    TARGETS as CONTROLLER_ICON_TARGETS,
    ControllerIconInspection,
    ControllerIconState,
    inspect_controller_icons,
    install_controller_icons,
    restore_controller_icons,
    validate_controller_icon_root,
)
from modules.forzahorizon.game_launch import (
    discover_forza_install,
    discover_xbox_forza_install,
    is_forza_game_running,
)
from modules.forzahorizon.fh6_language import (
    FH6Install,
    FH6LanguageError,
    LanguageInspection,
    discover_fh6_install,
    discover_xbox_fh6_install,
    enable_chinese_text_english_voice,
    inspect_language_state,
    is_fh6_running,
    repair_native_language,
    restore_native_language,
    validate_game_root,
)
from modules.forzahorizon.fh6_language_presentation import (
    LanguageView,
    language_summary_view,
    language_view,
)
from modules.xinput.service import STEAM_PLATFORM, normalize_forza_platform

from . import theme as T
from . import widgets as W
from .dialogs import ConfirmationDialog

log = logging.getLogger("fhds.gui.fh6_utilities")

DISCOVERY_RETRY_S = 30.0
RUNTIME_POLL_MS = 2000


class FH6UtilitiesTab(ctk.CTkFrame):
    """Explicit FH6 file tools with discovery active only while this page is visible."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self.settings = app.settings
        self._visible = False
        self._has_shown = False
        self._tick_after_id = None
        self._runtime_busy = False

        self._fh6_install: FH6Install | None = None
        self._fh6_inspection = inspect_language_state(None)
        self._fh6_game_running = False
        self._fh6_scan_busy = False
        self._fh6_silent_scan = False
        self._fh6_operation_busy = False
        self._fh6_error = ""
        self._fh6_view: LanguageView | None = None
        self._fh6_status: ctk.CTkLabel | None = None
        self._fh6_detail: ctk.CTkLabel | None = None
        self._fh6_path: ctk.CTkLabel | None = None
        self._fh6_game_language: ctk.CTkLabel | None = None
        self._fh6_display_language: ctk.CTkLabel | None = None
        self._fh6_voice_language: ctk.CTkLabel | None = None
        self._fh6_action: ctk.CTkButton | None = None
        self._fh6_action_packed = False
        self._fh6_render_cache = None
        self._fh6_platform = normalize_forza_platform(
            self.settings.preferred_forza_platform
        )
        self._fh6_path_hint = self._language_saved_path(self._fh6_platform)
        self._fh6_last_scan = 0.0
        self._fh6_scan_serial = 0
        self._fh6_active_serial: int | None = None

        self._icon_platform = normalize_forza_platform(
            self.settings.preferred_forza_platform
        )
        self._icon_inspection = inspect_controller_icons(None)
        self._icon_scan_busy = False
        self._icon_silent_scan = False
        self._icon_operation_busy = False
        self._icon_game_running = False
        self._icon_error = ""
        self._icon_status: ctk.CTkLabel | None = None
        self._icon_detail: ctk.CTkLabel | None = None
        self._icon_path: ctk.CTkLabel | None = None
        self._icon_install_action: ctk.CTkButton | None = None
        self._icon_restore_action: ctk.CTkButton | None = None
        self._icon_render_cache = None
        self._icon_path_hint = self._icon_saved_path(self._icon_platform)
        self._icon_last_scan = 0.0
        self._icon_scan_serial = 0
        self._icon_active_serial: int | None = None

        W.PageHeader(
            self,
            t("FH6 utilities"),
            t("Language files and PlayStation button icons for Forza Horizon 6."),
        ).pack(fill="x", pady=(0, T.PAD_MD))
        self._scroll = W.FastScroll(self)
        self._scroll.pack(fill="both", expand=True)
        self._build_fh6_language_card()
        self._build_controller_icon_card()

    # MARK: page lifecycle -------------------------------------------------

    def on_show(self):
        if self.app._tearing_down:
            return
        self._visible = True
        language_changed, icon_changed = self._sync_context()
        first_show = not self._has_shown
        self._has_shown = True
        if first_show or language_changed or self._fh6_install is None:
            self._start_fh6_scan(rediscover=True, silent=not first_show)
        if first_show or icon_changed or self._icon_inspection.root is None:
            self._start_icon_scan(rediscover=True, silent=not first_show)
        self._schedule_tick()

    def on_hide(self):
        self._visible = False
        if self._tick_after_id is not None:
            try:
                self.app.root.after_cancel(self._tick_after_id)
            except Exception:
                pass
            self._tick_after_id = None

    def _schedule_tick(self):
        if not self._visible or self.app._tearing_down:
            return
        if self._tick_after_id is not None:
            try:
                self.app.root.after_cancel(self._tick_after_id)
            except Exception:
                pass
        self._tick_after_id = self.app.root.after(RUNTIME_POLL_MS, self._tick_visible)

    def _tick_visible(self):
        self._tick_after_id = None
        if not self._visible or self.app._tearing_down:
            return
        language_changed, icon_changed = self._sync_context()
        now = time.monotonic()
        if language_changed:
            self._start_fh6_scan(rediscover=True)
        elif (
            self._fh6_install is None
            and not self._fh6_scan_busy
            and now - self._fh6_last_scan >= DISCOVERY_RETRY_S
        ):
            self._start_fh6_scan(rediscover=True, silent=True)
        if icon_changed:
            self._start_icon_scan(rediscover=True)
        elif (
            self._icon_inspection.root is None
            and not self._icon_scan_busy
            and now - self._icon_last_scan >= DISCOVERY_RETRY_S
        ):
            self._start_icon_scan(rediscover=True, silent=True)
        if (
            not self._runtime_busy
            and (self._fh6_install is not None or self._icon_inspection.root is not None)
        ):
            self._start_runtime_refresh()
        self._schedule_tick()

    def _sync_context(self) -> tuple[bool, bool]:
        platform = normalize_forza_platform(self.settings.preferred_forza_platform)
        language_hint = self._language_saved_path(platform)
        language_changed = (
            platform != self._fh6_platform or language_hint != self._fh6_path_hint
        )
        if language_changed:
            self._fh6_platform = platform
            self._fh6_path_hint = language_hint
            self._invalidate_fh6()

        icon_hint = self._icon_saved_path(platform)
        icon_changed = platform != self._icon_platform or icon_hint != self._icon_path_hint
        if icon_changed:
            self._icon_platform = platform
            self._icon_path_hint = icon_hint
            self._invalidate_icons()
        return language_changed, icon_changed

    def _invalidate_fh6(self):
        self._fh6_scan_serial += 1
        self._fh6_active_serial = None
        self._fh6_scan_busy = False
        self._fh6_silent_scan = False
        self._fh6_install = None
        self._fh6_inspection = inspect_language_state(None)
        self._fh6_game_running = False
        self._fh6_last_scan = 0.0
        self._fh6_render_cache = None

    def _invalidate_icons(self):
        self._icon_scan_serial += 1
        self._icon_active_serial = None
        self._icon_scan_busy = False
        self._icon_silent_scan = False
        self._icon_inspection = inspect_controller_icons(None)
        self._icon_game_running = False
        self._icon_last_scan = 0.0
        self._icon_render_cache = None

    def _start_runtime_refresh(self):
        self._runtime_busy = True
        language_install = self._fh6_install

        def worker():
            try:
                running = (
                    is_fh6_running(language_install)
                    if language_install is not None
                    else is_forza_game_running("fh6")
                )
            except Exception:
                running = False
                log.exception("FH6 process check failed")
            try:
                self.app.root.after(0, lambda: self._apply_runtime_refresh(running))
            except Exception:
                pass

        threading.Thread(target=worker, name="fhds-fh6-runtime", daemon=True).start()

    def _apply_runtime_refresh(self, running: bool):
        self._runtime_busy = False
        language_changed = self._fh6_game_running != running
        icon_changed = self._icon_game_running != running
        self._fh6_game_running = running
        self._icon_game_running = running
        if language_changed:
            self._render_fh6_status()
        if icon_changed:
            self._render_icon_status()

    # MARK: FH6 language archives -----------------------------------------

    def _language_saved_path(self, platform: str | None = None) -> str:
        platform = platform or normalize_forza_platform(
            self.settings.preferred_forza_platform
        )
        return str(
            self.settings.fh6_install_path
            if platform == STEAM_PLATFORM
            else self.settings.fh6_xbox_install_path
        )

    def _build_fh6_language_card(self):
        card = W.Card(self._scroll)
        card.pack(fill="x", pady=(0, T.PAD_MD))
        W.H2(card, t("FH6 Chinese text + English voice")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_XS)
        )
        W.Hint(
            card,
            t(
                "Windows Steam and Xbox App editions. Install folders are detected automatically; manual selection remains available."
            ),
            wrap=self.app.px(640),
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        self._fh6_status = W.Body(card, t("Scanning for FH6"))
        self._fh6_status.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._fh6_detail = W.Hint(card, "", wrap=self.app.px(640))
        self._fh6_detail.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._fh6_path = W.Hint(card, t("Install folder: not found"), wrap=self.app.px(640))
        self._fh6_path.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._fh6_game_language = W.Hint(
            card, t("Current FH6 game language: {language}").format(language=t("Unknown"))
        )
        self._fh6_game_language.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._fh6_display_language = W.Hint(
            card, t("Actual display language: {language}").format(language=t("Unknown"))
        )
        self._fh6_display_language.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._fh6_voice_language = W.Hint(
            card, t("Voice language: {language}").format(language=t("Unknown"))
        )
        self._fh6_voice_language.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))

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

    def _start_fh6_scan(
        self,
        *,
        rediscover: bool,
        manual_path: str = "",
        silent: bool = False,
    ):
        manual_path = str(manual_path).strip()
        if self._fh6_operation_busy or self.app._tearing_down:
            return
        # A folder explicitly chosen by the user supersedes an automatic scan.
        # The serial below makes the older worker result harmless when it returns.
        if self._fh6_scan_busy and not manual_path:
            return
        self._fh6_scan_serial += 1
        serial = self._fh6_scan_serial
        self._fh6_active_serial = serial
        self._fh6_scan_busy = True
        self._fh6_silent_scan = bool(silent and self._fh6_install is None)
        self._fh6_error = ""
        self._fh6_last_scan = time.monotonic()
        platform = normalize_forza_platform(self.settings.preferred_forza_platform)
        context_hint = self._language_saved_path(platform)
        current_install = self._fh6_install
        self._render_fh6_status()

        def worker():
            error = ""
            try:
                if manual_path:
                    source = "Manual Steam" if platform == STEAM_PLATFORM else "Manual Xbox App"
                    install = validate_game_root(manual_path, source=source)
                elif (
                    current_install is not None
                    and not rediscover
                    and platform == self._fh6_platform
                ):
                    install = current_install
                elif platform == STEAM_PLATFORM:
                    install = discover_fh6_install(context_hint)
                else:
                    install = discover_xbox_fh6_install(context_hint)
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
                    lambda: self._apply_fh6_scan(
                        serial,
                        platform,
                        context_hint,
                        bool(manual_path),
                        install,
                        inspection,
                        running,
                        error,
                    ),
                )
            except Exception:
                pass

        threading.Thread(target=worker, name="fhds-fh6-language-scan", daemon=True).start()

    def _apply_fh6_scan(
        self,
        serial: int,
        platform: str,
        context_hint: str,
        manual: bool,
        install,
        inspection,
        running,
        error,
    ):
        if serial != self._fh6_active_serial:
            return
        current_platform = normalize_forza_platform(self.settings.preferred_forza_platform)
        current_hint = self._language_saved_path(current_platform)
        if platform != current_platform or (not manual and context_hint != current_hint):
            self._fh6_platform = current_platform
            self._fh6_path_hint = current_hint
            self._invalidate_fh6()
            if self._visible:
                self._start_fh6_scan(rediscover=True)
            return
        self._fh6_active_serial = None
        self._fh6_scan_busy = False
        self._fh6_silent_scan = False
        self._fh6_platform = platform
        self._fh6_install = install
        self._fh6_inspection = inspection
        self._fh6_game_running = running
        self._fh6_error = error
        if manual and install is None:
            self.app.toast(t("FH6 installation not found"))
        if install is not None:
            field = (
                "fh6_install_path"
                if platform == STEAM_PLATFORM
                else "fh6_xbox_install_path"
            )
            resolved = str(install.root)
            self._fh6_path_hint = resolved
            if getattr(self.settings, field) != resolved:
                setattr(self.settings, field, resolved)
                preferences.save(self.settings)
        self._fh6_render_cache = None
        self._render_fh6_status()

    def _render_fh6_status(self):
        if self._fh6_status is None:
            return
        view = language_view(
            self._fh6_inspection,
            game_running=self._fh6_game_running,
            translate=t,
            platform=self._fh6_platform,
        )
        summary = language_summary_view(self._fh6_inspection, t)
        self._fh6_view = view
        status = view.status
        detail = self._fh6_error or view.detail
        if self._fh6_scan_busy and not self._fh6_silent_scan:
            status = t("Scanning for FH6")
        if self._fh6_operation_busy:
            status = t("Changing FH6 language files")
            detail = t("Please wait. Do not start FH6 until the operation finishes.")
        install = self._fh6_inspection.install
        path_text = (
            t("Install folder: {path}").format(path=install.root)
            if install is not None
            else t("Install folder: not found")
        )
        game_language_text = t("Current FH6 game language: {language}").format(
            language=summary.game_language
        )
        display_language_text = t("Actual display language: {language}").format(
            language=summary.display_language
        )
        voice_language_text = t("Voice language: {language}").format(
            language=summary.voice_language
        )
        action_visible = bool(view.action)
        action_enabled = bool(
            view.action_enabled
            and not self._fh6_scan_busy
            and not self._fh6_operation_busy
        )
        render = (
            status,
            detail,
            path_text,
            game_language_text,
            display_language_text,
            voice_language_text,
            view.action_label,
            action_visible,
            action_enabled,
        )
        if render == self._fh6_render_cache:
            return
        self._fh6_render_cache = render
        self._fh6_status.configure(text=status)
        self._fh6_detail.configure(text=detail)
        self._fh6_path.configure(text=path_text)
        self._fh6_game_language.configure(text=game_language_text)
        self._fh6_display_language.configure(text=display_language_text)
        self._fh6_voice_language.configure(text=voice_language_text)
        if action_visible:
            self._fh6_action.configure(
                text=view.action_label,
                state="normal" if action_enabled else "disabled",
            )
            if not self._fh6_action_packed:
                self._fh6_action.pack(side="left", padx=(0, T.PAD_SM))
                self._fh6_action_packed = True
        elif self._fh6_action_packed:
            self._fh6_action.pack_forget()
            self._fh6_action_packed = False

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
                "Game updates or file verification may restore the original files."
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
                "FH6 game language could not be verified as English. Continue only if the game is configured for English."
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
        self._fh6_render_cache = None
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
        self._fh6_game_running = False
        self._fh6_error = error
        self._fh6_render_cache = None
        self._render_fh6_status()
        self.app.toast(
            t("FH6 language change failed") if error else t("FH6 language files updated")
        )

    # MARK: FH6 DualSense controller icons --------------------------------

    def _icon_saved_path(self, platform: str | None = None) -> str:
        platform = platform or normalize_forza_platform(
            self.settings.preferred_forza_platform
        )
        return str(
            self.settings.fh6_install_path
            if platform == STEAM_PLATFORM
            else self.settings.fh6_xbox_install_path
        )

    def _build_controller_icon_card(self):
        card = W.Card(self._scroll)
        card.pack(fill="x", pady=(0, T.PAD_MD))
        W.H2(card, t("FH6 DualSense button icons")).pack(
            anchor="w", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_XS)
        )
        W.Hint(
            card,
            t(
                "Windows Steam and Xbox App editions. Original files are backed up before the explicit install."
            ),
            wrap=self.app.px(640),
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        W.GhostButton(
            card,
            text=t("MOD by {author} - open Nexus Mods").format(author=MOD_AUTHOR),
            command=lambda: self.app._open_url(MOD_URL),
            anchor="w",
        ).pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))
        self._icon_status = W.Body(card, t("Scanning for FH6"))
        self._icon_status.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._icon_detail = W.Hint(card, "", wrap=self.app.px(640))
        self._icon_detail.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_XS))
        self._icon_path = W.Hint(card, t("Install folder: not found"), wrap=self.app.px(640))
        self._icon_path.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_SM))

        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(fill="x", padx=T.PAD_MD, pady=(0, T.PAD_MD))
        self._icon_install_action = W.PrimaryButton(
            actions,
            t("Install DualSense icons"),
            lambda: self._request_icon_action("install"),
            width=180,
        )
        self._icon_install_action.pack(side="left", padx=(0, T.PAD_SM))
        self._icon_restore_action = W.SecondaryButton(
            actions,
            t("Restore original icons"),
            lambda: self._request_icon_action("restore"),
            width=180,
        )
        self._icon_restore_action.pack(side="left", padx=(0, T.PAD_SM))
        W.SecondaryButton(
            actions,
            t("Rescan"),
            lambda: self._start_icon_scan(rediscover=True),
            width=90,
        ).pack(side="left", padx=(0, T.PAD_SM))
        W.GhostButton(
            actions,
            t("Choose folder"),
            self._choose_icon_folder,
            width=110,
        ).pack(side="left")

    def _start_icon_scan(
        self,
        *,
        rediscover: bool,
        manual_path: str = "",
        silent: bool = False,
    ):
        manual_path = str(manual_path).strip()
        if self._icon_operation_busy or self.app._tearing_down:
            return
        # Manual selection must win over a page-opening background discovery.
        if self._icon_scan_busy and not manual_path:
            return
        platform = normalize_forza_platform(self.settings.preferred_forza_platform)
        cached_path = self._icon_saved_path(platform)
        current_root = self._icon_inspection.root
        self._icon_scan_serial += 1
        serial = self._icon_scan_serial
        self._icon_active_serial = serial
        self._icon_scan_busy = True
        self._icon_silent_scan = bool(silent and current_root is None)
        self._icon_error = ""
        self._icon_last_scan = time.monotonic()
        self._render_icon_status()

        def worker():
            error = ""
            try:
                if manual_path:
                    root = validate_controller_icon_root(manual_path)
                elif current_root is not None and not rediscover and platform == self._icon_platform:
                    root = validate_controller_icon_root(current_root)
                elif platform == STEAM_PLATFORM:
                    required = tuple(relative.parent for relative in CONTROLLER_ICON_TARGETS)
                    install = discover_forza_install(
                        "fh6",
                        cached_path,
                        required_directories=required,
                    )
                    root = install.root if install is not None else None
                else:
                    required = tuple(relative.parent for relative in CONTROLLER_ICON_TARGETS)
                    install = discover_xbox_forza_install(
                        "fh6",
                        cached_path,
                        required_directories=required,
                    )
                    root = install.root if install is not None else None
                inspection = inspect_controller_icons(root)
                running = is_forza_game_running("fh6") if root is not None else False
            except Exception as exc:
                inspection = inspect_controller_icons(None)
                running = False
                error = str(exc) or type(exc).__name__
                log.exception("FH6 controller-icon status scan failed")
            try:
                self.app.root.after(
                    0,
                    lambda: self._apply_icon_scan(
                        serial,
                        platform,
                        cached_path,
                        bool(manual_path),
                        inspection,
                        running,
                        error,
                    ),
                )
            except Exception:
                pass

        threading.Thread(
            target=worker,
            name="fhds-fh6-controller-icons-scan",
            daemon=True,
        ).start()

    def _apply_icon_scan(
        self,
        serial: int,
        platform: str,
        context_hint: str,
        manual: bool,
        inspection: ControllerIconInspection,
        running: bool,
        error: str,
    ):
        if serial != self._icon_active_serial:
            return
        current_platform = normalize_forza_platform(self.settings.preferred_forza_platform)
        current_hint = self._icon_saved_path(current_platform)
        if not manual and (platform != current_platform or context_hint != current_hint):
            self._icon_platform = current_platform
            self._icon_path_hint = current_hint
            self._invalidate_icons()
            if self._visible:
                self._start_icon_scan(rediscover=True)
            return
        self._icon_active_serial = None
        self._icon_scan_busy = False
        self._icon_silent_scan = False
        self._icon_platform = platform
        self._icon_inspection = inspection
        self._icon_game_running = running
        self._icon_error = error
        if manual and inspection.root is None:
            self.app.toast(t("FH6 installation not found"))
        if inspection.root is not None:
            field = "fh6_install_path" if platform == STEAM_PLATFORM else "fh6_xbox_install_path"
            resolved = str(inspection.root)
            self._icon_path_hint = resolved
            if getattr(self.settings, field) != resolved:
                setattr(self.settings, field, resolved)
                preferences.save(self.settings)
        self._icon_render_cache = None
        self._render_icon_status()

    def _render_icon_status(self):
        if self._icon_status is None:
            return
        state = self._icon_inspection.state
        if self._icon_operation_busy:
            status = t("Changing FH6 controller icon files")
            detail = t("Please wait. Do not start FH6 until the operation finishes.")
        elif self._icon_scan_busy and not self._icon_silent_scan:
            status = t("Scanning for FH6")
            detail = ""
        elif self._icon_game_running:
            status = t("Close FH6 first")
            detail = t("Controller icon files cannot be changed while the game is running.")
        elif state is ControllerIconState.NOT_FOUND:
            status = t("FH6 installation not found")
            detail = (
                t(
                    "Automatic detection failed. Rescan or choose the Xbox App FH6 install folder."
                )
                if self._icon_platform != STEAM_PLATFORM
                else t("Run FH6 at least once, then rescan or choose its install folder.")
            )
        elif state is ControllerIconState.INSTALLED:
            status = t("DualSense button icons are installed")
            detail = t("The verified original files can be restored at any time.")
        elif state is ControllerIconState.PARTIAL:
            status = t("Controller icon files need repair")
            detail = (
                t("Restore the verified original files before installing again.")
                if self._icon_inspection.has_backup
                else t("Verify the game files before installing the MOD again.")
            )
        elif state is ControllerIconState.ASSET_ERROR:
            status = t("Bundled controller-icon MOD is unavailable")
            detail = self._icon_inspection.detail
        else:
            status = t("Original controller icons are active")
            detail = t("Ready to install the DualSense button icons.")
        if self._icon_error:
            detail = self._icon_error
        path_text = (
            t("Install folder: {path}").format(path=self._icon_inspection.root)
            if self._icon_inspection.root is not None
            else t("Install folder: not found")
        )
        busy = self._icon_scan_busy or self._icon_operation_busy or self._icon_game_running
        can_install = (
            not busy
            and state in (ControllerIconState.READY, ControllerIconState.PARTIAL)
            and (state is not ControllerIconState.PARTIAL or self._icon_inspection.has_backup)
        )
        can_restore = (
            not busy
            and self._icon_inspection.has_backup
            and state in (ControllerIconState.INSTALLED, ControllerIconState.PARTIAL)
        )
        render = (status, detail, path_text, can_install, can_restore)
        if render == self._icon_render_cache:
            return
        self._icon_render_cache = render
        self._icon_status.configure(text=status)
        self._icon_detail.configure(text=detail)
        self._icon_path.configure(text=path_text)
        self._icon_install_action.configure(state="normal" if can_install else "disabled")
        self._icon_restore_action.configure(state="normal" if can_restore else "disabled")

    def _choose_icon_folder(self):
        selected = filedialog.askdirectory(
            parent=self.app.root,
            title=t("Choose the Forza Horizon 6 install folder"),
            mustexist=True,
        )
        if selected:
            self._start_icon_scan(rediscover=False, manual_path=selected)

    def _request_icon_action(self, action: str):
        if self._icon_inspection.root is None or self._icon_operation_busy:
            return
        install = action == "install"
        ConfirmationDialog(
            self.app.root,
            heading=(
                t("Install DualSense button icons?")
                if install
                else t("Restore original controller icons?")
            ),
            message=(
                t(
                    "FHDS will back up both original icon archives, then install the credited MOD. Close FH6 first."
                )
                if install
                else t("FHDS will restore both verified original icon archives. Close FH6 first.")
            ),
            confirm_label=(
                t("Install DualSense icons")
                if install
                else t("Restore original icons")
            ),
            on_confirm=lambda: self._run_icon_action(action),
        )

    def _run_icon_action(self, action: str):
        root = self._icon_inspection.root
        if root is None or self._icon_operation_busy:
            return
        self._icon_operation_busy = True
        self._icon_error = ""
        self._icon_render_cache = None
        self._render_icon_status()

        def worker():
            try:
                if action == "install":
                    inspection = install_controller_icons(root)
                elif action == "restore":
                    inspection = restore_controller_icons(root)
                else:
                    raise ValueError(f"Unknown controller-icon action: {action}")
                error = ""
            except Exception as exc:
                inspection = inspect_controller_icons(root)
                error = str(exc) or type(exc).__name__
                log.exception("FH6 controller-icon action failed")
            try:
                self.app.root.after(0, lambda: self._finish_icon_action(inspection, error))
            except Exception:
                pass

        threading.Thread(
            target=worker,
            name="fhds-fh6-controller-icons-action",
            daemon=True,
        ).start()

    def _finish_icon_action(self, inspection: ControllerIconInspection, error: str):
        self._icon_operation_busy = False
        self._icon_inspection = inspection
        self._icon_game_running = False
        self._icon_error = error
        self._icon_render_cache = None
        self._render_icon_status()
        self.app.toast(
            t("FH6 controller icon change failed")
            if error
            else t("FH6 controller icons updated")
        )
