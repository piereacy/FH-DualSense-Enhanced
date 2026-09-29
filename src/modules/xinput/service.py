"""Application-level platform switch for the optional XInput bridge."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, replace
from typing import Callable

from ..dualsense.hidhide import HidHidePhase, HidHideService, HidHideSnapshot
from ..dualsense.input_state import DPad, DualSenseInputState
from .bridge import BridgeSnapshot, BridgeStatus, XInputBridge
from .driver import (
    DriverProbeStatus,
    InstallResult,
    InstallStatus,
    install_and_probe,
    probe_vigem_bus,
)
from .gyro import (
    XInputGyroMapping,
    active_gyro_from_settings,
    normalize_gyro_settings,
)
from .hot_switch import KeyboardMouseActivityMonitor
from .mapping import (
    XInputButtonMapping,
    active_mapping_from_settings,
    normalize_mapping_settings,
)
from .vigem_client import is_supported_platform


STEAM_PLATFORM = "steam"
XBOX_APP_PLATFORM = "xbox_app"
FORZA_PLATFORMS = (STEAM_PLATFORM, XBOX_APP_PLATFORM)

log = logging.getLogger("fhds.xinput.service")


@dataclass(frozen=True, slots=True)
class HidHidePresentation:
    title: str
    detail: str


def normalize_forza_platform(value: object) -> str:
    normalized = str(value).strip().casefold()
    return normalized if normalized in FORZA_PLATFORMS else STEAM_PLATFORM


def custom_xinput_mapping_available(value: object) -> bool:
    """Custom mapping is meaningful only while the Xbox App bridge is selected."""
    return normalize_forza_platform(value) == XBOX_APP_PLATFORM


def _vigem_ready_for_isolation() -> bool:
    return probe_vigem_bus().status is DriverProbeStatus.AVAILABLE


def xbox_isolation_ready(
    settings,
    bridge: BridgeSnapshot,
    isolation: HidHideSnapshot,
    *,
    controller_connected: bool,
) -> bool:
    """Require the current physical controller's verified hiding before input."""
    return bool(
        normalize_forza_platform(
            getattr(settings, "preferred_forza_platform", STEAM_PLATFORM)
        ) == XBOX_APP_PLATFORM
        and bool(getattr(settings, "enable_hidhide", False))
        and not bool(getattr(settings, "use_dsx", False))
        and controller_connected
        and bridge.target_connected
        and bridge.status in {BridgeStatus.ACTIVE, BridgeStatus.STALE}
        and isolation.phase is HidHidePhase.ACTIVE
        and isolation.hidden_device_count > 0
    )


def _neutral_input(state: DualSenseInputState) -> DualSenseInputState:
    """Keep the virtual target alive without forwarding unisolated controls."""
    return replace(
        state,
        left_x=128,
        left_y=128,
        right_x=128,
        right_y=128,
        left_trigger=0,
        right_trigger=0,
        dpad=DPad.NEUTRAL,
        buttons=frozenset(),
        touchpad_regions=frozenset(),
        touchpad_touched=False,
        gyro_x=0,
        gyro_y=0,
        gyro_z=0,
        accel_x=0,
        accel_y=0,
        accel_z=0,
    )


def hidhide_presentation(
    settings,
    bridge: BridgeSnapshot,
    isolation: HidHideSnapshot,
    translate: Callable[[str], str],
    *,
    controller_connected: bool = True,
) -> HidHidePresentation:
    if isolation.phase is HidHidePhase.ERROR:
        return HidHidePresentation(
            translate("HidHide isolation error"),
            isolation.last_error
            or translate("Open the HidHide Configuration Client to recover"),
        )
    if not bool(getattr(settings, "enable_hidhide", False)):
        return HidHidePresentation(
            translate("HidHide is required for Xbox App")
            if normalize_forza_platform(getattr(settings, "preferred_forza_platform", STEAM_PLATFORM)) == XBOX_APP_PLATFORM
            else translate("HidHide isolation is off"),
            translate("Enable HidHide before using Xbox App")
            if normalize_forza_platform(getattr(settings, "preferred_forza_platform", STEAM_PLATFORM)) == XBOX_APP_PLATFORM
            else translate("FHDS is not checking HidHide; manual device hiding may remain active"),
        )
    if normalize_forza_platform(
        getattr(settings, "preferred_forza_platform", STEAM_PLATFORM)
    ) != XBOX_APP_PLATFORM:
        return HidHidePresentation(
            translate("HidHide isolation is paused"),
            translate("Select Xbox App mode to hide the physical DualSense"),
        )
    if bool(getattr(settings, "use_dsx", False)):
        return HidHidePresentation(
            translate("HidHide isolation is paused"),
            translate("Direct HID mode is required; DSX owns the controller"),
        )
    if isolation.phase is HidHidePhase.ACTIVE and (
        isolation.hidden_device_count < 1 or not controller_connected
    ):
        return HidHidePresentation(
            translate("HidHide isolation is waiting"),
            translate("Connect or reconnect the DualSense to apply isolation"),
        )
    if isolation.phase is HidHidePhase.ACTIVE:
        if isolation.automatic_configuration:
            detail = translate(
                "FHDS configured {count} hidden DualSense device(s); restart an already-running game"
            ).format(count=isolation.hidden_device_count)
        elif isolation.manual_configuration:
            detail = translate(
                "Verified {count} manually hidden device(s); restart an already-running game"
            ).format(count=isolation.hidden_device_count)
        else:
            detail = translate(
                "Hidden {count} device path(s); restart an already-running game"
            ).format(count=isolation.hidden_device_count)
        return HidHidePresentation(
            translate(
                "FHDS-managed HidHide isolation active"
                if isolation.automatic_configuration
                else (
                    "Manual HidHide rules verified"
                    if isolation.manual_configuration
                    else "Physical DualSense hidden from games"
                )
            ),
            detail,
        )
    if isolation.phase is HidHidePhase.READY:
        if isolation.automatic_configuration:
            return HidHidePresentation(
                translate("HidHide isolation is ready"),
                translate("FHDS configured HidHide; reconnect the DualSense to apply hiding"),
            )
        if isolation.manual_configuration:
            return HidHidePresentation(
                translate("HidHide isolation is ready"),
                translate("Manual HidHide rules found; reconnect the DualSense to verify hiding"),
            )
        return HidHidePresentation(
            translate("HidHide isolation is ready"),
            translate("Connect or reconnect the DualSense to apply isolation"),
        )
    if isolation.phase is HidHidePhase.UNAVAILABLE:
        return HidHidePresentation(
            translate("HidHide unavailable"),
            isolation.last_error
            or translate("Install HidHide and restart FHDS"),
        )
    if bridge.status in {
        BridgeStatus.DRIVER_MISSING,
        BridgeStatus.INSTALLING,
        BridgeStatus.RESTART_REQUIRED,
    }:
        detail = translate(
            "ViGEmBus must be ready before the physical controller is hidden"
        )
    else:
        detail = translate(
            "Connect or reconnect the DualSense to apply isolation"
        )
    return HidHidePresentation(translate("HidHide isolation is waiting"), detail)


class XInputBridgeService:
    """Run the optional Xbox App bridge for the selected backend lifetime.

    Steam mode leaves the bridge off. Xbox App direct-HID mode starts one
    virtual X360 worker plus the Raw Input activity monitor for the lifetime of
    the selected backend. Physical input stays neutral until HidHide is verified.
    """

    def __init__(
        self,
        settings,
        *,
        bridge: XInputBridge | None = None,
        input_activity_monitor: KeyboardMouseActivityMonitor | None = None,
        hidhide_service: HidHideService | None = None,
        hidhide_driver_ready: Callable[[], bool] = _vigem_ready_for_isolation,
        platform_supported: Callable[[], bool] = is_supported_platform,
        hidhide_retry_timer_factory: Callable[
            [float, Callable[[], None]], threading.Timer
        ] = threading.Timer,
    ):
        self.settings = settings
        if bridge is None:
            activity_monitor = input_activity_monitor or KeyboardMouseActivityMonitor()
            input_activity_monitor = activity_monitor
            bridge = XInputBridge(
                keyboard_mouse_activity=(
                    activity_monitor.poll if activity_monitor.available else None
                )
            )
        self._bridge = bridge
        self._input_activity_monitor = input_activity_monitor
        self._hidhide = hidhide_service or HidHideService()
        self._hidhide_driver_ready = hidhide_driver_ready
        self._platform_supported = platform_supported
        self._hidhide_retry_timer_factory = hidhide_retry_timer_factory
        self._hidhide_retry_timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._hidhide_callback_lock = threading.Lock()
        self._backend = None
        self._override: BridgeSnapshot | None = None
        self._preview_requested = False

        callback_setter = getattr(self._bridge, "set_target_state_callback", None)
        if callable(callback_setter):
            callback_setter(self._on_bridge_target_state_changed)

    @property
    def platform(self) -> str:
        return normalize_forza_platform(
            getattr(self.settings, "preferred_forza_platform", STEAM_PLATFORM)
        )

    @property
    def preview_requested(self) -> bool:
        with self._lock:
            return self._preview_requested

    def request_preview_runtime(self, enabled: bool) -> bool:
        """Track the bounded Lab request; the normal backend already owns HID."""
        with self._lock:
            self._preview_requested = bool(enabled)
        return True

    def sync(self, backend) -> None:
        with self._lifecycle_lock:
            self._sync(backend)

    def prepare_controller_access(self, backend) -> HidHideSnapshot:
        """Allow FHDS through HidHide before the HID worker first opens it."""
        with self._lifecycle_lock:
            if self._application_access_needed(backend):
                return self._hidhide.prepare_application_access()
            return self._hidhide.snapshot()

    def _sync(self, backend) -> None:
        self._cancel_hidhide_retry()
        self.refresh_button_mapping()
        old_backend = self._detach_backend()
        self._bridge.stop()
        self._stop_input_activity_monitor()
        self._apply_hidhide_disabled(
            backend=old_backend,
            remove_allowlist=not self._hidhide_enabled(),
        )

        with self._lock:
            self._backend = backend
            self._override = (
                BridgeSnapshot(status=BridgeStatus.DISABLED)
                if self.platform != XBOX_APP_PLATFORM
                else None
            )
        if self.platform != XBOX_APP_PLATFORM:
            return
        if not self._platform_supported():
            with self._lock:
                self._override = BridgeSnapshot(
                    status=BridgeStatus.DISABLED,
                    last_error="Xbox App input bridge requires Windows x64",
                )
            return
        setter = getattr(backend, "set_input_consumer", None)
        if not callable(setter):
            with self._lock:
                self._override = BridgeSnapshot(
                    status=BridgeStatus.ERROR,
                    last_error=(
                        "Xbox App input bridge requires direct HID mode; disable DSX"
                    ),
                )
            return

        self._start_input_activity_monitor()
        self._bridge.start()
        bridge_publisher = self._bridge.publish_latest

        def isolated_publish(
            state: DualSenseInputState,
            received_at: float | None = None,
        ) -> None:
            bridge_publisher(
                state if self.isolation_confirmed() else _neutral_input(state),
                received_at,
            )

        setter(isolated_publish)
        with self._lock:
            self._override = None
        self._reconcile_hidhide()

    def _on_bridge_target_state_changed(self, _connected: bool) -> None:
        """Reconcile isolation off the ViGEm worker without blocking it."""
        if not self._hidhide_callback_lock.acquire(blocking=False):
            return

        def reconcile() -> None:
            try:
                with self._lifecycle_lock:
                    self._reconcile_hidhide()
            except Exception:
                log.exception("HidHide target-state reconciliation failed")
            finally:
                self._hidhide_callback_lock.release()

        threading.Thread(
            target=reconcile,
            name="fhds-hidhide-reconcile",
            daemon=True,
        ).start()

    def sync_hidhide(self) -> HidHideSnapshot:
        """Apply the isolation toggle without recreating the virtual target."""
        with self._lifecycle_lock:
            self._reconcile_hidhide(force=True)
            return self._hidhide.snapshot()

    def hidhide_snapshot(self) -> HidHideSnapshot:
        return self._hidhide.snapshot()

    def isolation_confirmed(self) -> bool:
        with self._lock:
            backend = self._backend
        return xbox_isolation_ready(
            self.settings,
            self.snapshot(),
            self._hidhide.snapshot(),
            controller_connected=bool(getattr(backend, "connected", False)),
        )

    def verify_isolation(self) -> bool:
        """Recheck the driver immediately before a programmatic game launch."""
        with self._lifecycle_lock:
            verifier = getattr(self._hidhide, "verify_active", None)
            if callable(verifier):
                verifier()
            return self.isolation_confirmed()

    def _reconcile_hidhide(self, *, force: bool = False) -> None:
        del force
        with self._lock:
            backend = self._backend
        bridge = self._bridge.snapshot()
        visibility_setter = getattr(backend, "set_device_visibility_observer", None)
        desired = bool(
            self._hidhide_enabled()
            and self.platform == XBOX_APP_PLATFORM
            and self._platform_supported()
            and callable(getattr(backend, "set_input_consumer", None))
            and callable(visibility_setter)
            and self._bridge_ready_for_hidhide(bridge)
        )
        if not desired:
            cleaned = self._apply_hidhide_disabled(
                backend=backend,
                remove_allowlist=not self._hidhide_enabled(),
            )
            if cleaned and self._application_access_needed(backend):
                snapshot = self._hidhide.prepare_application_access()
                if snapshot.phase in {HidHidePhase.ERROR, HidHidePhase.UNAVAILABLE}:
                    self._schedule_hidhide_retry()
                else:
                    self._cancel_hidhide_retry()
            elif self._application_access_needed(backend):
                self._schedule_hidhide_retry()
            else:
                self._cancel_hidhide_retry()
            return
        self._apply_hidhide_enabled(backend)
        # The same bounded timer also detects a rule or Device hiding switch
        # removed in the official client while FHDS is running.
        self._schedule_hidhide_retry()

    def _schedule_hidhide_retry(self) -> None:
        if self._hidhide_retry_timer is not None:
            return

        def retry() -> None:
            with self._lifecycle_lock:
                if self._hidhide_retry_timer is not timer:
                    return
                self._hidhide_retry_timer = None
                try:
                    self._reconcile_hidhide()
                except Exception:
                    log.exception("HidHide isolation retry failed")

        timer = self._hidhide_retry_timer_factory(5.0, retry)
        timer.daemon = True
        self._hidhide_retry_timer = timer
        try:
            timer.start()
        except Exception:
            self._hidhide_retry_timer = None
            log.exception("Could not schedule HidHide isolation retry")

    def _cancel_hidhide_retry(self) -> None:
        timer, self._hidhide_retry_timer = self._hidhide_retry_timer, None
        if timer is not None:
            timer.cancel()

    def _application_access_needed(self, backend) -> bool:
        return bool(
            self._hidhide_enabled()
            and self.platform == XBOX_APP_PLATFORM
            and self._platform_supported()
            and callable(getattr(backend, "set_input_consumer", None))
            and callable(getattr(backend, "set_device_visibility_observer", None))
        )

    @staticmethod
    def _bridge_ready_for_hidhide(snapshot: BridgeSnapshot) -> bool:
        return bool(
            snapshot.target_connected
            and snapshot.status in {BridgeStatus.ACTIVE, BridgeStatus.STALE}
        )

    def _apply_hidhide_disabled(
        self,
        *,
        backend=None,
        remove_allowlist: bool,
    ) -> bool:
        observer_detached = True
        visibility_setter = getattr(backend, "set_device_visibility_observer", None)
        if callable(visibility_setter):
            try:
                visibility_setter(None)
            except Exception:
                observer_detached = False
                log.exception("Could not detach the HidHide visibility observer")
        try:
            snapshot = self._hidhide.stop(remove_allowlist=remove_allowlist)
        except Exception:
            log.exception("Could not stop the HidHide isolation session")
            return False
        return bool(observer_detached and snapshot.phase is HidHidePhase.DISABLED)

    def _apply_hidhide_enabled(self, backend) -> bool:
        if not self._hidhide_enabled():
            return False
        bridge = self._bridge.snapshot()
        if not self._bridge_ready_for_hidhide(bridge):
            return False
        visibility_setter = getattr(backend, "set_device_visibility_observer", None)
        if not callable(visibility_setter):
            return False
        try:
            driver_ready = bool(self._hidhide_driver_ready())
        except Exception as exc:
            log.warning("Could not probe HidHide readiness: %s", exc)
            driver_ready = False
        if not driver_ready:
            return False

        current = self._hidhide.snapshot()
        if current.phase in {HidHidePhase.ERROR, HidHidePhase.UNAVAILABLE}:
            if not self._apply_hidhide_disabled(
                backend=backend,
                remove_allowlist=False,
            ):
                return False
            current = self._hidhide.snapshot()
        if self._hidhide.started and current.phase in {
            HidHidePhase.READY,
            HidHidePhase.ACTIVE,
        }:
            snapshot = current
        else:
            try:
                snapshot = self._hidhide.start()
            except Exception:
                log.exception("Could not start the HidHide isolation session")
                return False
        if snapshot.phase not in {HidHidePhase.READY, HidHidePhase.ACTIVE}:
            return False
        try:
            visibility_setter(self._hidhide.register_device)
        except Exception:
            log.exception("Could not attach the HidHide visibility observer")
            self._apply_hidhide_disabled(
                backend=backend,
                remove_allowlist=False,
            )
            return False
        return True

    def _hidhide_enabled(self) -> bool:
        return bool(getattr(self.settings, "enable_hidhide", False))

    def refresh_button_mapping(self) -> XInputButtonMapping:
        """Apply global button and motion settings without recreating the target."""
        normalize_mapping_settings(self.settings)
        normalize_gyro_settings(self.settings)
        mapping = active_mapping_from_settings(self.settings)
        setter = getattr(self._bridge, "set_button_mapping", None)
        if callable(setter):
            setter(mapping)
        gyro_setter = getattr(self._bridge, "set_gyro_mapping", None)
        if callable(gyro_setter):
            gyro_setter(active_gyro_from_settings(self.settings))
        return mapping

    def refresh_gyro_mapping(self) -> XInputGyroMapping:
        """Apply only the motion conversion settings for live UI changes."""
        normalize_gyro_settings(self.settings)
        mapping = active_gyro_from_settings(self.settings)
        setter = getattr(self._bridge, "set_gyro_mapping", None)
        if callable(setter):
            setter(mapping)
        return mapping

    def retry(self) -> None:
        with self._lock:
            backend = self._backend
        self.sync(backend)

    def install_driver(
        self,
        installer: Callable[[], InstallResult] = install_and_probe,
    ) -> InstallResult:
        """Run the already-confirmed installer flow; caller owns the UI prompt."""
        with self._lifecycle_lock:
            self._cancel_hidhide_retry()
            with self._lock:
                backend = self._backend
            self._detach_backend()
            self._bridge.stop()
            self._stop_input_activity_monitor()
            self._apply_hidhide_disabled(
                backend=backend,
                remove_allowlist=not self._hidhide_enabled(),
            )
            with self._lock:
                self._backend = backend
                self._override = BridgeSnapshot(status=BridgeStatus.INSTALLING)
            result = installer()
            if result.status is InstallStatus.SUCCESS:
                self._sync(backend)
                return result
            status = {
                InstallStatus.CANCELLED: BridgeStatus.DRIVER_MISSING,
                InstallStatus.RESTART_REQUIRED: BridgeStatus.RESTART_REQUIRED,
                InstallStatus.FAILED: BridgeStatus.ERROR,
            }[result.status]
            with self._lock:
                self._backend = backend
                self._override = BridgeSnapshot(
                    status=status,
                    last_error=result.error,
                )
            return result

    def snapshot(self) -> BridgeSnapshot:
        with self._lock:
            override = self._override
        return override or self._bridge.snapshot()

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._cancel_hidhide_retry()
            backend = self._detach_backend()
            self._bridge.stop()
            self._stop_input_activity_monitor()
            self._apply_hidhide_disabled(
                backend=backend,
                remove_allowlist=not self._hidhide_enabled(),
            )
            with self._lock:
                self._preview_requested = False
                self._override = None

    def _detach_backend(self):
        with self._lock:
            backend = self._backend
            self._backend = None
        self._disconnect_backend_callbacks(backend)
        return backend

    @staticmethod
    def _disconnect_backend_callbacks(backend) -> None:
        setter = getattr(backend, "set_input_consumer", None)
        if callable(setter):
            try:
                setter(None)
            except Exception:
                log.exception("Could not detach the XInput consumer")
        visibility_setter = getattr(backend, "set_device_visibility_observer", None)
        if callable(visibility_setter):
            try:
                visibility_setter(None)
            except Exception:
                log.exception("Could not detach the HidHide visibility observer")

    def _start_input_activity_monitor(self) -> None:
        monitor = self._input_activity_monitor
        if monitor is not None and monitor.available:
            monitor.start()

    def _stop_input_activity_monitor(self) -> None:
        monitor = self._input_activity_monitor
        if monitor is not None:
            monitor.stop()
