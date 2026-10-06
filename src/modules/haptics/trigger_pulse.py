"""Latest bounded UI feedback request, consumed by the telemetry output owner."""

import threading
import time
from dataclasses import dataclass

from modules.dualsense.adaptive_trigger import rigid, vibrate
from modules.dualsense.main import _normalise_identity
from modules.dualsense.output_state import TriggerOutputGuard


@dataclass(frozen=True, slots=True)
class PulseOutput:
    effect: tuple
    guard: TriggerOutputGuard | None = None


class TriggerPulse:
    def __init__(self):
        self._lock = threading.Lock()
        self._amplitude: int | None = None
        self._started_at: float | None = None
        self._identification = None

    def request(self, on_state: bool) -> None:
        with self._lock:
            self._amplitude = 200 if on_state else 120
            self._started_at = None
            self._identification = None

    def identify(self, controller, serial: str, *, force: int, now: float | None = None) -> bool:
        """Identify an already owned native connection; never open or await one."""
        self.stop()
        if controller is None or getattr(controller, "is_dsx", False):
            return False
        snapshot = controller.snapshot()
        identity = _normalise_identity(serial)
        if not identity or not snapshot.connected or snapshot.identity != identity:
            return False
        timestamp = time.monotonic() if now is None else now
        with self._lock:
            self._identification = (
                controller, snapshot.connection_generation, identity,
                timestamp + 0.75, rigid(force),
            )
        return True

    def stop(self) -> None:
        with self._lock:
            self._amplitude = None
            self._started_at = None
            self._identification = None

    def sample_output(self, *, now: float, controller=None) -> PulseOutput | None:
        with self._lock:
            if self._identification is not None:
                owner, generation, identity, deadline, effect = self._identification
                snapshot = controller.snapshot() if controller is owner else None
                if (
                    snapshot is None or not snapshot.connected
                    or snapshot.connection_generation != generation
                    or snapshot.identity != identity or now >= deadline
                ):
                    self._identification = None
                    self._started_at = None
                    return None
                if self._started_at is None:
                    self._started_at = now
                expires_at = min(deadline, self._started_at + 0.2)
                if now >= expires_at:
                    self._identification = None
                    self._started_at = None
                    return None
                return PulseOutput(effect, TriggerOutputGuard(generation, expires_at))
            if self._amplitude is None:
                return None
            if self._started_at is None:
                self._started_at = now
            if now - self._started_at >= 0.1:
                self._amplitude = None
                self._started_at = None
                return None
            return PulseOutput(vibrate(40, self._amplitude))

    def sample(self, *, now: float, controller=None):
        output = self.sample_output(now=now, controller=controller)
        return output.effect if output is not None else None
