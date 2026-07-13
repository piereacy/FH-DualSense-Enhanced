from modules.dsx import DSXClient
from modules.dsx import dsx_wrapper
from modules.dualsense.adaptive_trigger import rigid, vibrate


def test_set_accepts_and_ignores_native_rumble_argument(monkeypatch):
    client = DSXClient(enable_startup_pulse=False)
    sent = []
    monkeypatch.setattr(client, "_send", sent.append)
    left = rigid(30)
    right = vibrate(20, 10)

    client.set(left, right, None)

    assert sent == [dsx_wrapper.frames_to_packet(left, right)]
