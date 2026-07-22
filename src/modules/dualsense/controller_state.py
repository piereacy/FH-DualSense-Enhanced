from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

from .input_state import BatteryStatus, InputTransport


class ControllerPhase(StrEnum):
    WAITING = "waiting"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SWITCHING = "switching"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ControllerSnapshot:
    phase: ControllerPhase = ControllerPhase.WAITING
    transport: InputTransport | None = None
    identity: str = ""
    last_input_at: float | None = None
    battery_level: int | None = None
    battery_status: BatteryStatus = BatteryStatus.UNKNOWN
    error: str = ""

    @property
    def connected(self) -> bool:
        return self.phase is ControllerPhase.CONNECTED and self.transport is not None

    def input_age(self, now: float | None = None) -> float | None:
        if self.last_input_at is None:
            return None
        return max(0.0, (time.monotonic() if now is None else float(now)) - self.last_input_at)

    @property
    def battery_percent(self) -> int | None:
        if self.battery_level is None:
            return None
        return max(0, min(10, int(self.battery_level))) * 10
