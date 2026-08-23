"""Application-level platform switch for the optional XInput bridge."""
from __future__ import annotations

import logging
import math
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable

from ..dualsense.hidhide import HidHidePhase, HidHideService, HidHideSnapshot
from ..forzahorizon.game_launch import is_any_forza_game_foreground
from ..forzahorizon.process_watch import ProcessScanError
from .bridge import BridgeSnapshot, BridgeStatus, XInputBridge
from .driver import (
    DriverProbeStatus,
    InstallResult,
    InstallStatus,
    install_and_probe,
    probe_vigem_bus,
)
from .hot_switch import KeyboardMouseActivityMonitor
from .gyro import (
    XInputGyroMapping,
    active_gyro_from_settings,
    normalize_gyro_settings,
)
from .mapping import (
    XInputButtonMapping,
    active_mapping_from_settings,
    normalize_mapping_settings,
)
from .vigem_client import is_supported_platform


STEAM_PLATFORM = "steam"
XBOX_APP_PLATFORM = "xbox_app"
FORZA_PLATFORMS = (STEAM_PLATFORM, XBOX_APP_PLATFORM)
# The telemetry loop may already be inside one 50 ms socket wait when this
# monitor observes an edge. A 50 ms Windows poll keeps the combined worst-case
# foreground-to-output response within the 100 ms contract.
FORZA_GATE_POLL_S = 0.05 if sys.platform == "win32" else 0.5
FOREGROUND_MONITOR_STOP_TIMEOUT_S = 5.0
CHILD_LIFECYCLE_STOP_TIMEOUT_S = 5.0
HIDHIDE_RETRY_S = 1.0

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


def _supported_forza_foreground() -> bool:
    return is_any_forza_game_foreground(strict=True)


def hidhide_presentation(
    settings,
    bridge: BridgeSnapshot,
    isolation: HidHideSnapshot,
    translate: Callable[[str], str],
) -> HidHidePresentation:
    if isolation.phase is HidHidePhase.ERROR:
        return HidHidePresentation(
            translate("HidHide isolation error"),
            isolation.last_error
            or translate("Open the HidHide Configuration Client to recover"),
        )
    if not bool(getattr(settings, "enable_hidhide", False)):
        return HidHidePresentation(
            translate("HidHide isolation is off"),
            translate("The physical DualSense remains visible to games"),
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
    if bridge.status is BridgeStatus.WAITING_GAME:
        return HidHidePresentation(
            translate("HidHide isolation is waiting"),
            translate("Isolation starts only while FH4, FH5, or FH6 is in the foreground"),
        )
    if isolation.phase is HidHidePhase.ACTIVE:
        return HidHidePresentation(
            translate("Physical DualSense hidden from games"),
            translate("Hidden {count} device path(s); restart an already-running game").format(
                count=isolation.hidden_device_count
            ),
        )
    if isolation.phase is HidHidePhase.READY:
        return HidHidePresentation(
            translate("HidHide isolation is ready"),
            translate("Connect or reconnect the DualSense to apply isolation"),
        )
    if isolation.phase is HidHidePhase.UNAVAILABLE:
        return HidHidePresentation(
            translate("HidHide unavailable"),
            isolation.last_error or translate("Install HidHide 1.7 or newer and restart FHDS"),
        )
    if bridge.status in {
        BridgeStatus.DRIVER_MISSING,
        BridgeStatus.INSTALLING,
        BridgeStatus.RESTART_REQUIRED,
    }:
        detail = translate("ViGEmBus must be ready before the physical controller is hidden")
    else:
        detail = translate("Install HidHide 1.7 or newer and restart FHDS")
    return HidHidePresentation(translate("HidHide isolation is waiting"), detail)


class XInputBridgeService:
    """Gate every game-facing controller path from the exact Forza foreground.

    Native DualSense discovery stays passive while the gate is closed: hidapi
    enumeration may report availability, but no physical handle is held. The
    HID owner, Xbox bridge, Raw Input monitor, HidHide session and telemetry
    output are activated only while FH4, FH5 or FH6 owns the foreground window.
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
        forza_foreground: Callable[[], bool] | None = None,
        clock: Callable[[], float] = time.monotonic,
        foreground_poll_interval_s: float = FORZA_GATE_POLL_S,
        background_foreground_monitor: bool | None = None,
    ):
        use_default_foreground_detector = forza_foreground is None
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
        self._forza_foreground = forza_foreground or _supported_forza_foreground
        self._clock = clock
        try:
            poll_interval = float(foreground_poll_interval_s)
        except (TypeError, ValueError, OverflowError):
            poll_interval = FORZA_GATE_POLL_S
        self._foreground_poll_interval = (
            poll_interval
            if math.isfinite(poll_interval) and poll_interval >= 0.05
            else FORZA_GATE_POLL_S
        )
        self._background_foreground_monitor = (
            use_default_foreground_detector
            if background_foreground_monitor is None
            else bool(background_foreground_monitor)
        )
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._backend = None
        self._override: BridgeSnapshot | None = None
        self._forza_gate_enabled = False
        self._forza_active = False
        self._forza_state_known = False
        self._preview_requested = False
        self._last_foreground_poll_at: float | None = None
        self._hidhide_applied = False
        self._hidhide_retry_desired: bool | None = None
        self._hidhide_retry_at = 0.0
        self._foreground_monitor_stop = threading.Event()
        self._foreground_monitor_wake = threading.Event()
        self._foreground_monitor_thread: threading.Thread | None = None
        self._foreground_monitor_restart_pending = False
        self._foreground_monitor_stop_timeout = FOREGROUND_MONITOR_STOP_TIMEOUT_S
        self._child_lifecycle_stop = threading.Event()
        self._child_lifecycle_wake = threading.Event()
        self._child_lifecycle_thread: threading.Thread | None = None
        self._child_lifecycle_revision = 0
        self._child_session_active = False
        self._background_gate_generation = 0
        self._child_session_generation = -1
        self._background_consumer_token: object | None = None
        self._background_visibility_token: object | None = None
        self._child_lifecycle_stop_timeout = CHILD_LIFECYCLE_STOP_TIMEOUT_S
        target_callback_setter = getattr(
            self._bridge,
            "set_target_state_callback",
            None,
        )
        if callable(target_callback_setter):
            target_callback_setter(self._on_bridge_target_state_changed)

    @property
    def platform(self) -> str:
        return normalize_forza_platform(
            getattr(self.settings, "preferred_forza_platform", STEAM_PLATFORM)
        )

    def sync(self, backend) -> None:
        self._publish_closed_gate()
        self._stop_foreground_monitor()
        self._request_child_lifecycle_stop()
        with self._lifecycle_lock:
            self._sync(backend)
        self._join_child_lifecycle_worker()
        self._start_child_lifecycle_worker()
        self._start_foreground_monitor()

    def _publish_closed_gate(self) -> None:
        """Close the output gate before any monitor join or child teardown."""
        with self._lock:
            backend = self._backend
            self._forza_gate_enabled = False
            self._forza_active = False
            self._forza_state_known = True
            self._preview_requested = False
            self._override = BridgeSnapshot(status=BridgeStatus.WAITING_GAME)
            self._background_consumer_token = None
            self._background_visibility_token = None
            self._background_gate_generation += 1
            self._child_lifecycle_revision += 1
        self._child_lifecycle_wake.set()
        self._cancel_backend_startup_pulse(backend)
        self._set_backend_runtime_enabled(backend, False)

    def _sync(self, backend) -> None:
        self.refresh_button_mapping()
        with self._lock:
            # Publish the closed gate before any child teardown can block.
            self._forza_active = False
            self._forza_state_known = True
            self._override = BridgeSnapshot(status=BridgeStatus.WAITING_GAME)
        self._cancel_backend_startup_pulse(self._backend)
        self._detach_backend()
        self._bridge.stop()
        self._stop_input_activity_monitor()
        self._apply_hidhide_disabled(
            remove_allowlist=not self._hidhide_enabled(),
        )
        with self._lock:
            self._child_session_active = False
            self._child_session_generation = -1
            self._backend = backend
            self._forza_gate_enabled = True
            self._forza_active = False
            self._forza_state_known = False
            self._preview_requested = False
            self._last_foreground_poll_at = None
            self._override = BridgeSnapshot(status=BridgeStatus.WAITING_GAME)
        self._set_backend_runtime_enabled(backend, False)
        self._poll_forza_foreground(force=True)
        if self._background_foreground_monitor:
            self._request_child_lifecycle_reconcile()
        else:
            self._reconcile_hidhide()

    @property
    def forza_active(self) -> bool:
        with self._lock:
            return self._forza_active

    @property
    def preview_requested(self) -> bool:
        with self._lock:
            return self._preview_requested

    def request_preview_runtime(self, enabled: bool) -> bool:
        """Temporarily allow native HID for an explicit Haptics Lab preview.

        The UI must revoke this request as soon as its window loses focus and
        when the bounded preview completes. Forza remains authoritative and
        never shares this path with the Xbox/Raw Input/HidHide child session.
        """
        requested = bool(enabled)
        with self._lock:
            if not self._forza_gate_enabled or self._backend is None:
                requested = False
            self._preview_requested = requested
            backend = self._backend
            runtime_enabled = bool(self._forza_active or requested)
        self._set_backend_runtime_enabled(backend, runtime_enabled)
        return requested

    def poll_forza_foreground(self, *, force: bool = False) -> bool:
        """Return the exact FH4/FH5/FH6 foreground-window output gate.

        Production services refresh this state on their own monitor thread, so
        the telemetry loop never performs a Win32/psutil query or waits for
        child teardown. Injected detectors keep the synchronous path for
        deterministic unit tests.
        """
        if self._background_foreground_monitor:
            return self.forza_active
        with self._lifecycle_lock:
            active = self._poll_forza_foreground(force=force)
            self._reconcile_hidhide()
            return active

    def _poll_forza_foreground(self, *, force: bool = False) -> bool:
        with self._lock:
            enabled = self._forza_gate_enabled
            last_poll = self._last_foreground_poll_at
            active = self._forza_active
        if not enabled:
            return active
        now = self._clock()
        if (
            not force
            and last_poll is not None
            and now - last_poll < self._foreground_poll_interval
        ):
            return active
        with self._lock:
            self._last_foreground_poll_at = now
        try:
            detected = bool(self._forza_foreground())
        except ProcessScanError as exc:
            log.warning(
                "Could not verify the Forza foreground window; game-facing output remains off: %s",
                exc,
            )
            detected = False
        except Exception as exc:
            log.warning(
                "Forza foreground gate failed; game-facing output remains off: %s",
                exc,
            )
            detected = False
        self._set_forza_active(detected)
        return detected

    def _set_forza_active(self, active: bool) -> None:
        if self._background_foreground_monitor:
            self._set_forza_active_deferred(active)
            return
        with self._lock:
            # A lifecycle operation may close the gate while an older Win32
            # query is still in flight. Never let that stale result reopen it.
            if active and not self._forza_gate_enabled:
                return
            previous = self._forza_active
            state_known = self._forza_state_known
            backend = self._backend
        if state_known and active == previous:
            return
        if not active:
            with self._lock:
                # This state is the safety boundary consumed by loop.py. It
                # must become observable before any join or driver IO below.
                self._forza_active = False
                self._forza_state_known = True
                self._override = BridgeSnapshot(status=BridgeStatus.WAITING_GAME)
                self._preview_requested = False
            # `_sync()` has already cleaned every optional callback/session on
            # the first (usually inactive) observation.  Only a real active ->
            # inactive edge needs the reverse lifecycle again.
            if state_known:
                self._cancel_backend_startup_pulse(backend)
                self._set_backend_runtime_enabled(backend, False)
                self._disconnect_backend_callbacks(backend)
                # stop() signals the bridge worker before it waits, so the
                # existing X360 target is neutralized without waiting for the
                # remaining lifecycle cleanup.
                self._bridge.stop()
                self._stop_input_activity_monitor()
                self._apply_hidhide_disabled(
                    remove_allowlist=not self._hidhide_enabled(),
                )
            if previous:
                log.info(
                    "No supported Forza Horizon window is in the foreground; game-facing output paused"
                )
            return

        bridge_override: BridgeSnapshot | None = BridgeSnapshot(
            status=BridgeStatus.DISABLED
        )
        bridge_started = False
        with self._lock:
            # Let the output loop preempt Lab immediately. Optional Xbox child
            # startup may still take time, but it no longer owns this gate.
            self._forza_active = True
            self._forza_state_known = True
            self._preview_requested = False
            self._override = bridge_override
        self._set_backend_runtime_enabled(backend, True)
        try:
            if backend is None:
                raise RuntimeError("controller backend is unavailable")
            if self.platform == XBOX_APP_PLATFORM:
                if not self._platform_supported():
                    bridge_override = BridgeSnapshot(
                        status=BridgeStatus.DISABLED,
                        last_error="Xbox App input bridge requires Windows x64",
                    )
                else:
                    setter = getattr(backend, "set_input_consumer", None)
                    if not callable(setter):
                        bridge_override = BridgeSnapshot(
                            status=BridgeStatus.ERROR,
                            last_error=(
                                "Xbox App input bridge requires direct HID mode; disable DSX"
                            ),
                        )
                    else:
                        self._start_input_activity_monitor()
                        self._bridge.start()
                        setter(self._bridge.publish_latest)
                        bridge_started = True
                        bridge_override = None

        except Exception as exc:
            self._disconnect_backend_callbacks(backend)
            self._bridge.stop()
            self._stop_input_activity_monitor()
            self._apply_hidhide_disabled(
                remove_allowlist=not self._hidhide_enabled(),
            )
            with self._lock:
                self._override = BridgeSnapshot(
                    status=BridgeStatus.ERROR,
                    last_error=str(exc) or type(exc).__name__,
                )
            log.exception("Could not start the Forza game-facing output session")
            return
        with self._lock:
            self._override = bridge_override
        if bridge_started:
            log.info(
                "Supported Forza Horizon foreground detected; controller and virtual Xbox input started"
            )
        else:
            log.info("Supported Forza Horizon foreground detected; game-facing output enabled")

    def _set_forza_active_deferred(self, active: bool) -> None:
        """Publish the production gate edge without running child lifecycle IO."""
        with self._lock:
            if active and not self._forza_gate_enabled:
                return
            previous = self._forza_active
            state_known = self._forza_state_known
            if state_known and active == previous:
                return
            self._forza_active = active
            self._forza_state_known = True
            if active:
                self._preview_requested = False
            backend = self._backend
            self._override = BridgeSnapshot(
                status=(BridgeStatus.DISABLED if active else BridgeStatus.WAITING_GAME)
            )
            if not active:
                # Invalidate every callback before the detector returns. A
                # child call that was already blocked may still finish later,
                # but its consumer/observer can no longer affect this gate.
                self._background_consumer_token = None
                self._background_visibility_token = None
            self._background_gate_generation += 1
            self._child_lifecycle_revision += 1
        self._child_lifecycle_wake.set()
        if active:
            self._set_backend_runtime_enabled(backend, True)
            log.info("Supported Forza Horizon foreground detected; game-facing output enabled")
        else:
            # This is an in-memory backend request, not child lifecycle IO.
            # Cancel it on the same edge that closes the telemetry gate so a
            # slow HidHide/ViGEm/Raw Input operation cannot emit it later.
            self._cancel_backend_startup_pulse(backend)
            self._set_backend_runtime_enabled(backend, False)
            if previous:
                log.info(
                    "No supported Forza Horizon window is in the foreground; game-facing output paused"
                )

    def _request_child_lifecycle_reconcile(self) -> None:
        if not self._background_foreground_monitor:
            return
        with self._lock:
            self._child_lifecycle_revision += 1
        self._child_lifecycle_wake.set()

    def _start_child_lifecycle_worker(self) -> None:
        if not self._background_foreground_monitor:
            return
        with self._lock:
            current = self._child_lifecycle_thread
            if current is not None and current.is_alive():
                return
            if not self._forza_gate_enabled:
                return
            self._child_lifecycle_stop.clear()
            thread = threading.Thread(
                target=self._child_lifecycle_loop,
                name="fhds-forza-child-lifecycle",
                daemon=True,
            )
            self._child_lifecycle_thread = thread
        self._child_lifecycle_wake.set()
        thread.start()

    def _request_child_lifecycle_stop(self) -> None:
        if not self._background_foreground_monitor:
            return
        self._child_lifecycle_stop.set()
        self._child_lifecycle_wake.set()

    def _join_child_lifecycle_worker(self) -> None:
        if not self._background_foreground_monitor:
            return
        with self._lock:
            thread = self._child_lifecycle_thread
        if thread is None:
            return
        if thread is not threading.current_thread():
            thread.join(timeout=self._child_lifecycle_stop_timeout)
        if thread.is_alive():
            log.error(
                "Forza child lifecycle worker did not stop within %.2f seconds",
                self._child_lifecycle_stop_timeout,
            )
            return
        with self._lock:
            if self._child_lifecycle_thread is thread:
                self._child_lifecycle_thread = None

    def _child_lifecycle_loop(self) -> None:
        try:
            while not self._child_lifecycle_stop.is_set():
                signaled = self._child_lifecycle_wake.wait(HIDHIDE_RETRY_S)
                self._child_lifecycle_wake.clear()
                if self._child_lifecycle_stop.is_set():
                    break
                with self._lock:
                    periodic_needed = bool(
                        (self._forza_gate_enabled and self._forza_active)
                        or self._child_session_active
                        or self._hidhide_retry_desired is not None
                    )
                if not signaled and not periodic_needed:
                    continue
                try:
                    while not self._child_lifecycle_stop.is_set():
                        with self._lock:
                            revision = self._child_lifecycle_revision
                            desired = bool(
                                self._forza_gate_enabled and self._forza_active
                            )
                        with self._lifecycle_lock:
                            if self._child_lifecycle_stop.is_set():
                                break
                            self._apply_background_child_lifecycle(desired)
                        with self._lock:
                            if revision == self._child_lifecycle_revision:
                                break
                except Exception:
                    # A transient child failure must not permanently remove
                    # the lifecycle owner. The next wake or one-second retry
                    # re-evaluates the latest gate revision.
                    log.exception("Forza child lifecycle worker iteration failed")
        finally:
            with self._lock:
                if self._child_lifecycle_thread is threading.current_thread():
                    self._child_lifecycle_thread = None

    def _background_gate_open(self, generation: int | None = None) -> bool:
        with self._lock:
            return bool(
                not self._child_lifecycle_stop.is_set()
                and self._forza_gate_enabled
                and self._forza_active
                and (
                    generation is None
                    or generation == self._background_gate_generation
                )
            )

    def _background_input_consumer(self, token: object, publisher):
        def publish(state, received_at=None) -> None:
            with self._lock:
                allowed = bool(
                    self._background_consumer_token is token
                    and self._forza_gate_enabled
                    and self._forza_active
                )
            if allowed:
                publisher(state, received_at)

        return publish

    def _background_visibility_observer(self, token: object):
        def observe(info) -> bool:
            with self._lock:
                allowed = bool(
                    self._background_visibility_token is token
                    and self._forza_gate_enabled
                    and self._forza_active
                )
            return bool(allowed and self._hidhide.register_device(info))

        return observe

    def _apply_background_child_lifecycle(self, desired: bool) -> None:
        with self._lock:
            backend = self._backend
            child_active = self._child_session_active
            gate_generation = self._background_gate_generation
            child_generation = self._child_session_generation
        if not desired:
            self._cleanup_background_children(backend)
            return
        if child_active and child_generation == gate_generation:
            if self.platform == XBOX_APP_PLATFORM:
                # A timed-out Raw Input startup remains fail-open for the
                # controller, then the periodic lifecycle pass retries once
                # its cancelled listener has actually exited.
                self._start_input_activity_monitor()
            self._reconcile_hidhide()
            if not self._background_gate_open(gate_generation):
                self._cleanup_background_children(backend)
            return
        if child_active:
            # The gate closed and reopened while an older blocking start was
            # still in flight. Tear down that generation before rebinding the
            # backend callbacks for the new foreground session.
            self._cleanup_background_children(backend)
            if not self._background_gate_open():
                return
            with self._lock:
                gate_generation = self._background_gate_generation

        bridge_override: BridgeSnapshot | None = BridgeSnapshot(
            status=BridgeStatus.DISABLED
        )
        try:
            if backend is None:
                raise RuntimeError("controller backend is unavailable")
            if self.platform == XBOX_APP_PLATFORM:
                if not self._platform_supported():
                    bridge_override = BridgeSnapshot(
                        status=BridgeStatus.DISABLED,
                        last_error="Xbox App input bridge requires Windows x64",
                    )
                else:
                    setter = getattr(backend, "set_input_consumer", None)
                    if not callable(setter):
                        bridge_override = BridgeSnapshot(
                            status=BridgeStatus.ERROR,
                            last_error=(
                                "Xbox App input bridge requires direct HID mode; disable DSX"
                            ),
                        )
                    else:
                        self._start_input_activity_monitor()
                        if not self._background_gate_open(gate_generation):
                            self._cleanup_background_children(backend)
                            return
                        self._bridge.start()
                        if not self._background_gate_open(gate_generation):
                            self._cleanup_background_children(backend)
                            return
                        publisher = self._bridge.publish_latest
                        token: object | None = object()
                        with self._lock:
                            if not self._forza_active or not self._forza_gate_enabled:
                                token = None
                            self._background_consumer_token = token
                        if token is None:
                            self._cleanup_background_children(backend)
                            return
                        setter(self._background_input_consumer(token, publisher))
                        if not self._background_gate_open(gate_generation):
                            self._cleanup_background_children(backend)
                            return
                        with self._lock:
                            self._child_session_active = True
                            self._child_session_generation = gate_generation
                        bridge_override = None
        except Exception as exc:
            self._cleanup_background_children(backend)
            if self._background_gate_open():
                with self._lock:
                    self._override = BridgeSnapshot(
                        status=BridgeStatus.ERROR,
                        last_error=str(exc) or type(exc).__name__,
                    )
            log.exception("Could not start the Forza game-facing output session")
            return

        with self._lock:
            if (
                self._forza_active
                and self._forza_gate_enabled
                and gate_generation == self._background_gate_generation
            ):
                self._override = bridge_override
                self._child_session_active = True
                self._child_session_generation = gate_generation
        self._reconcile_hidhide()
        if not self._background_gate_open(gate_generation):
            self._cleanup_background_children(backend)

    def _cleanup_background_children(self, backend) -> None:
        with self._lock:
            self._background_consumer_token = None
            self._background_visibility_token = None
        self._disconnect_backend_callbacks(backend)
        self._bridge.stop()
        self._stop_input_activity_monitor()
        self._apply_hidhide_disabled(
            backend=backend,
            remove_allowlist=not self._hidhide_enabled(),
        )
        with self._lock:
            self._child_session_active = False
            self._child_session_generation = -1
            if not self._forza_active:
                self._override = BridgeSnapshot(status=BridgeStatus.WAITING_GAME)

    def _start_foreground_monitor(self) -> None:
        if not self._background_foreground_monitor:
            return
        with self._lock:
            current = self._foreground_monitor_thread
            if current is not None and current.is_alive():
                if self._foreground_monitor_stop.is_set():
                    self._foreground_monitor_restart_pending = True
                return
            if not self._forza_gate_enabled:
                return
            self._foreground_monitor_restart_pending = False
            self._foreground_monitor_stop.clear()
            self._foreground_monitor_wake.clear()
            thread = threading.Thread(
                target=self._foreground_monitor_loop,
                name="fhds-forza-foreground-gate",
                daemon=True,
            )
            self._foreground_monitor_thread = thread
        thread.start()

    def _stop_foreground_monitor(self) -> None:
        if not self._background_foreground_monitor:
            return
        with self._lock:
            thread = self._foreground_monitor_thread
        if thread is None:
            return
        self._foreground_monitor_stop.set()
        self._foreground_monitor_wake.set()
        if thread is not threading.current_thread():
            thread.join(timeout=self._foreground_monitor_stop_timeout)
        if thread.is_alive():
            log.error(
                "Forza foreground monitor did not stop within %.2f seconds",
                self._foreground_monitor_stop_timeout,
            )
            return
        with self._lock:
            if self._foreground_monitor_thread is thread:
                self._foreground_monitor_thread = None

    def _foreground_monitor_loop(self) -> None:
        try:
            while not self._foreground_monitor_stop.is_set():
                self._foreground_monitor_wake.wait(self._foreground_poll_interval)
                self._foreground_monitor_wake.clear()
                if self._foreground_monitor_stop.is_set():
                    break
                try:
                    self._poll_forza_foreground(force=True)
                except Exception:
                    # _poll_forza_foreground already fails query errors closed.
                    # Keep the detector alive for unexpected publication errors.
                    log.exception("Forza foreground monitor failure")
        finally:
            restart = False
            with self._lock:
                if self._foreground_monitor_thread is threading.current_thread():
                    self._foreground_monitor_thread = None
                    restart = bool(
                        self._foreground_monitor_restart_pending
                        and self._forza_gate_enabled
                    )
                    self._foreground_monitor_restart_pending = False
            if restart:
                self._start_foreground_monitor()

    def _on_bridge_target_state_changed(self, _connected: bool) -> None:
        # The bridge worker must never call HidHide/Win32 lifecycle operations.
        # Wake the service monitor and let its serialized lifecycle reconcile
        # actual target readiness with the isolation setting.
        self._foreground_monitor_wake.set()
        self._request_child_lifecycle_reconcile()

    def sync_hidhide(self) -> HidHideSnapshot:
        """Apply the isolation toggle without recreating the virtual target."""
        with self._lifecycle_lock:
            return self._sync_hidhide()

    def _sync_hidhide(self) -> HidHideSnapshot:
        with self._lock:
            backend = self._backend
        self._apply_hidhide_disabled(
            backend=backend,
            remove_allowlist=not self._hidhide_enabled(),
        )
        self._reconcile_hidhide(force=True)
        return self._hidhide.snapshot()

    def hidhide_snapshot(self) -> HidHideSnapshot:
        return self._hidhide.snapshot()

    def _reconcile_hidhide(self, *, force: bool = False) -> None:
        with self._lock:
            backend = self._backend
            forza_active = self._forza_active
        bridge = self._bridge.snapshot()
        visibility_setter = getattr(backend, "set_device_visibility_observer", None)
        desired = bool(
            self._hidhide_enabled()
            and self.platform == XBOX_APP_PLATFORM
            and forza_active
            and self._platform_supported()
            and callable(getattr(backend, "set_input_consumer", None))
            and callable(visibility_setter)
            and self._bridge_ready_for_hidhide(bridge)
        )
        snapshot = self._hidhide.snapshot()
        consistent = (
            snapshot.phase in {HidHidePhase.READY, HidHidePhase.ACTIVE}
            if desired
            else snapshot.phase is HidHidePhase.DISABLED
        )
        now = self._clock()
        with self._lock:
            applied = self._hidhide_applied
            retry_desired = self._hidhide_retry_desired
            retry_at = self._hidhide_retry_at
        if not force:
            if retry_desired is desired and now < retry_at:
                return
            if retry_desired is None and desired == applied and consistent:
                return

        if not desired:
            self._apply_hidhide_disabled(
                backend=backend,
                remove_allowlist=not self._hidhide_enabled(),
            )
            return

        self._apply_hidhide_enabled(backend)

    @staticmethod
    def _bridge_ready_for_hidhide(snapshot: BridgeSnapshot) -> bool:
        return bool(
            snapshot.target_connected
            and snapshot.status in {BridgeStatus.ACTIVE, BridgeStatus.STALE}
        )

    def _record_hidhide_result(self, desired: bool, success: bool) -> None:
        with self._lock:
            if success:
                self._hidhide_applied = desired
                self._hidhide_retry_desired = None
                self._hidhide_retry_at = 0.0
                return
            self._hidhide_retry_desired = desired
            self._hidhide_retry_at = self._clock() + HIDHIDE_RETRY_S

    def _apply_hidhide_disabled(
        self,
        *,
        backend=None,
        remove_allowlist: bool,
    ) -> bool:
        with self._lock:
            self._background_visibility_token = None
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
            success = False
        else:
            success = bool(
                observer_detached and snapshot.phase is HidHidePhase.DISABLED
            )
        self._record_hidhide_result(False, success)
        return success

    def _apply_hidhide_enabled(self, backend) -> bool:
        bridge = self._bridge.snapshot()
        if not self._hidhide_enabled() or not self._bridge_ready_for_hidhide(bridge):
            self._record_hidhide_result(True, False)
            return False
        visibility_setter = getattr(backend, "set_device_visibility_observer", None)
        if not callable(visibility_setter):
            self._record_hidhide_result(True, False)
            return False
        try:
            driver_ready = bool(self._hidhide_driver_ready())
        except Exception as exc:
            log.warning("Could not probe HidHide readiness: %s", exc)
            driver_ready = False
        if not driver_ready:
            self._record_hidhide_result(True, False)
            return False
        if self._background_foreground_monitor and not self._background_gate_open():
            self._record_hidhide_result(True, False)
            return False

        current = self._hidhide.snapshot()
        if current.phase is HidHidePhase.ERROR:
            if not self._apply_hidhide_disabled(remove_allowlist=False):
                self._record_hidhide_result(True, False)
                return False
        try:
            snapshot = self._hidhide.start()
        except Exception:
            log.exception("Could not start the HidHide isolation session")
            self._record_hidhide_result(True, False)
            return False
        if snapshot.phase not in {HidHidePhase.READY, HidHidePhase.ACTIVE}:
            self._record_hidhide_result(True, False)
            return False
        if self._background_foreground_monitor and not self._background_gate_open():
            self._apply_hidhide_disabled(
                backend=backend,
                remove_allowlist=False,
            )
            self._record_hidhide_result(True, False)
            return False
        observer = self._hidhide.register_device
        if self._background_foreground_monitor:
            token: object | None = object()
            with self._lock:
                if not self._forza_active or not self._forza_gate_enabled:
                    token = None
                self._background_visibility_token = token
            if token is None:
                self._apply_hidhide_disabled(
                    backend=backend,
                    remove_allowlist=False,
                )
                self._record_hidhide_result(True, False)
                return False
            observer = self._background_visibility_observer(token)
        try:
            visibility_setter(observer)
        except Exception:
            log.exception("Could not attach the HidHide visibility observer")
            self._apply_hidhide_disabled(
                backend=backend,
                remove_allowlist=False,
            )
            self._record_hidhide_result(True, False)
            return False
        if self._background_foreground_monitor and not self._background_gate_open():
            self._apply_hidhide_disabled(
                backend=backend,
                remove_allowlist=False,
            )
            self._record_hidhide_result(True, False)
            return False
        self._record_hidhide_result(True, True)
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
        with self._lock:
            gate_enabled = self._forza_gate_enabled
        self._publish_closed_gate()
        self._stop_foreground_monitor()
        self._request_child_lifecycle_stop()
        try:
            with self._lifecycle_lock:
                return self._install_driver(installer, gate_enabled=gate_enabled)
        finally:
            self._join_child_lifecycle_worker()
            self._start_child_lifecycle_worker()
            self._start_foreground_monitor()

    def _install_driver(
        self,
        installer: Callable[[], InstallResult],
        *,
        gate_enabled: bool,
    ) -> InstallResult:
        with self._lock:
            backend = self._backend
            self._forza_active = False
            self._forza_state_known = True
        self._cancel_backend_startup_pulse(backend)
        self._detach_backend()
        self._bridge.stop()
        self._stop_input_activity_monitor()
        self._apply_hidhide_disabled(
            remove_allowlist=not self._hidhide_enabled(),
        )
        with self._lock:
            self._child_session_active = False
            self._child_session_generation = -1
            self._backend = backend
            self._forza_gate_enabled = gate_enabled
            self._forza_active = False
            self._forza_state_known = True
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
            self._forza_gate_enabled = gate_enabled
            self._forza_active = False
            self._forza_state_known = True
            self._last_foreground_poll_at = None
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
        self._publish_closed_gate()
        self._stop_foreground_monitor()
        self._request_child_lifecycle_stop()
        with self._lifecycle_lock:
            self._stop()
        self._join_child_lifecycle_worker()

    def _stop(self) -> None:
        with self._lock:
            self._forza_active = False
            self._forza_state_known = True
            self._preview_requested = False
        self._cancel_backend_startup_pulse(self._backend)
        self._detach_backend()
        self._bridge.stop()
        self._stop_input_activity_monitor()
        self._apply_hidhide_disabled(
            remove_allowlist=not self._hidhide_enabled(),
        )
        with self._lock:
            self._child_session_active = False
            self._child_session_generation = -1
            self._background_consumer_token = None
            self._background_visibility_token = None
            self._backend = None
            self._override = None
            self._forza_gate_enabled = False
            self._forza_active = False
            self._forza_state_known = False
            self._last_foreground_poll_at = None

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

    @staticmethod
    def _cancel_backend_startup_pulse(backend) -> None:
        cancel = getattr(backend, "cancel_startup_pulse", None)
        if callable(cancel):
            try:
                cancel()
            except Exception:
                log.exception("Could not cancel the controller startup pulse")

    @staticmethod
    def _set_backend_runtime_enabled(backend, enabled: bool) -> None:
        setter = getattr(backend, "set_runtime_enabled", None)
        if callable(setter):
            try:
                setter(bool(enabled))
            except Exception:
                log.exception("Could not update physical controller runtime ownership")

    def _start_input_activity_monitor(self) -> None:
        monitor = self._input_activity_monitor
        if monitor is not None and monitor.available:
            monitor.start()

    def _stop_input_activity_monitor(self) -> None:
        monitor = self._input_activity_monitor
        if monitor is not None:
            monitor.stop()
