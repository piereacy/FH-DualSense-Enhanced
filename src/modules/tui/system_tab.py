"""System tab: controller selection and ZUV-independent built-in updates."""
import asyncio
import logging
import threading
import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, ProgressBar, RadioButton, RadioSet, Switch

from lang import t
from modules.config import preferences
from modules.dualsense.main import _enumerate_dualsenses, _is_bluetooth, identify_pulse
from modules.forzahorizon.fh6_language import (
    FH6Install,
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

from .settings_tab import SYSTEM_SECTIONS, SettingsTab

log = logging.getLogger("fhds")

class SystemTab(SettingsTab):
    SECTIONS = SYSTEM_SECTIONS
    SHOW_RESET = False
    SHOW_EXPERIMENTAL = False

    DEFAULT_CSS = """
    SystemTab #controller-buttons { height: 3; padding: 0 1; }
    SystemTab #controller-buttons Button { margin-right: 2; }
    SystemTab #controller-radio { height: auto; padding: 0 1 1 1; }
    SystemTab #controller-hid-section { height: auto; }
    SystemTab #controller-hid-section > Label { padding: 0 1; }
    SystemTab #fh6-path-row { height: 3; padding: 0 1; }
    SystemTab #fh6-path-row Input { width: 1fr; }
    SystemTab #fh6-buttons { height: 3; padding: 0 1; }
    SystemTab #fh6-buttons Button { margin-right: 2; }
    """

    def __init__(self, settings):
        super().__init__(settings)
        self._fh6_install: FH6Install | None = None
        self._fh6_inspection = inspect_language_state(None)
        self._fh6_game_running = False
        self._fh6_busy = False
        self._fh6_pending_action = ""
        self._fh6_confirm_deadline = 0.0
        self._fh6_view: LanguageView | None = None

    def compose(self) -> ComposeResult:
        updater_supported = self.app._update_service.supported
        yield Label(t("Controller"), classes="section")
        # Skip blocking HID enumeration here; on_show() scans off-thread.
        self._devices = []
        # Controller picking only applies in HID mode; hidden while DSX owns the device.
        with Vertical(id="controller-hid-section"):
            yield Label(t("Lock to controller"))
            yield RadioSet(*self._build_controller_buttons(), id="controller-radio")
            with Horizontal(id="controller-buttons"):
                yield Button(t("Rescan"), id="controller-rescan")
        yield Label(
            t("DSX is active - controller managed by DSX. "
              "Disable DSX to select a controller here."),
            id="dsx-controller-note",
            classes="hint",
        )

        yield Label(t("Updates"), classes="section")
        with Horizontal(classes="row"):
            yield Switch(
                value=self.settings.check_for_updates,
                id="check_for_updates",
                disabled=not updater_supported,
            )
            yield Label(t("Automatically check for updates"))
        with Horizontal(classes="row"):
            yield Switch(
                value=self.settings.auto_download_updates,
                id="auto_download_updates",
                disabled=not updater_supported,
            )
            yield Label(t("Download updates in the background"))
        yield Label(t("Update status: idle"), id="update-status", classes="hint")
        yield ProgressBar(total=100, show_eta=False, id="update-progress")
        with Horizontal(id="update-buttons"):
            yield Button(
                t("Check now"),
                id="update-check",
                disabled=not updater_supported,
            )
            yield Button(t("Download update"), id="update-action", disabled=True)

        yield Label(t("FH6 Chinese text + English voice"), classes="section")
        yield Label(
            t(
                "Windows Steam only. Detection is automatic, but files change only after you press a button and confirm."
            ),
            classes="hint",
        )
        yield Label(t("Scanning for FH6"), id="fh6-status")
        yield Label("", id="fh6-detail", classes="hint")
        yield Label(t("Install folder: not found"), id="fh6-install", classes="hint")
        yield Label(t("Steam language: unknown"), id="fh6-steam-language", classes="hint")
        with Horizontal(id="fh6-path-row"):
            yield Input(
                value=self.settings.fh6_install_path,
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

        yield from super().compose()

    def on_mount(self) -> None:
        self._sync_controller_visibility()
        self._update_timer = self.set_interval(0.5, self._refresh_update_status)
        self._fh6_timer = self.set_interval(5.0, self._schedule_fh6_refresh)
        self.run_worker(self._scan_fh6(rediscover=True), group="fh6-scan", exclusive=True)

    def _schedule_fh6_refresh(self) -> None:
        if not self._fh6_busy:
            self.run_worker(
                self._scan_fh6(rediscover=False),
                group="fh6-scan",
                exclusive=True,
            )

    def _refresh_update_status(self) -> None:
        snapshot = self.app._update_service.snapshot()
        self.query_one("#update-status", Label).update(localized_status(snapshot, t))
        self.query_one("#update-progress", ProgressBar).update(progress=snapshot.progress * 100)
        action = self.query_one("#update-action", Button)
        if snapshot.phase is UpdatePhase.AVAILABLE:
            action.label = t("Download update")
            action.disabled = False
        elif snapshot.phase is UpdatePhase.READY:
            action.label = t("Restart and install")
            action.disabled = False
        else:
            action.disabled = True

    def _sync_controller_visibility(self) -> None:
        """Controller picking is meaningless while DSX owns the device, so swap the
        HID section for an explanatory note when DSX is on."""
        from textual.css.query import NoMatches
        try:
            hid = self.query_one("#controller-hid-section")
            note = self.query_one("#dsx-controller-note")
        except NoMatches:
            return
        hid.display = not self.settings.use_dsx
        note.display = bool(self.settings.use_dsx)

    async def on_show(self) -> None:
        # Re-enumerating is pointless (and the radio is hidden) under DSX.
        if not self.settings.use_dsx:
            await self._rerender_controller()
        await self._scan_fh6(rediscover=self._fh6_install is None)

    async def _scan_fh6(self, *, rediscover: bool, manual_path: str = "") -> None:
        if self._fh6_busy:
            return
        self._fh6_busy = True
        self._fh6_pending_action = ""
        self._render_fh6_status()
        try:
            if manual_path:
                install = await asyncio.to_thread(
                    validate_game_root,
                    manual_path,
                    source="Manual",
                )
            elif self._fh6_install is not None and not rediscover:
                install = self._fh6_install
            else:
                install = await asyncio.to_thread(
                    discover_fh6_install,
                    self.settings.fh6_install_path,
                )
            inspection = await asyncio.to_thread(inspect_language_state, install)
            running = (
                await asyncio.to_thread(is_fh6_running, install)
                if install is not None
                else False
            )
            self._fh6_install = install
            self._fh6_inspection = inspection
            self._fh6_game_running = running
            if install is not None:
                resolved = str(install.root)
                if self.settings.fh6_install_path != resolved:
                    self.settings.fh6_install_path = resolved
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
            self._render_fh6_status()

    def _render_fh6_status(self) -> None:
        if not self.is_mounted:
            return
        view = language_view(
            self._fh6_inspection,
            game_running=self._fh6_game_running,
            translate=t,
        )
        self._fh6_view = view
        self.query_one("#fh6-status", Label).update(
            t("Changing FH6 language files")
            if self._fh6_busy and self._fh6_pending_action
            else t("Scanning for FH6") if self._fh6_busy else view.status
        )
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
        steam_language = (
            install.steam_language if install and install.steam_language else t("unknown")
        )
        self.query_one("#fh6-steam-language", Label).update(
            t("Steam language: {language}").format(language=steam_language)
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

    def _attached_serial(self) -> str:
        ds = getattr(self.app, "_ds", None)
        if ds is None or not ds.connected:
            return ""
        return getattr(ds, "dev_serial", "") or ""

    def _build_controller_buttons(self) -> list[RadioButton]:
        attached_serial = self._attached_serial()
        current_lock = self.settings.controller_lock_serial
        buttons: list[RadioButton] = []
        buttons.append(RadioButton(
            t("Auto (first found)"),
            id="ctrl-auto",
            value=(current_lock == ""),
        ))
        for d in self._devices:
            sn = d.get("serial_number") or ""
            transport = "BT" if _is_bluetooth(d) else "USB"
            if sn:
                attached_now = t("attached now")
                marker = f"  < {attached_now}" if sn == attached_serial else ""
                buttons.append(RadioButton(
                    f"\\[{transport}] {sn}{marker}",
                    id=f"ctrl-{sn}",
                    value=(sn == current_lock),
                ))
            else:
                no_serial = t("(no serial - not selectable)")
                buttons.append(RadioButton(
                    f"\\[{transport}] {no_serial}",
                    id=f"ctrl-noserial-{id(d)}",
                    disabled=True,
                ))
        return buttons

    def _selected_lock(self) -> str | None:
        radio = self.query_one("#controller-radio", RadioSet)
        button = radio.pressed_button
        if button is None or button.id is None:
            return None
        if button.id == "ctrl-auto":
            return ""
        if button.id.startswith("ctrl-noserial-"):
            return None
        return button.id[len("ctrl-"):]

    async def _rerender_controller(self) -> None:
        # Enumerate off-thread; blocking HID I/O would freeze the event loop.
        self._devices = await asyncio.to_thread(_enumerate_dualsenses)
        # await remove_children() before mount() to avoid a DuplicateIds collision.
        radio = self.query_one("#controller-radio", RadioSet)
        await radio.remove_children()
        for b in self._build_controller_buttons():
            await radio.mount(b)

    async def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id != "controller-radio":
            return
        # Force visual sync: clear stale value=True on all but the pressed button.
        pressed = event.pressed
        for rb in event.radio_set.query(RadioButton):
            if rb is not pressed and rb.value:
                rb.value = False
        new = self._selected_lock()
        if new is None:
            return
        if pressed is not None and pressed.id is not None and pressed.id.startswith("ctrl-") \
                and pressed.id != "ctrl-auto" and not pressed.id.startswith("ctrl-noserial-"):
            serial = pressed.id[len("ctrl-"):]
            info = next((d for d in self._devices
                         if (d.get("serial_number") or "") == serial), None)
            if info is not None:
                threading.Thread(target=identify_pulse, args=(info,),
                                 kwargs={"force": self.settings.startup_pulse_force},
                                 daemon=True).start()
        current = self.settings.controller_lock_serial
        if new != current:
            self.settings.controller_lock_serial = new
            preferences.save(self.settings)
            log.info("controller_lock_serial = %r", new)
        ds = getattr(self.app, "_ds", None)
        if ds is not None:
            ds.set_selection(new)
            if new and new != self._attached_serial():
                ds.force_reconnect()
        await self._rerender_controller()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "controller-rescan":
            await self._rerender_controller()
        elif event.button.id == "update-check":
            self.app._update_service.check_now()
        elif event.button.id == "update-action":
            snapshot = self.app._update_service.snapshot()
            if snapshot.phase is UpdatePhase.AVAILABLE:
                self.app._update_service.download()
            elif snapshot.phase is UpdatePhase.READY:
                try:
                    self.app._update_service.install_on_exit()
                except Exception as exc:
                    log.warning("Could not start update install: %s", exc)
                    return
                self.app.exit()
        elif event.button.id == "fh6-rescan":
            await self._scan_fh6(rediscover=True)
        elif event.button.id == "fh6-path-apply":
            path = self.query_one("#fh6-path", Input).value.strip()
            await self._scan_fh6(rediscover=False, manual_path=path)
        elif event.button.id == "fh6-action":
            view = self._fh6_view
            if view is None or not view.action_enabled or not view.action:
                return
            now = time.monotonic()
            if (
                self._fh6_pending_action != view.action
                or now > self._fh6_confirm_deadline
            ):
                self._fh6_pending_action = view.action
                self._fh6_confirm_deadline = now + 10.0
                self._render_fh6_status()
                return
            await self._run_fh6_action(
                view.action,
                allow_unknown=view.unknown_language_warning,
            )

    def on_switch_changed(self, event: Switch.Changed) -> None:
        super().on_switch_changed(event)
        if event.switch.id == "use_dsx":
            self._sync_controller_visibility()
            log.info("DSX %s", "enabled" if event.value else "disabled")
