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


@dataclass(frozen=True, slots=True)
class ControllerDiagnosticsSnapshot:
    connection_enumeration_count: int = 0
    last_enumeration_interface_count: int | None = None
    open_attempt_count: int = 0
    successful_open_count: int = 0
    valid_input_report_count: int = 0
    rejected_input_report_count: int = 0
    output_write_count: int = 0
    output_write_failure_count: int = 0
    reconnect_request_count: int = 0
    io_recovery_count: int = 0
    bluetooth_haptics_queued_count: int = 0
    bluetooth_haptics_dropped_count: int = 0
    bluetooth_haptics_failed: bool = False
    last_valid_input_age_s: float | None = None
    input_consumer_attached: bool = False
    worker_alive: bool = False
    product_id: int | None = None
