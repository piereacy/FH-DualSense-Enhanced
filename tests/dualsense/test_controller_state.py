from modules.dualsense.controller_state import ControllerPhase, ControllerSnapshot
from modules.dualsense.input_state import BatteryStatus, InputTransport


def test_controller_snapshot_exposes_coarse_battery_and_input_age():
    snapshot = ControllerSnapshot(
        phase=ControllerPhase.CONNECTED,
        transport=InputTransport.BLUETOOTH,
        identity="aabbccddeeff",
        last_input_at=10.0,
        battery_level=7,
        battery_status=BatteryStatus.DISCHARGING,
    )

    assert snapshot.connected is True
    assert snapshot.battery_percent == 70
    assert snapshot.input_age(12.5) == 2.5


def test_waiting_snapshot_cannot_report_stale_connection_or_battery():
    snapshot = ControllerSnapshot()

    assert snapshot.connected is False
    assert snapshot.transport is None
    assert snapshot.battery_percent is None
    assert snapshot.input_age(100.0) is None
