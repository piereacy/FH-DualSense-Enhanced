from modules.dsx import DSXClient
from modules.dsx import dsx_wrapper
from modules.dualsense.adaptive_trigger import off, rigid, vibrate, vibrate_zones


def test_set_accepts_and_ignores_native_rumble_argument(monkeypatch):
    client = DSXClient(enable_startup_pulse=False)
    sent = []
    monkeypatch.setattr(client, "_send", sent.append)
    left = rigid(30)
    right = vibrate(20, 10)

    client.set(left, right, None)

    assert sent == [dsx_wrapper.frames_to_packet(left, right)]


def test_zoned_abs_wall_falls_back_to_dynamic_vibration_in_dsx():
    packet = dsx_wrapper.frames_to_packet(vibrate_zones(3, 42, 3), off())

    left = packet["instructions"][0]
    assert left["parameters"] == [
        0,
        dsx_wrapper.T_LEFT,
        dsx_wrapper.TM_VIBRATE,
        42,
    ]
