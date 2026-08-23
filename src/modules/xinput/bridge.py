"""Latest-state DualSense to ViGEm Xbox 360 bridge worker."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import logging
import threading
import time
from typing import Callable, Protocol

from ..dualsense.input_state import DualSenseInputState
from .hot_switch import controller_input_changed, controller_input_is_active
from .gyro import (
    DEFAULT_GYRO_MAPPING,
    GyroToJoystickProcessor,
    XInputGyroMapping,
    gyro_input_is_active,
)
from .mapping import DEFAULT_BUTTON_MAPPING, XInputButtonMapping
from .report import XUSBReport, map_dualsense_to_xusb
from .vigem_client import ViGEmClient, ViGEmError, ViGEmErrorCode


log = logging.getLogger("fhds.xinput")

STALE_AFTER_S = 0.100
KEYBOARD_MOUSE_POLL_S = 0.050
RECOVERY_DELAYS_S = (0.25, 1.0, 5.0)
WORKER_STOP_TIMEOUT_S = 2.0


class BridgeStatus(str, Enum):
    DISABLED = "disabled"
    DRIVER_MISSING = "driver_missing"
    INSTALLING = "installing"
    RESTART_REQUIRED = "restart_required"
    WAITING_CONTROLLER = "waiting_controller"
    ACTIVE = "active"
    STALE = "stale"
    ERROR = "error"


class InputOwner(str, Enum):
    CONTROLLER = "controller"
    KEYBOARD_MOUSE = "keyboard_mouse"


@dataclass(frozen=True, slots=True)
class BridgeSnapshot:
    status: BridgeStatus = BridgeStatus.DISABLED
    target_connected: bool = False
    received_reports: int = 0
    forwarded_reports: int = 0
    stale_neutralizations: int = 0
    recovery_attempts: int = 0
    input_owner: InputOwner = InputOwner.CONTROLLER
    last_error: str = ""


@dataclass(frozen=True, slots=True)
class _PublishedInput:
    state: DualSenseInputState
    received_at: float
    sequence: int
    generation: int


class _InputPublisher(Protocol):
    def __call__(
        self,
        state: DualSenseInputState,
        received_at: float | None = None,
    ) -> None: ...


_DRIVER_UNAVAILABLE_CODES = frozenset(
    {
        ViGEmErrorCode.BUS_NOT_FOUND,
        ViGEmErrorCode.BUS_VERSION_MISMATCH,
        ViGEmErrorCode.BUS_ACCESS_FAILED,
    }
)


class XInputBridge:
    """Own a ViGEm client/target on one worker and discard input backlog."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], ViGEmClient] = ViGEmClient,
        clock: Callable[[], float] = time.monotonic,
        stale_after_s: float = STALE_AFTER_S,
        recovery_delays_s: tuple[float, ...] = RECOVERY_DELAYS_S,
        keyboard_mouse_activity: Callable[[], bool] | None = None,
    ):
        self._client_factory = client_factory
        self._clock = clock
        self._stale_after = float(stale_after_s)
        if self._stale_after <= 0:
            raise ValueError("stale timeout must be positive")
        delays = tuple(max(0.001, float(delay)) for delay in recovery_delays_s)
        if not delays:
            raise ValueError("at least one recovery delay is required")
        self._recovery_delays = delays
        self._keyboard_mouse_activity = keyboard_mouse_activity
        self._lock = threading.Lock()
        self._latest: _PublishedInput | None = None
        self._sequence = 0
        self._button_mapping = DEFAULT_BUTTON_MAPPING
        self._gyro_mapping = DEFAULT_GYRO_MAPPING
        self._mapping_revision = 0
        self._snapshot = BridgeSnapshot()
        self._wake = threading.Event()
        self._running = False
        self._thread: threading.Thread | None = None
        self._session_generation = 0
        self._publisher: _InputPublisher = self._publisher_for_generation(0)
        self._restart_pending = False
        self._input_owner = InputOwner.CONTROLLER
        self._controller_resume_baseline: DualSenseInputState | None = None
        self._controller_resume_motion_active = False
        self._target_state_callback: Callable[[bool], None] | None = None

    def set_target_state_callback(
        self,
        callback: Callable[[bool], None] | None,
    ) -> None:
        """Publish actual virtual-target readiness without transferring ownership.

        The callback is only an edge notification. It must not call ViGEm or
        block this worker; the application service uses it to wake its own
        HidHide lifecycle reconciler.
        """
        with self._lock:
            self._target_state_callback = callback

    def _notify_target_state(self, connected: bool) -> None:
        with self._lock:
            callback = self._target_state_callback
        if callback is None:
            return
        try:
            callback(bool(connected))
        except Exception:
            log.exception("XInput target-state observer failed")

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            thread = self._thread
            if thread is not None:
                if thread.is_alive():
                    self._begin_session_locked()
                    self._restart_pending = True
                    return
                self._thread = None
            generation = self._begin_session_locked()
            self._restart_pending = False
            self._start_worker_locked(generation)

    def _begin_session_locked(self) -> int:
        self._session_generation += 1
        generation = self._session_generation
        self._publisher = self._publisher_for_generation(generation)
        self._running = True
        self._latest = None
        self._input_owner = InputOwner.CONTROLLER
        self._controller_resume_baseline = None
        self._controller_resume_motion_active = False
        self._snapshot = replace(
            self._snapshot,
            status=BridgeStatus.WAITING_CONTROLLER,
            target_connected=False,
            input_owner=InputOwner.CONTROLLER,
            last_error="",
        )
        return generation

    def _start_worker_locked(self, generation: int) -> None:
        thread = threading.Thread(
            target=self._run,
            args=(generation,),
            name="fhds-xinput-bridge",
            daemon=True,
        )
        self._thread = thread
        # Starting while holding the state lock closes the small window where a
        # concurrent start could mistake this not-yet-started thread for dead.
        thread.start()

    @property
    def publish_latest(self) -> _InputPublisher:
        """Return the publisher bound to the current bridge session.

        The physical HID worker may already have copied a consumer while the
        service detaches it. Rotating this callable on every real start keeps
        such a late callback from publishing into a newer bridge session.
        """
        with self._lock:
            return self._publisher

    def _publisher_for_generation(self, generation: int) -> _InputPublisher:
        def publish(
            state: DualSenseInputState,
            received_at: float | None = None,
        ) -> None:
            self._publish_latest(generation, state, received_at)

        return publish

    def _publish_latest(
        self,
        generation: int,
        state: DualSenseInputState,
        received_at: float | None = None,
    ) -> None:
        with self._lock:
            if not self._running or generation != self._session_generation:
                return
        timestamp = self._clock() if received_at is None else float(received_at)
        with self._lock:
            # stop() can close the session while the timestamp is being
            # normalized, so validate the generation again before publishing.
            if not self._running or generation != self._session_generation:
                return
            self._sequence += 1
            self._latest = _PublishedInput(
                state,
                timestamp,
                self._sequence,
                generation,
            )
            self._snapshot = replace(
                self._snapshot,
                received_reports=self._snapshot.received_reports + 1,
            )
        self._wake.set()

    def snapshot(self) -> BridgeSnapshot:
        with self._lock:
            return self._snapshot

    def set_button_mapping(self, mapping: XInputButtonMapping) -> None:
        """Atomically replace the map and re-apply the latest live input."""
        if not isinstance(mapping, XInputButtonMapping):
            raise TypeError("mapping must be an XInputButtonMapping")
        with self._lock:
            if self._button_mapping == mapping:
                return
            self._button_mapping = mapping
            self._mapping_revision += 1
        self._wake.set()

    def set_gyro_mapping(self, mapping: XInputGyroMapping) -> None:
        """Atomically replace motion conversion and reset its session state."""
        if not isinstance(mapping, XInputGyroMapping):
            raise TypeError("mapping must be an XInputGyroMapping")
        with self._lock:
            if self._gyro_mapping == mapping:
                return
            self._gyro_mapping = mapping
            self._mapping_revision += 1
        self._wake.set()

    def stop(self) -> None:
        notify_disconnected = False
        with self._lock:
            stopped_generation = self._session_generation
            self._restart_pending = False
            thread = self._thread
            if not self._running and (thread is None or not thread.is_alive()):
                self._thread = None
                self._latest = None
                notify_disconnected = self._snapshot.target_connected
                self._snapshot = replace(
                    self._snapshot,
                    status=BridgeStatus.DISABLED,
                    target_connected=False,
                    input_owner=InputOwner.CONTROLLER,
                )
                thread = None
            else:
                self._running = False
                self._latest = None
        if notify_disconnected:
            self._notify_target_state(False)
        if thread is None:
            return
        self._wake.set()

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=WORKER_STOP_TIMEOUT_S)
        if thread is not None and thread.is_alive():
            message = (
                "XInput bridge worker did not stop within "
                f"{WORKER_STOP_TIMEOUT_S:g} seconds"
            )
            log.error(message)
            with self._lock:
                # A newer start may have registered a successor while this
                # stop() was waiting for the old worker. Do not overwrite the
                # new session's pending state.
                if (
                    self._session_generation != stopped_generation
                    or self._running
                ):
                    return
                notify_disconnected = self._snapshot.target_connected
                self._snapshot = replace(
                    self._snapshot,
                    status=BridgeStatus.ERROR,
                    target_connected=False,
                    last_error=message,
                )
            if notify_disconnected:
                self._notify_target_state(False)
            return
        with self._lock:
            if (
                self._session_generation != stopped_generation
                or self._running
            ):
                return
            if self._thread is thread:
                self._thread = None
            self._snapshot = replace(
                self._snapshot,
                status=BridgeStatus.DISABLED,
                target_connected=False,
                input_owner=InputOwner.CONTROLLER,
            )

    def _is_running(self, generation: int) -> bool:
        with self._lock:
            return self._session_is_running_locked(generation)

    def _session_is_running_locked(self, generation: int) -> bool:
        return self._running and generation == self._session_generation

    def _read_latest_mapping(
        self,
        generation: int,
    ) -> tuple[_PublishedInput | None, XInputButtonMapping, XInputGyroMapping, int]:
        with self._lock:
            latest = self._latest
            if latest is not None and latest.generation != generation:
                latest = None
            return (
                latest,
                self._button_mapping,
                self._gyro_mapping,
                self._mapping_revision,
            )

    def _replace_snapshot_for_generation(self, generation: int, **changes) -> bool:
        with self._lock:
            if not self._session_is_running_locked(generation):
                return False
            self._snapshot = replace(self._snapshot, **changes)
            return True

    def _run(self, generation: int) -> None:
        failures = 0
        try:
            while self._is_running(generation):
                client = None
                try:
                    client = self._client_factory()
                    client.connect()
                    if not self._replace_snapshot_for_generation(
                        generation,
                        status=BridgeStatus.WAITING_CONTROLLER,
                        target_connected=False,
                        last_error="",
                    ):
                        break
                    self._run_connected(client, generation)
                    break
                except Exception as exc:
                    if not self._is_running(generation):
                        break
                    status = self._connection_failure_status(exc)
                    if status is BridgeStatus.DRIVER_MISSING:
                        self._replace_snapshot_for_generation(
                            generation,
                            status=status,
                            last_error=str(exc),
                        )
                        log.warning("XInput bridge could not connect: %s", exc)
                        while self._is_running(generation):
                            self._wake.wait(0.5)
                            self._wake.clear()
                        break
                    failures += 1
                    delay = self._recovery_delays[
                        min(failures - 1, len(self._recovery_delays) - 1)
                    ]
                    with self._lock:
                        if not self._session_is_running_locked(generation):
                            break
                        self._snapshot = replace(
                            self._snapshot,
                            status=BridgeStatus.ERROR,
                            target_connected=False,
                            recovery_attempts=self._snapshot.recovery_attempts + 1,
                            last_error=str(exc) or type(exc).__name__,
                        )
                    log.exception(
                        "XInput bridge session failed; retrying in %.2fs",
                        delay,
                    )
                    self._wake.clear()
                    if self._is_running(generation):
                        self._wake.wait(delay)
                finally:
                    if client is not None:
                        try:
                            client.close()
                        except Exception:
                            pass
        finally:
            notify_disconnected = False
            with self._lock:
                current_thread = threading.current_thread()
                if self._thread is current_thread:
                    if (
                        self._running
                        and self._restart_pending
                        and generation != self._session_generation
                    ):
                        successor_generation = self._session_generation
                        self._restart_pending = False
                        self._start_worker_locked(successor_generation)
                    else:
                        self._thread = None
                        if generation == self._session_generation:
                            self._running = False
                            self._restart_pending = False
                            notify_disconnected = self._snapshot.target_connected
                            self._snapshot = replace(
                                self._snapshot,
                                target_connected=False,
                            )
            if notify_disconnected:
                self._notify_target_state(False)

    def _run_connected(self, client: ViGEmClient, generation: int) -> None:
        """Forward one ViGEm session while retaining its player slot on input gaps."""
        target = None
        last_applied_sequence = 0
        last_mapping_revision = -1
        stale_sent = False
        gyro_processor = GyroToJoystickProcessor()
        try:
            while self._is_running(generation):
                now = self._clock()
                latest, mapping, gyro_mapping, mapping_revision = (
                    self._read_latest_mapping(generation)
                )
                gyro_processor.set_mapping(gyro_mapping)
                age = float("inf") if latest is None else max(0.0, now - latest.received_at)

                if self._poll_keyboard_mouse_activity():
                    if not self._activate_keyboard_mouse(
                        latest,
                        target,
                        generation,
                    ):
                        break

                with self._lock:
                    if not self._session_is_running_locked(generation):
                        break
                    input_owner = self._input_owner

                should_forward = (
                    latest is not None
                    and (
                        latest.sequence != last_applied_sequence
                        or mapping_revision != last_mapping_revision
                    )
                    and age < self._stale_after
                )
                if (
                    should_forward
                    and input_owner is InputOwner.KEYBOARD_MOUSE
                    and not self._controller_reclaims_input(latest, generation)
                ):
                    should_forward = False

                if should_forward:
                    if target is None:
                        target = client.create_x360_target()
                        target.update(XUSBReport())
                    gyro_axes = gyro_processor.update(
                        latest.state,
                        latest.received_at,
                    )
                    target.update(
                        map_dualsense_to_xusb(
                            latest.state,
                            mapping,
                            gyro_axes=gyro_axes,
                            gyro_stick=gyro_mapping.output_stick.value,
                        )
                    )
                    last_applied_sequence = latest.sequence
                    last_mapping_revision = mapping_revision
                    stale_sent = False
                    with self._lock:
                        # stop() may have timed out while a native target update
                        # was still in flight. Never let that old worker publish
                        # readiness again after the logical session closed.
                        if not self._session_is_running_locked(generation):
                            continue
                        notify_connected = not self._snapshot.target_connected
                        self._snapshot = replace(
                            self._snapshot,
                            status=BridgeStatus.ACTIVE,
                            target_connected=True,
                            forwarded_reports=self._snapshot.forwarded_reports + 1,
                            last_error="",
                        )
                    if notify_connected:
                        self._notify_target_state(True)

                if latest is not None and age >= self._stale_after:
                    # A new physical sample after a gap must begin a fresh
                    # Deflection integration session. Never carry an old pose
                    # through a neutralized/stalled HID stream.
                    gyro_processor.reset()

                if (
                    input_owner is InputOwner.CONTROLLER
                    and target is not None
                    and age >= self._stale_after
                    and not stale_sent
                ):
                    target.update(XUSBReport())
                    with self._lock:
                        if not self._session_is_running_locked(generation):
                            continue
                        stale_sent = True
                        self._snapshot = replace(
                            self._snapshot,
                            status=BridgeStatus.STALE,
                            target_connected=True,
                            stale_neutralizations=(
                                self._snapshot.stale_neutralizations + 1
                            ),
                        )

                self._wake.clear()
                if not self._is_running(generation):
                    break
                current_latest, _current_mapping, _current_gyro, current_revision = (
                    self._read_latest_mapping(generation)
                )
                if current_latest is not latest or current_revision != mapping_revision:
                    continue
                self._wake.wait(self._next_wait(age, target is not None, stale_sent))
        finally:
            if target is not None:
                try:
                    target.update(XUSBReport())
                except Exception:
                    pass
                try:
                    target.close()
                except Exception:
                    pass
                with self._lock:
                    notify_disconnected = False
                    if generation == self._session_generation:
                        notify_disconnected = self._snapshot.target_connected
                        self._snapshot = replace(
                            self._snapshot,
                            target_connected=False,
                        )
                if notify_disconnected:
                    self._notify_target_state(False)

    def _poll_keyboard_mouse_activity(self) -> bool:
        detector = self._keyboard_mouse_activity
        if detector is None:
            return False
        try:
            return bool(detector())
        except Exception as exc:
            self._keyboard_mouse_activity = None
            log.warning(
                "Keyboard/mouse hot-switch monitor failed; controller forwarding remains active: %s",
                exc,
            )
            return False

    def _activate_keyboard_mouse(
        self,
        latest: _PublishedInput | None,
        target,
        generation: int,
    ) -> bool:
        with self._lock:
            if not self._session_is_running_locked(generation):
                return False
            changed = self._input_owner is not InputOwner.KEYBOARD_MOUSE
            self._input_owner = InputOwner.KEYBOARD_MOUSE
            self._controller_resume_baseline = (
                latest.state if latest is not None else None
            )
            self._controller_resume_motion_active = bool(
                latest is not None
                and gyro_input_is_active(latest.state, self._gyro_mapping)
            )
            if changed:
                self._snapshot = replace(
                    self._snapshot,
                    input_owner=InputOwner.KEYBOARD_MOUSE,
                )
        if not changed:
            return True
        log.info("Keyboard/mouse input active; virtual Xbox controller neutralized")
        if target is not None:
            target.update(XUSBReport())
        return True

    def _controller_reclaims_input(
        self,
        latest: _PublishedInput,
        generation: int,
    ) -> bool:
        with self._lock:
            if not self._session_is_running_locked(generation):
                return False
            baseline = self._controller_resume_baseline
            changed = (
                controller_input_is_active(latest.state)
                if baseline is None
                else controller_input_changed(baseline, latest.state)
            )
            if not changed:
                # Only motion that began after keyboard/mouse took ownership
                # may reclaim it. A controller already rotating when the key
                # event arrived must not immediately undo the handover.
                current_motion = gyro_input_is_active(
                    latest.state,
                    self._gyro_mapping,
                )
                changed = (
                    current_motion
                    and not self._controller_resume_motion_active
                )
                self._controller_resume_motion_active = current_motion
            if not changed:
                return False
            self._input_owner = InputOwner.CONTROLLER
            self._controller_resume_baseline = None
            self._controller_resume_motion_active = False
            self._snapshot = replace(
                self._snapshot,
                input_owner=InputOwner.CONTROLLER,
            )
        log.info("DualSense input active; virtual Xbox controller resumed")
        return True

    def _next_wait(self, age: float, has_target: bool, stale_sent: bool) -> float:
        if not has_target:
            wait = 0.5
        elif stale_sent:
            wait = 0.5
        else:
            wait = max(0.001, min(0.5, self._stale_after - age))
        if self._keyboard_mouse_activity is not None:
            wait = min(wait, KEYBOARD_MOUSE_POLL_S)
        return wait

    @staticmethod
    def _connection_failure_status(exc: Exception) -> BridgeStatus:
        if isinstance(exc, ViGEmError) and exc.code in _DRIVER_UNAVAILABLE_CODES:
            return BridgeStatus.DRIVER_MISSING
        return BridgeStatus.ERROR
