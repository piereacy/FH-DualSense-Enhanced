from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .controller_state import ControllerPhase, ControllerSnapshot
from .input_state import BatteryStatus


@dataclass(frozen=True, slots=True)
class ControllerPillStatus:
    state: str
    detail: str = ""
    low_battery: bool = False


def controller_pill_status(
    snapshot: ControllerSnapshot,
    translate: Callable[[str], str],
) -> ControllerPillStatus:
    if snapshot.phase is ControllerPhase.CONNECTED and snapshot.transport is not None:
        transport = "BT" if snapshot.transport.value == "bluetooth" else "USB"
        percent = snapshot.battery_percent
        if snapshot.battery_status is BatteryStatus.FULL:
            detail = translate("Fully charged")
        elif snapshot.battery_status is BatteryStatus.CHARGING:
            detail = (
                translate("Charging {percent}%").format(percent=percent)
                if percent is not None
                else translate("Charging")
            )
        elif snapshot.battery_status is BatteryStatus.DISCHARGING and percent is not None:
            detail = f"{percent}%"
        elif snapshot.battery_status is BatteryStatus.NOT_CHARGING:
            detail = translate("Battery unavailable")
        else:
            detail = translate("Reading battery")
        return ControllerPillStatus(
            transport,
            detail,
            snapshot.battery_status is BatteryStatus.DISCHARGING and percent == 10,
        )
    if snapshot.phase is ControllerPhase.SWITCHING:
        return ControllerPillStatus(translate("Switching connection"))
    if snapshot.phase is ControllerPhase.RECONNECTING:
        return ControllerPillStatus(translate("Reconnecting"))
    if snapshot.phase is ControllerPhase.CONNECTING:
        return ControllerPillStatus(translate("Connecting"))
    if snapshot.phase is ControllerPhase.ERROR:
        return ControllerPillStatus(translate("Connection error"))
    return ControllerPillStatus(translate("Waiting for controller"))
