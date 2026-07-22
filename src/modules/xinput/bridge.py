"""Latest-state DualSense to ViGEm Xbox 360 bridge worker."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import logging
import threading
import time
from typing import Callable

from ..dualsense.input_state import DualSenseInputState
from .report import XUSBReport, map_dualsense_to_xusb
from .vigem_client import ViGEmClient, ViGEmError, ViGEmErrorCode


log = logging.getLogger("fhds.xinput")

STALE_AFTER_S = 0.100
RECOVERY_DELAYS_S = (0.25, 1.0, 5.0)


class BridgeStatus(str, Enum):
    DISABLED = "disabled"
    DRIVER_MISSING = "driver_missing"
    INSTALLING = "installing"
    RESTART_REQUIRED = "restart_required"
    WAITING_CONTROLLER = "waiting_controller"
    ACTIVE = "active"
    STALE = "stale"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class BridgeSnapshot:
    status: BridgeStatus = BridgeStatus.DISABLED
    target_connected: bool = False
    received_reports: int = 0
    forwarded_reports: int = 0
    stale_neutralizations: int = 0
    recovery_attempts: int = 0
    last_error: str = ""


@dataclass(frozen=True, slots=True)
class _PublishedInput:
    state: DualSenseInputState
    received_at: float
    sequence: int


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
        self._lock = threading.Lock()
        self._latest: _PublishedInput | None = None
        self._sequence = 0
        self._snapshot = BridgeSnapshot()
        self._wake = threading.Event()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread is not None:
                if self._thread.is_alive():
                    return
                self._thread = None
                self._running = False
            if self._running:
                return
            self._running = True
            self._snapshot = replace(
                self._snapshot,
                status=BridgeStatus.WAITING_CONTROLLER,
                target_connected=False,
                last_error="",
            )
            thread = threading.Thread(
                target=self._run,
                name="fhds-xinput-bridge",
                daemon=True,
            )
            self._thread = thread
        thread.start()

    def publish_latest(
        self,
        state: DualSenseInputState,
        received_at: float | None = None,
    ) -> None:
        timestamp = self._clock() if received_at is None else float(received_at)
        with self._lock:
            self._sequence += 1
            self._latest = _PublishedInput(state, timestamp, self._sequence)
            self._snapshot = replace(
                self._snapshot,
                received_reports=self._snapshot.received_reports + 1,
            )
        self._wake.set()

    def snapshot(self) -> BridgeSnapshot:
        with self._lock:
            return self._snapshot

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            if not self._running and (thread is None or not thread.is_alive()):
                self._thread = None
                self._latest = None
                self._snapshot = replace(
                    self._snapshot,
                    status=BridgeStatus.DISABLED,
                    target_connected=False,
                )
                return
            self._running = False
            self._latest = None
        self._wake.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if thread is not None and thread.is_alive():
            message = "XInput bridge worker did not stop within 2 seconds"
            log.error(message)
            self._replace_snapshot(status=BridgeStatus.ERROR, last_error=message)
            return
        with self._lock:
            if self._thread is thread:
                self._thread = None
            self._snapshot = replace(
                self._snapshot,
                status=BridgeStatus.DISABLED,
                target_connected=False,
            )

    def _is_running(self) -> bool:
        with self._lock:
            return self._running

    def _read_latest(self) -> _PublishedInput | None:
        with self._lock:
            return self._latest

    def _replace_snapshot(self, **changes) -> None:
        with self._lock:
            self._snapshot = replace(self._snapshot, **changes)

    def _run(self) -> None:
        failures = 0
        try:
            while self._is_running():
                client = None
                try:
                    client = self._client_factory()
                    client.connect()
                    self._replace_snapshot(
                        status=BridgeStatus.WAITING_CONTROLLER,
                        target_connected=False,
                        last_error="",
                    )
                    self._run_connected(client)
                    break
                except Exception as exc:
                    if not self._is_running():
                        break
                    status = self._connection_failure_status(exc)
                    if status is BridgeStatus.DRIVER_MISSING:
                        self._replace_snapshot(status=status, last_error=str(exc))
                        log.warning("XInput bridge could not connect: %s", exc)
                        while self._is_running():
                            self._wake.wait(0.5)
                            self._wake.clear()
                        break
                    failures += 1
                    delay = self._recovery_delays[
                        min(failures - 1, len(self._recovery_delays) - 1)
                    ]
                    with self._lock:
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
                    if self._is_running():
                        self._wake.wait(delay)
                finally:
                    if client is not None:
                        try:
                            client.close()
                        except Exception:
                            pass
        finally:
            with self._lock:
                self._running = False
                self._snapshot = replace(self._snapshot, target_connected=False)

    def _run_connected(self, client: ViGEmClient) -> None:
        """Forward one ViGEm session while retaining its player slot on input gaps."""
        target = None
        last_applied_sequence = 0
        stale_sent = False
        try:
            while self._is_running():
                now = self._clock()
                latest = self._read_latest()
                age = float("inf") if latest is None else max(0.0, now - latest.received_at)

                if (
                    latest is not None
                    and latest.sequence != last_applied_sequence
                    and age < self._stale_after
                ):
                    if target is None:
                        target = client.create_x360_target()
                        target.update(XUSBReport())
                    target.update(map_dualsense_to_xusb(latest.state))
                    last_applied_sequence = latest.sequence
                    stale_sent = False
                    with self._lock:
                        self._snapshot = replace(
                            self._snapshot,
                            status=BridgeStatus.ACTIVE,
                            target_connected=True,
                            forwarded_reports=self._snapshot.forwarded_reports + 1,
                            last_error="",
                        )

                if target is not None and age >= self._stale_after and not stale_sent:
                    target.update(XUSBReport())
                    stale_sent = True
                    self._increment_stale_count()
                    self._replace_snapshot(
                        status=BridgeStatus.STALE,
                        target_connected=True,
                    )

                self._wake.clear()
                if not self._is_running():
                    break
                if self._read_latest() is not latest:
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

    def _increment_stale_count(self) -> None:
        with self._lock:
            self._snapshot = replace(
                self._snapshot,
                stale_neutralizations=self._snapshot.stale_neutralizations + 1,
            )

    def _next_wait(self, age: float, has_target: bool, stale_sent: bool) -> float:
        if not has_target:
            return 0.5
        if stale_sent:
            return 0.5
        return max(0.001, min(0.5, self._stale_after - age))

    @staticmethod
    def _connection_failure_status(exc: Exception) -> BridgeStatus:
        if isinstance(exc, ViGEmError) and exc.code in _DRIVER_UNAVAILABLE_CODES:
            return BridgeStatus.DRIVER_MISSING
        return BridgeStatus.ERROR
