"""System tab: controller selection and ZUV-independent built-in updates."""
import asyncio
import logging
import time

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Collapsible,
    Label,
    ProgressBar,
    RadioButton,
    RadioSet,
    Select,
    Switch,
)

from lang import t
from modules.config import preferences
from modules.dualsense.hidhide_installer import (
    find_hidhide_client,
    install_and_probe as install_hidhide,
    open_hidhide_client,
    probe_hidhide,
)
from modules.dualsense.main import (
    _is_bluetooth,
    _normalise_identity,
    _raw_dualsense_interfaces,
)
from modules.update import UpdatePhase
from modules.update.presentation import update_status_presentation
from modules.xinput.bridge import BridgeStatus, InputOwner
from modules.xinput.driver import InstallStatus
from modules.xinput.service import (
    STEAM_PLATFORM,
    XBOX_APP_PLATFORM,
    hidhide_presentation,
    normalize_forza_platform,
)

from .haptics_lab_tab import HapticsLabPanel
from .settings_tab import SYSTEM_SECTIONS, SettingsTab

log = logging.getLogger("fhds")

class SystemTab(SettingsTab):
    SWITCH_SECTIONS: tuple = ()
    SECTIONS: list = SYSTEM_SECTIONS
    EXPERIMENTAL_SECTIONS: tuple = ()
    SHOW_RESET = False
    SHOW_EXPERIMENTAL = False

    DEFAULT_CSS = """
    SystemTab #controller-buttons { height: 3; padding: 0 1; }
    SystemTab #controller-buttons Button { margin-right: 2; }
    SystemTab #xinput-buttons { height: 3; padding: 0 1; }
    SystemTab #update-manual-download { width: 1fr; margin: 0 1 1 1; }
    SystemTab #diagnostics-export { width: 1fr; margin: 1; }
    SystemTab #controller-radio { height: auto; padding: 0 1 1 1; }
    SystemTab #controller-hid-section { height: auto; }
    SystemTab #controller-hid-section > Label { padding: 0 1; }
    """

    def __init__(self, settings):
        super().__init__(settings)
        self._driver_confirm_deadline = 0.0
        self._hidhide_installed: bool | None = None
        self._hidhide_installing = False

    def compose(self) -> ComposeResult:
        updater_supported = self.app._update_service.supported
        yield Label(t("Forza platform"), classes="section")
        yield Select(
            (("Steam", STEAM_PLATFORM), ("Xbox App", XBOX_APP_PLATFORM)),
            value=normalize_forza_platform(self.settings.preferred_forza_platform),
            allow_blank=False,
            id="preferred_forza_platform",
        )
        yield Label("", id="xinput-status", markup=False)
        yield Label("", id="xinput-detail", classes="hint", markup=False)
        with Horizontal(id="xinput-buttons"):
            yield Button(t("Install ViGEmBus"), id="xinput-action", disabled=True)

        yield Label(t("Controller"), classes="section")
        # Skip blocking HID enumeration here; on_show() scans off-thread.
        self._devices = []
        # Controller picking only applies in HID mode; hidden while DSX owns the device.
        with Vertical(id="controller-hid-section"):
            yield Label(t("Lock to controller"))
            yield RadioSet(*self._build_controller_buttons(), id="controller-radio")
            with Horizontal(id="controller-buttons"):
                yield Button(t("Rescan"), id="controller-rescan")
                yield Button(t("Reconnect now"), id="controller-reconnect")
        yield Label(
            t("DSX is active - controller managed by DSX. "
              "Disable DSX to select a controller here."),
            id="dsx-controller-note",
            classes="hint",
        )

        yield Label(t("Physical controller isolation"), classes="section")
        yield Label(t("HidHide is required for Xbox App"), classes="hint")
        yield Label(
            t("Xbox App only. Install HidHide to download the signed driver and enable isolation; FHDS configures the current DualSense automatically. A Windows or game restart may be required."),
            classes="hint",
            markup=False,
        )
        yield Button(t("Install HidHide and enable isolation"), id="hidhide-install")
        yield Button(t("Open HidHide Configuration Client"), id="hidhide-open")
        yield Label("", id="hidhide-install-status", classes="hint", markup=False)
        yield Label("", id="hidhide-status", markup=False)
        yield Label("", id="hidhide-detail", classes="hint", markup=False)

        yield Label(t("Diagnostics"), classes="section")
        yield Label(
            t(
                "Create a ZIP with controller, input owner, telemetry, "
                "USB/Bluetooth haptics counters, and bounded runtime logs."
            ),
            classes="hint",
            markup=False,
        )
        yield Label(
            t(
                "Preferences and profiles are excluded. Review the ZIP before sharing because logs can contain local paths."
            ),
            classes="hint",
            markup=False,
        )
        yield Button(
            t("Create diagnostic package"),
            id="diagnostics-export",
        )
        yield Label("", id="diagnostics-status", classes="hint", markup=False)

        with Collapsible(
            title=t("Haptics Lab"),
            collapsed=True,
            id="haptics-lab-card",
        ):
            yield Label(
                t(
                    "Preview one bounded feedback layer at a time without game input forwarding."
                ),
                classes="hint",
                markup=False,
            )
            yield HapticsLabPanel()

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
        yield Label(
            t("Update status: idle"),
            id="update-status",
            classes="hint",
            markup=False,
        )
        yield ProgressBar(total=100, show_eta=False, id="update-progress")
        with Horizontal(id="update-buttons"):
            yield Button(
                t("Check now"),
                id="update-check",
                disabled=not updater_supported,
            )
            yield Button(t("Download update"), id="update-action", disabled=True)
            yield Button(t("View release"), id="update-release", disabled=True)
        yield Button(
            "",
            id="update-manual-download",
            disabled=True,
        )

        yield from super().compose()

    def on_mount(self) -> None:
        self._sync_controller_visibility()
        self._refresh_update_status()
        self._update_timer = self.set_interval(0.5, self._refresh_update_status)
        asyncio.create_task(self._probe_hidhide_status())

    async def _probe_hidhide_status(self) -> None:
        ready = await asyncio.to_thread(probe_hidhide)
        if not self.is_mounted or self._hidhide_installing or self._hidhide_installed:
            return
        self._hidhide_installed = ready
        if ready:
            self.query_one("#hidhide-install-status", Label).update(t("HidHide installed"))
        elif find_hidhide_client() is not None:
            self.query_one("#hidhide-install-status", Label).update(
                t("HidHide client found; driver not ready")
            )

    def _refresh_update_status(self) -> None:
        snapshot = self.app._update_service.snapshot()
        presentation = update_status_presentation(snapshot, t)
        self.query_one("#update-status", Label).update(presentation.status)
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
        self.query_one("#update-release", Button).disabled = snapshot.release is None
        manual_download = self.query_one("#update-manual-download", Button)
        manual_download.disabled = not bool(presentation.manual_download_url)
        manual_download.display = bool(presentation.manual_download_url)
        if presentation.manual_download_url:
            manual_download.label = t("Or download manually: {url}").format(
                url=presentation.manual_download_url
            )
        self._refresh_hidhide_status()
        self._refresh_xinput_status()

    def _refresh_hidhide_status(self) -> None:
        client_available = find_hidhide_client() is not None
        self.query_one("#hidhide-open", Button).disabled = not client_available
        self.query_one("#hidhide-install", Button).label = t(
            "Check HidHide and enable isolation" if client_available
            else "Install HidHide and enable isolation"
        )
        presentation = hidhide_presentation(
            self.settings,
            self.app._xinput_service.snapshot(),
            self.app._xinput_service.hidhide_snapshot(),
            t,
            controller_connected=bool(getattr(getattr(self.app, "_ds", None), "connected", False)),
        )
        self.query_one("#hidhide-status", Label).update(presentation.title)
        self.query_one("#hidhide-detail", Label).update(presentation.detail)

    def _refresh_xinput_status(self) -> None:
        status = self.query_one("#xinput-status", Label)
        detail = self.query_one("#xinput-detail", Label)
        action = self.query_one("#xinput-action", Button)
        snapshot = self.app._xinput_service.snapshot()
        if normalize_forza_platform(self.settings.preferred_forza_platform) == STEAM_PLATFORM:
            status.update(t("Steam Input mode"))
            detail.update(t("XInput bridge is off"))
            action.disabled = True
            return
        mapping = {
            BridgeStatus.DRIVER_MISSING: (
                t("ViGEmBus required"),
                t("Install the bundled driver to use Xbox App"),
            ),
            BridgeStatus.INSTALLING: (
                t("Installing ViGEmBus"),
                t("Complete the Windows installer"),
            ),
            BridgeStatus.RESTART_REQUIRED: (
                t("Windows restart required"),
                t("Restart Windows before using the Xbox App bridge"),
            ),
            BridgeStatus.WAITING_CONTROLLER: (
                t("Waiting for DualSense input"),
                t("The virtual Xbox 360 controller starts after input"),
            ),
            BridgeStatus.ACTIVE: (
                t("Xbox 360 controller active"),
                t("Forwarded {count} input reports").format(
                    count=snapshot.forwarded_reports
                ),
            ),
            BridgeStatus.STALE: (
                t("Controller input paused"),
                t("Neutral state sent to prevent stuck controls"),
            ),
            BridgeStatus.ERROR: (
                t("XInput bridge error"),
                snapshot.last_error,
            ),
            BridgeStatus.DISABLED: (
                t("XInput bridge unavailable"),
                snapshot.last_error,
            ),
        }
        if (
            snapshot.input_owner is InputOwner.KEYBOARD_MOUSE
            and snapshot.status
            in {BridgeStatus.WAITING_CONTROLLER, BridgeStatus.ACTIVE, BridgeStatus.STALE}
        ):
            title = t("Keyboard and mouse active")
            message = t(
                "Virtual Xbox input is neutral; move or press the DualSense to resume"
            )
        else:
            title, message = mapping[snapshot.status]
        status.update(title)
        detail.update(message)
        action.disabled = snapshot.status not in {
            BridgeStatus.DRIVER_MISSING,
            BridgeStatus.ERROR,
        }
        action.label = (
            t("Install ViGEmBus")
            if snapshot.status is BridgeStatus.DRIVER_MISSING
            else t("Retry XInput bridge")
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        select_id = event.select.id or ""
        if select_id != "preferred_forza_platform":
            return
        platform = normalize_forza_platform(event.value)
        if platform == self.settings.preferred_forza_platform:
            return
        self.settings.preferred_forza_platform = platform
        if platform == XBOX_APP_PLATFORM:
            self.settings.enable_hidhide = True
        preferences.save(self.settings)
        self.app._xinput_service.sync(getattr(self.app, "_ds", None))
        if platform == XBOX_APP_PLATFORM:
            self.app.notify(t("HidHide is required for Xbox App"))
        self._driver_confirm_deadline = 0.0
        self._refresh_xinput_status()

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

    def on_hide(self) -> None:
        self._stop_haptics_lab("page_hidden")

    def on_collapsible_collapsed(self, event: Collapsible.Collapsed) -> None:
        if event.collapsible.id == "haptics-lab-card":
            self._stop_haptics_lab("card_collapsed")

    def _stop_haptics_lab(self, reason: str) -> None:
        panels = self.query(HapticsLabPanel)
        for panel in panels:
            panel.stop(reason)

    def _attached_serial(self) -> str:
        ds = getattr(self.app, "_ds", None)
        if ds is None or not ds.connected:
            return ""
        return getattr(ds, "dev_serial", "") or ""

    def _build_controller_buttons(self) -> list[RadioButton]:
        attached_serial = _normalise_identity(self._attached_serial())
        current_lock = _normalise_identity(self.settings.controller_lock_serial)
        # A serial is a device identity, not a valid Textual widget identifier.
        # Prefer USB when both transports enumerate the same physical device;
        # enumeration stays read-only and never opens a second HID handle.
        devices = {}
        for index, info in enumerate(self._devices):
            serial = _normalise_identity(info.get("serial_number"))
            key = ("serial", serial) if serial else ("unidentified", index)
            previous = devices.get(key)
            if previous is None or (_is_bluetooth(previous) and not _is_bluetooth(info)):
                devices[key] = info
        self._controller_choices = {}
        buttons: list[RadioButton] = []
        buttons.append(RadioButton(
            t("Auto (first found)"),
            id="ctrl-auto",
            value=(current_lock == ""),
        ))
        for index, d in enumerate(devices.values()):
            sn = _normalise_identity(d.get("serial_number"))
            transport = "BT" if _is_bluetooth(d) else "USB"
            if sn:
                button_id = f"ctrl-device-{index}"
                self._controller_choices[button_id] = (sn, d)
                attached_now = t("attached now")
                marker = f"  < {attached_now}" if sn == attached_serial else ""
                buttons.append(RadioButton(
                    escape(f"[{transport}] {sn}{marker}"),
                    id=button_id,
                    value=(sn == current_lock),
                ))
            else:
                no_serial = t("(no serial - not selectable)")
                buttons.append(RadioButton(
                    f"\\[{transport}] {no_serial}",
                    id=f"ctrl-noserial-{index}",
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
        choice = self._controller_choices.get(button.id)
        return choice[0] if choice is not None else None

    async def _rerender_controller(self) -> None:
        # Enumerate off-thread; HID discovery may block the Textual event loop.
        self._devices = await asyncio.to_thread(_raw_dualsense_interfaces)
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
        pulse = self.app._trigger_pulse
        pulse.stop()
        current = self.settings.controller_lock_serial
        if new != current:
            self.settings.controller_lock_serial = new
            preferences.save(self.settings)
            log.info("controller_lock_serial = %r", new)
        ds = getattr(self.app, "_ds", None)
        if ds is not None:
            ds.set_selection(new)
            if new and new != _normalise_identity(self._attached_serial()):
                ds.force_reconnect()
            elif new and self.settings.enable_trigger_feedback:
                pulse.identify(ds, new, force=self.settings.startup_pulse_force)
        await self._rerender_controller()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "hidhide-install":
            if self.settings.preferred_forza_platform != XBOX_APP_PLATFORM:
                self.app.notify(t("Select Xbox App mode before installing HidHide"), severity="error")
                return
            event.button.disabled = True
            self._hidhide_installing = True
            install_status = self.query_one("#hidhide-install-status", Label)
            install_status.update(t("Checking HidHide installation; approve UAC if prompted"))
            try:
                result = await asyncio.to_thread(install_hidhide)
            except Exception as exc:
                self.app.notify(str(exc), severity="error")
                install_status.update(str(exc))
                return
            finally:
                self._hidhide_installing = False
                event.button.disabled = False
            if result.status in {InstallStatus.SUCCESS, InstallStatus.RESTART_REQUIRED}:
                self.settings.enable_hidhide = True
                preferences.save(self.settings)
                if result.status is InstallStatus.SUCCESS:
                    self._hidhide_installed = True
                    install_status.update(t("HidHide installed"))
                    await asyncio.to_thread(self.app._xinput_service.sync_hidhide)
                else:
                    install_status.update(t("Restart Windows to finish HidHide setup"))
                    self.app.notify(t("Restart Windows to finish HidHide setup"))
            else:
                install_status.update(result.error or t("HidHide installation failed"))
                self.app.notify(result.error or t("HidHide installation failed"), severity="error")
            self._refresh_hidhide_status()
        elif event.button.id == "hidhide-open":
            try:
                open_hidhide_client()
            except OSError as exc:
                self.app.notify(str(exc), severity="error")
        elif event.button.id == "xinput-action":
            snapshot = self.app._xinput_service.snapshot()
            if snapshot.status is BridgeStatus.ERROR:
                self.app._xinput_service.retry()
                self._refresh_xinput_status()
                return
            if snapshot.status is not BridgeStatus.DRIVER_MISSING:
                return
            now = time.monotonic()
            if now > self._driver_confirm_deadline:
                self._driver_confirm_deadline = now + 10.0
                event.button.label = t("Press again to install ViGEmBus")
                self.app.notify(
                    t(
                        "The bundled official ViGEmBus 1.22.0 installer will be verified and opened with UAC. No internet is required."
                    )
                )
                return
            self._driver_confirm_deadline = 0.0
            result = await asyncio.to_thread(self.app._xinput_service.install_driver)
            self._refresh_xinput_status()
            if result.status is InstallStatus.RESTART_REQUIRED:
                self.app.notify(t("Restart Windows to finish ViGEmBus setup"))
            elif result.status is InstallStatus.FAILED:
                self.app.notify(result.error, severity="error")
        elif event.button.id == "controller-rescan":
            await self._rerender_controller()
        elif event.button.id == "controller-reconnect":
            controller = getattr(self.app, "_ds", None)
            reconnect = getattr(controller, "force_reconnect", None)
            if callable(reconnect):
                reconnect()
                log.info("Immediate DualSense reconnect requested")
        elif event.button.id == "diagnostics-export":
            status = self.query_one("#diagnostics-status", Label)
            event.button.disabled = True
            status.update(t("Creating diagnostic package..."))
            try:
                path = await asyncio.to_thread(self.app.export_diagnostics)
            except Exception as exc:
                log.exception("Diagnostic package export failed")
                message = t("Diagnostic package failed: {error}").format(
                    error=str(exc) or type(exc).__name__
                )
                status.update(message)
                self.app.notify(message, severity="error")
            else:
                message = t("Diagnostic package saved: {path}").format(path=path)
                status.update(message)
                self.app.notify(message)
            finally:
                event.button.disabled = False
        elif event.button.id == "update-check":
            self.app._update_service.check_now()
        elif event.button.id == "update-action":
            snapshot = self.app._update_service.snapshot()
            if snapshot.phase is UpdatePhase.AVAILABLE:
                self.app._update_service.download()
            elif snapshot.phase is UpdatePhase.READY:
                self.app.request_close(
                    before_exit=self.app._update_service.install_on_exit,
                )
        elif event.button.id == "update-release":
            release = self.app._update_service.snapshot().release
            if release is not None and release.html_url:
                self.app._open_url(release.html_url)
        elif event.button.id == "update-manual-download":
            release = self.app._update_service.snapshot().release
            if release is not None and release.asset_url:
                self.app._open_url(release.asset_url)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        super().on_switch_changed(event)
        if event.switch.id == "use_dsx":
            self._sync_controller_visibility()
            log.info("DSX %s", "enabled" if event.value else "disabled")
