from modules.dualsense.controller_state import ControllerPhase, ControllerSnapshot
from modules.dualsense.input_state import BatteryStatus, InputTransport
from modules.dualsense.presentation import controller_pill_status


def _t(value):
    return value


def test_connected_pill_shows_transport_charging_and_coarse_battery():
    status = controller_pill_status(
        ControllerSnapshot(
            phase=ControllerPhase.CONNECTED,
            transport=InputTransport.USB,
            battery_level=7,
            battery_status=BatteryStatus.CHARGING,
        ),
        _t,
    )

    assert status.state == "USB"
    assert status.detail == "Charging 70%"
    assert status.low_battery is False


def test_only_discharging_ten_percent_is_low_battery():
    low = controller_pill_status(
        ControllerSnapshot(
            phase=ControllerPhase.CONNECTED,
            transport=InputTransport.BLUETOOTH,
            battery_level=1,
            battery_status=BatteryStatus.DISCHARGING,
        ),
        _t,
    )
    charging = controller_pill_status(
        ControllerSnapshot(
            phase=ControllerPhase.CONNECTED,
            transport=InputTransport.BLUETOOTH,
            battery_level=1,
            battery_status=BatteryStatus.CHARGING,
        ),
        _t,
    )

    assert low.detail == "10%"
    assert low.low_battery is True
    assert charging.low_battery is False


def test_disconnected_pill_cannot_keep_old_transport_or_battery():
    status = controller_pill_status(ControllerSnapshot(), _t)

    assert status.state == "Waiting for controller"
    assert status.detail == ""
