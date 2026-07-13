from modules.dualsense.adaptive_trigger import rigid, vibrate
from modules.dualsense import main as dualsense_main
from modules.haptics.frame import CompatibleRumble


class _Device:
    def __init__(self):
        self.path = None
        self.nonblocking = None
        self.writes = []
        self.closed = False

    def open_path(self, path):
        self.path = path

    def set_nonblocking(self, enabled):
        self.nonblocking = enabled

    def write(self, report):
        self.writes.append(bytes(report))
        return len(report)

    def close(self):
        self.closed = True


def test_reconnect_requeues_the_last_trigger_and_rumble_frame(monkeypatch):
    device = _Device()
    info = {
        "path": b"bluetooth-controller",
        "product_id": dualsense_main.PRODUCT_IDS[0],
        "serial_number": "001122334455",
        "bus_type": 2,
        "usage_page": 1,
        "usage": 5,
    }
    monkeypatch.setattr(dualsense_main, "_enumerate_dualsenses", lambda: [info])
    monkeypatch.setattr(dualsense_main.hid, "device", lambda: device)
    monkeypatch.setattr(dualsense_main.hidhide, "is_detected", lambda: False)

    controller = dualsense_main.DualSense(
        enable_startup_pulse=False,
        enable_reconnect=True,
    )
    left = rigid(40)
    right = vibrate(20, 10)
    rumble = CompatibleRumble(low_frequency=0.3, high_frequency=0.2)
    controller.set(left, right, rumble)
    controller._dirty = False  # Simulate the frame having been sent before a drop.

    assert controller._try_connect() is True

    assert controller._left == left
    assert controller._right == right
    assert controller._rumble == rumble
    assert controller._dirty is True
    assert controller._wake.is_set()


def test_disconnect_explicitly_zeros_owned_compatible_rumble():
    device = _Device()
    controller = dualsense_main.DualSense(enable_startup_pulse=False)
    controller.dev = device
    controller.lay = dualsense_main.BT
    controller._rumble = CompatibleRumble(low_frequency=0.8, high_frequency=0.4)

    controller._disconnect()

    report = device.writes[-1]
    assert report[dualsense_main.BT["flags"]] == (
        dualsense_main.TRIG_FLAGS | dualsense_main.RUMBLE_FLAGS
    )
    assert report[dualsense_main.BT["motor_l"]] == 0
    assert report[dualsense_main.BT["motor_r"]] == 0
    assert device.closed is True
