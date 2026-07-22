"""FH6-only language and DualSense icon utilities for the Textual UI."""
from __future__ import annotations

import asyncio
import logging
import time

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Input, Label

from lang import t
from modules.config import preferences
from modules.forzahorizon.controller_icons import (
    MOD_AUTHOR,
    MOD_URL,
    TARGETS as CONTROLLER_ICON_TARGETS,
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

log = logging.getLogger("fhds.tui.fh6_utilities")


class FH6UtilitiesTab(VerticalScroll):
    DEFAULT_CSS = """
    FH6UtilitiesTab { width: 1fr; height: 1fr; padding: 1 2; }
    FH6UtilitiesTab Label.section {
        width: 1fr; height: auto; padding: 1 1 0 1;
        color: $accent; text-style: bold;
    }
    FH6UtilitiesTab Label.hint { width: 1fr; height: auto; color: $text-muted; padding: 0 1; }
    FH6UtilitiesTab #fh6-path-row, FH6UtilitiesTab #icon-path-row {
        height: 3; padding: 0 1;
    }
    FH6UtilitiesTab #fh6-path-row Input, FH6UtilitiesTab #icon-path-row Input { width: 1fr; }
    FH6UtilitiesTab #fh6-buttons, FH6UtilitiesTab #icon-buttons { height: 3; padding: 0 1; }
    FH6UtilitiesTab #fh6-buttons Button, FH6UtilitiesTab #icon-buttons Button { margin-right: 2; }
    """

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._visible = False
        self._has_shown = False
        self._fh6_install: FH6Install | None = None
        self._fh6_inspection = inspect_language_state(None)
        self._fh6_game_running = False
        self._fh6_busy = False
        self._fh6_silent = False
        self._fh6_pending_action = ""
        self._fh6_confirm_deadline = 0.0
        self._fh6_view: LanguageView | None = None
        self._fh6_platform = normalize_forza_platform(
            self.settings.preferred_forza_platform
        )
        self._fh6_path_hint = self._language_saved_path(self._fh6_platform)
        self._icon_inspection = inspect_controller_icons(None)
        self._icon_platform = normalize_forza_platform(
            self.settings.preferred_forza_platform
        )
        self._icon_path_hint = self._icon_saved_path(self._icon_platform)
        self._icon_game_running = False
        self._icon_busy = False
        self._icon_silent = False
        self._icon_pending_action = ""
        self._icon_confirm_deadline = 0.0
        self._runtime_busy = False

    def compose(self) -> ComposeResult:
        yield Label(t("FH6 Chinese text + English voice"), classes="section")
        yield Label(
            t(
                "Windows Steam and Xbox App editions. Install folders are detected automatically; manual selection remains available."
            ),
            classes="hint",
        )
        yield Label(t("Scanning for FH6"), id="fh6-status", markup=False)
        yield Label("", id="fh6-detail", classes="hint", markup=False)
        yield Label(
            t("Install folder: not found"),
            id="fh6-install",
            classes="hint",
            markup=False,
        )
        yield Label(
            t("Current FH6 game language: {language}").format(language=t("Unknown")),
            id="fh6-game-language",
            classes="hint",
            markup=False,
        )
        yield Label(
            t("Actual display language: {language}").format(language=t("Unknown")),
            id="fh6-display-language",
            classes="hint",
            markup=False,
        )
        yield Label(
            t("Voice language: {language}").format(language=t("Unknown")),
            id="fh6-voice-language",
            classes="hint",
            markup=False,
        )
        with Horizontal(id="fh6-path-row"):
            yield Input(
                value=self._language_saved_path(),
                placeholder=t("FH6 install folder"),
                id="fh6-path",
            )
            yield Button(t("Use folder"), id="fh6-path-apply")
        with Horizontal(id="fh6-buttons"):
            yield Button(t("Rescan"), id="fh6-rescan")
            yield Button(
                t("Enable Chinese text + English voice"),
                id="fh6-action",
                variant="primary",
                disabled=True,
            )

        yield Label(t("FH6 DualSense button icons"), classes="section")
        yield Label(
            t(
                "Windows Steam and Xbox App editions. Original files are backed up before the explicit install."
            ),
            classes="hint",
        )
        yield Button(
            t("MOD by {author} - open Nexus Mods").format(author=MOD_AUTHOR),
            id="icon-credit",
        )
        yield Label(t("Scanning for FH6"), id="icon-status", markup=False)
        yield Label("", id="icon-detail", classes="hint", markup=False)
        yield Label(
            t("Install folder: not found"),
            id="icon-install",
            classes="hint",
            markup=False,
        )
        with Horizontal(id="icon-path-row"):
            yield Input(
                value=self._icon_saved_path(),
                placeholder=t("FH6 install folder"),
                id="icon-path",
            )
            yield Button(t("Use folder"), id="icon-path-apply")
        with Horizontal(id="icon-buttons"):
            yield Button(t("Rescan"), id="icon-rescan")
            yield Button(
                t("Install DualSense icons"),
                id="icon-install-action",
                variant="primary",
                disabled=True,
            )
            yield Button(
                t("Restore original icons"),
                id="icon-restore-action",
                disabled=True,
            )

    def on_mount(self) -> None:
        self._retry_timer = self.set_interval(30.0, self._schedule_missing_refresh)
        self._runtime_timer = self.set_interval(2.0, self._schedule_runtime_refresh)

    async def on_show(self) -> None:
        self._visible = True
        language_changed, icon_changed = self._sync_context()
        first_show = not self._has_shown
        self._has_shown = True
        if first_show or language_changed or self._fh6_install is None:
            await self._scan_fh6(rediscover=True, silent=not first_show)
        if first_show or icon_changed or self._icon_inspection.root is None:
            await self._scan_icons(rediscover=True, silent=not first_show)

    def on_hide(self) -> None:
        self._visible = False

    def _sync_context(self) -> tuple[bool, bool]:
        platform = normalize_forza_platform(self.settings.preferred_forza_platform)
        language_hint = self._language_saved_path(platform)
        language_changed = (
            platform != self._fh6_platform or language_hint != self._fh6_path_hint
        )
        if language_changed:
            self._fh6_platform = platform
            self._fh6_path_hint = language_hint
            self._fh6_install = None
            self._fh6_inspection = inspect_language_state(None)
            self._fh6_game_running = False
            if self.is_mounted:
                self.query_one("#fh6-path", Input).value = language_hint

        icon_hint = self._icon_saved_path(platform)
        icon_changed = platform != self._icon_platform or icon_hint != self._icon_path_hint
        if icon_changed:
            self._icon_platform = platform
            self._icon_path_hint = icon_hint
            self._icon_inspection = inspect_controller_icons(None)
            self._icon_game_running = False
            if self.is_mounted:
                self.query_one("#icon-path", Input).value = icon_hint
        return language_changed, icon_changed

    def _schedule_missing_refresh(self) -> None:
        if not self._visible:
            return
        language_changed, icon_changed = self._sync_context()
        if not self._fh6_busy and (language_changed or self._fh6_install is None):
            self.run_worker(
                self._scan_fh6(rediscover=True, silent=not language_changed),
                group="fh6-utilities-language",
                exclusive=True,
            )
        if not self._icon_busy and (icon_changed or self._icon_inspection.root is None):
            self.run_worker(
                self._scan_icons(rediscover=True, silent=not icon_changed),
                group="fh6-utilities-icons",
                exclusive=True,
            )

    def _schedule_runtime_refresh(self) -> None:
        if (
            not self._visible
            or self._runtime_busy
            or (self._fh6_install is None and self._icon_inspection.root is None)
        ):
            return
        self.run_worker(
            self._refresh_runtime(),
            group="fh6-utilities-runtime",
            exclusive=True,
        )

    async def _refresh_runtime(self) -> None:
        self._runtime_busy = True
        try:
            running = (
                await asyncio.to_thread(is_fh6_running, self._fh6_install)
                if self._fh6_install is not None
                else await asyncio.to_thread(is_forza_game_running, "fh6")
            )
            language_changed = running != self._fh6_game_running
            icon_changed = running != self._icon_game_running
            self._fh6_game_running = running
            self._icon_game_running = running
            if language_changed:
                self._render_fh6_status()
            if icon_changed:
                self._render_icon_status()
        finally:
            self._runtime_busy = False

    def _language_saved_path(self, platform: str | None = None) -> str:
        platform = platform or normalize_forza_platform(
            self.settings.preferred_forza_platform
        )
        return str(
            self.settings.fh6_install_path
            if platform == STEAM_PLATFORM
            else self.settings.fh6_xbox_install_path
        )

    def _icon_saved_path(self, platform: str | None = None) -> str:
        platform = platform or normalize_forza_platform(
            self.settings.preferred_forza_platform
        )
        return str(
            self.settings.fh6_install_path
            if platform == STEAM_PLATFORM
            else self.settings.fh6_xbox_install_path
        )

    async def _scan_fh6(
        self,
        *,
        rediscover: bool,
        manual_path: str = "",
        silent: bool = False,
    ) -> None:
        if self._fh6_busy:
            return
        self._fh6_busy = True
        self._fh6_silent = bool(silent and self._fh6_install is None)
        self._fh6_pending_action = ""
        platform = normalize_forza_platform(self.settings.preferred_forza_platform)
        context_hint = self._language_saved_path(platform)
        self._render_fh6_status()
        try:
            if manual_path:
                install = await asyncio.to_thread(
                    validate_game_root,
                    manual_path,
                    source=(
                        "Manual Steam"
                        if platform == STEAM_PLATFORM
                        else "Manual Xbox App"
                    ),
                )
            elif (
                self._fh6_install is not None
                and not rediscover
                and platform == self._fh6_platform
            ):
                install = self._fh6_install
            elif platform == STEAM_PLATFORM:
                install = await asyncio.to_thread(
                    discover_fh6_install,
                    context_hint,
                )
            else:
                install = await asyncio.to_thread(
                    discover_xbox_fh6_install,
                    context_hint,
                )
            inspection = await asyncio.to_thread(inspect_language_state, install)
            running = (
                await asyncio.to_thread(is_fh6_running, install)
                if install is not None
                else False
            )
            current_platform = normalize_forza_platform(
                self.settings.preferred_forza_platform
            )
            current_hint = self._language_saved_path(current_platform)
            if platform != current_platform or (
                not manual_path and context_hint != current_hint
            ):
                self._sync_context()
                return
            self._fh6_platform = platform
            self._fh6_install = install
            self._fh6_inspection = inspection
            self._fh6_game_running = running
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
                self.query_one("#fh6-path", Input).value = resolved
        except Exception as exc:
            log.exception("FH6 language status scan failed")
            self.app.notify(
                str(exc) or type(exc).__name__,
                title=t("FH6 language change failed"),
                severity="error",
            )
        finally:
            self._fh6_busy = False
            self._fh6_silent = False
            self._render_fh6_status()

    def _render_fh6_status(self) -> None:
        if not self.is_mounted:
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
        if self._fh6_busy and self._fh6_pending_action:
            status = t("Changing FH6 language files")
        elif self._fh6_busy and not self._fh6_silent:
            status = t("Scanning for FH6")
        self.query_one("#fh6-status", Label).update(status)
        detail = view.detail
        if self._fh6_pending_action and time.monotonic() <= self._fh6_confirm_deadline:
            detail = t("Press the action button again to confirm. No files change on the first press.")
        self.query_one("#fh6-detail", Label).update(detail)
        install = self._fh6_inspection.install
        self.query_one("#fh6-install", Label).update(
            t("Install folder: {path}").format(path=install.root)
            if install is not None
            else t("Install folder: not found")
        )
        self.query_one("#fh6-game-language", Label).update(
            t("Current FH6 game language: {language}").format(
                language=summary.game_language
            )
        )
        self.query_one("#fh6-display-language", Label).update(
            t("Actual display language: {language}").format(
                language=summary.display_language
            )
        )
        self.query_one("#fh6-voice-language", Label).update(
            t("Voice language: {language}").format(
                language=summary.voice_language
            )
        )
        action_button = self.query_one("#fh6-action", Button)
        action_button.label = (
            t("Press again to confirm") if self._fh6_pending_action else view.action_label
        ) or t("No safe action available")
        action_button.disabled = not view.action_enabled or self._fh6_busy

    async def _run_fh6_action(self, action: str, *, allow_unknown: bool) -> None:
        install = self._fh6_install
        if install is None or self._fh6_busy:
            return
        self._fh6_busy = True
        self._render_fh6_status()
        try:
            if action == "enable":
                inspection = await asyncio.to_thread(
                    enable_chinese_text_english_voice,
                    install,
                    allow_unknown_steam_language=allow_unknown,
                )
            elif action == "restore":
                inspection = await asyncio.to_thread(restore_native_language, install)
            else:
                inspection = await asyncio.to_thread(repair_native_language, install)
            self._fh6_inspection = inspection
            self._fh6_game_running = False
            self.app.notify(t("FH6 language files updated"))
        except Exception as exc:
            self._fh6_inspection = await asyncio.to_thread(inspect_language_state, install)
            self.app.notify(
                str(exc) or type(exc).__name__,
                title=t("FH6 language change failed"),
                severity="error",
            )
        finally:
            self._fh6_busy = False
            self._fh6_pending_action = ""
            self._render_fh6_status()

    async def _scan_icons(
        self,
        *,
        rediscover: bool,
        manual_path: str = "",
        silent: bool = False,
    ) -> None:
        if self._icon_busy:
            return
        self._icon_busy = True
        self._icon_silent = bool(silent and self._icon_inspection.root is None)
        self._icon_pending_action = ""
        self._render_icon_status()
        platform = normalize_forza_platform(self.settings.preferred_forza_platform)
        cached_path = self._icon_saved_path(platform)
        try:
            if manual_path:
                root = await asyncio.to_thread(validate_controller_icon_root, manual_path)
            elif (
                self._icon_inspection.root is not None
                and not rediscover
                and platform == self._icon_platform
            ):
                root = await asyncio.to_thread(
                    validate_controller_icon_root,
                    self._icon_inspection.root,
                )
            elif platform == STEAM_PLATFORM:
                install = await asyncio.to_thread(
                    discover_forza_install,
                    "fh6",
                    cached_path,
                    required_directories=tuple(
                        relative.parent for relative in CONTROLLER_ICON_TARGETS
                    ),
                )
                root = install.root if install is not None else None
            else:
                install = await asyncio.to_thread(
                    discover_xbox_forza_install,
                    "fh6",
                    cached_path,
                    required_directories=tuple(
                        relative.parent for relative in CONTROLLER_ICON_TARGETS
                    ),
                )
                root = install.root if install is not None else None
            inspection = await asyncio.to_thread(inspect_controller_icons, root)
            running = (
                await asyncio.to_thread(is_forza_game_running, "fh6")
                if root is not None
                else False
            )
            self._icon_platform = platform
            self._icon_inspection = inspection
            self._icon_game_running = running
            if inspection.root is not None:
                field = "fh6_install_path" if platform == STEAM_PLATFORM else "fh6_xbox_install_path"
                resolved = str(inspection.root)
                self._icon_path_hint = resolved
                if getattr(self.settings, field) != resolved:
                    setattr(self.settings, field, resolved)
                    preferences.save(self.settings)
                self.query_one("#icon-path", Input).value = resolved
        except Exception as exc:
            log.exception("FH6 controller-icon status scan failed")
            self.app.notify(str(exc) or type(exc).__name__, severity="error")
        finally:
            self._icon_busy = False
            self._icon_silent = False
            self._render_icon_status()

    def _render_icon_status(self) -> None:
        if not self.is_mounted:
            return
        state = self._icon_inspection.state
        if self._icon_busy and self._icon_pending_action:
            status = t("Changing FH6 controller icon files")
            detail = t("Please wait. Do not start FH6 until the operation finishes.")
        elif self._icon_busy and not self._icon_silent:
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
        if self._icon_pending_action and time.monotonic() <= self._icon_confirm_deadline:
            detail = t("Press the action button again to confirm. No files change on the first press.")
        self.query_one("#icon-status", Label).update(status)
        self.query_one("#icon-detail", Label).update(detail)
        self.query_one("#icon-install", Label).update(
            t("Install folder: {path}").format(path=self._icon_inspection.root)
            if self._icon_inspection.root is not None
            else t("Install folder: not found")
        )
        busy = self._icon_busy or self._icon_game_running
        install_button = self.query_one("#icon-install-action", Button)
        restore_button = self.query_one("#icon-restore-action", Button)
        install_button.label = (
            t("Press again to confirm")
            if self._icon_pending_action == "install"
            else t("Install DualSense icons")
        )
        restore_button.label = (
            t("Press again to confirm")
            if self._icon_pending_action == "restore"
            else t("Restore original icons")
        )
        install_button.disabled = (
            busy
            or state not in (ControllerIconState.READY, ControllerIconState.PARTIAL)
            or (state is ControllerIconState.PARTIAL and not self._icon_inspection.has_backup)
        )
        restore_button.disabled = (
            busy
            or not self._icon_inspection.has_backup
            or state not in (ControllerIconState.INSTALLED, ControllerIconState.PARTIAL)
        )

    async def _run_icon_action(self, action: str) -> None:
        root = self._icon_inspection.root
        if root is None or self._icon_busy:
            return
        self._icon_busy = True
        self._render_icon_status()
        try:
            operation = install_controller_icons if action == "install" else restore_controller_icons
            self._icon_inspection = await asyncio.to_thread(operation, root)
            self._icon_game_running = False
            self.app.notify(t("FH6 controller icons updated"))
        except Exception as exc:
            self._icon_inspection = await asyncio.to_thread(inspect_controller_icons, root)
            self.app.notify(
                str(exc) or type(exc).__name__,
                title=t("FH6 controller icon change failed"),
                severity="error",
            )
        finally:
            self._icon_busy = False
            self._icon_pending_action = ""
            self._render_icon_status()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fh6-rescan":
            await self._scan_fh6(rediscover=True)
        elif event.button.id == "fh6-path-apply":
            path = self.query_one("#fh6-path", Input).value.strip()
            await self._scan_fh6(rediscover=False, manual_path=path)
        elif event.button.id == "fh6-action":
            view = self._fh6_view
            if view is None or not view.action_enabled or not view.action:
                return
            now = time.monotonic()
            if self._fh6_pending_action != view.action or now > self._fh6_confirm_deadline:
                self._fh6_pending_action = view.action
                self._fh6_confirm_deadline = now + 10.0
                self._render_fh6_status()
                return
            await self._run_fh6_action(
                view.action,
                allow_unknown=view.unknown_language_warning,
            )
        elif event.button.id == "icon-credit":
            self.app._open_url(MOD_URL)
        elif event.button.id == "icon-rescan":
            await self._scan_icons(rediscover=True)
        elif event.button.id == "icon-path-apply":
            path = self.query_one("#icon-path", Input).value.strip()
            await self._scan_icons(rediscover=False, manual_path=path)
        elif event.button.id in {"icon-install-action", "icon-restore-action"}:
            action = "install" if event.button.id == "icon-install-action" else "restore"
            now = time.monotonic()
            if self._icon_pending_action != action or now > self._icon_confirm_deadline:
                self._icon_pending_action = action
                self._icon_confirm_deadline = now + 10.0
                self._render_icon_status()
                return
            await self._run_icon_action(action)
