"""System tab: controller selection and ZUV-independent built-in updates."""
import asyncio
import logging
import threading
import time

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Label,
    ProgressBar,
    RadioButton,
    RadioSet,
    Select,
    Switch,
)

from lang import t
from modules.config import preferences
from modules.dualsense.main import _enumerate_dualsenses, _is_bluetooth, identify_pulse
from modules.update import UpdatePhase
from modules.update.presentation import localized_status
from modules.xinput.bridge import BridgeStatus
from modules.xinput.driver import InstallStatus
from modules.xinput.service import STEAM_PLATFORM, XBOX_APP_PLATFORM, normalize_forza_platform

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
    SystemTab #controller-radio { height: auto; padding: 0 1 1 1; }
    SystemTab #controller-hid-section { height: auto; }
    SystemTab #controller-hid-section > Label { padding: 0 1; }
    """

    def __init__(self, settings):
        super().__init__(settings)
        self._driver_confirm_deadline = 0.0

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

        yield from super().compose()

    def on_mount(self) -> None:
        self._sync_controller_visibility()
        self._update_timer = self.set_interval(0.5, self._refresh_update_status)
        self._refresh_xinput_status()

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
        self.query_one("#update-release", Button).disabled = snapshot.release is None
        self._refresh_xinput_status()

    def _refresh_xinput_status(self) -> None:
        status = self.query_one("#xinput-status", Label)
        detail = self.query_one("#xinput-detail", Label)
        action = self.query_one("#xinput-action", Button)
        if normalize_forza_platform(self.settings.preferred_forza_platform) == STEAM_PLATFORM:
            status.update(t("Steam Input mode"))
            detail.update(t("XInput bridge is off"))
            action.disabled = True
            return
        snapshot = self.app._xinput_service.snapshot()
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
        if event.select.id != "preferred_forza_platform":
            return
        platform = normalize_forza_platform(event.value)
        if platform == self.settings.preferred_forza_platform:
            return
        self.settings.preferred_forza_platform = platform
        preferences.save(self.settings)
        self.app._xinput_service.sync(getattr(self.app, "_ds", None))
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
        if event.button.id == "xinput-action":
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

    def on_switch_changed(self, event: Switch.Changed) -> None:
        super().on_switch_changed(event)
        if event.switch.id == "use_dsx":
            self._sync_controller_visibility()
            log.info("DSX %s", "enabled" if event.value else "disabled")
