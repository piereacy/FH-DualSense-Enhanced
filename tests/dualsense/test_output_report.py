import struct
import threading
import time
import zlib

import pytest

from modules.dualsense.adaptive_trigger import rigid, vibrate
from modules.dualsense.controller_state import ControllerPhase
from modules.dualsense.input_state import InputTransport
from modules.dualsense.main import (
    BT,
    RUMBLE_FLAGS,
    TRIG_FLAGS,
    USB,
    DualSense,
    _BT_CRC_SEED,
)
from modules.dualsense.output_state import ControllerVisualState, NO_VISUAL_CONTROL
from modules.haptics.frame import CompatibleRumble


LEFT = vibrate(20, 30)
RIGHT = rigid(40)


def _input_report(transport):
    bluetooth = transport is InputTransport.BLUETOOTH
    report = bytearray(BT["size"] if bluetooth else USB["size"])
    report[0] = 0x31 if bluetooth else 0x01
    base = 2 if bluetooth else 1
    report[base + 7] = 8
    if bluetooth:
        crc = zlib.crc32(memoryview(report)[:74], zlib.crc32(b"\xA1"))
        struct.pack_into("<I", report, 74, crc)
    return bytes(report)


def _mark_connected(controller, transport):
    controller.lay = BT if transport is InputTransport.BLUETOOTH else USB
    now = time.monotonic()
    controller._last_input_at = now
    controller._ever_connected = True
    controller._update_snapshot(
        phase=ControllerPhase.CONNECTED,
        transport=transport,
        last_input_at=now,
    )


class _GatedDevice:
    def __init__(self, read_count, transport=InputTransport.BLUETOOTH):
        self.read_entered = [threading.Event() for _ in range(read_count)]
        self.read_released = [threading.Event() for _ in range(read_count)]
        self.writes = []
        self.closed = False
        self._next_read = 0
        self._writes_changed = threading.Condition()
        self._report = _input_report(transport)

    def read(self, _size, timeout_ms=0):
        assert timeout_ms == 0
        index = self._next_read
        self._next_read += 1
        self.read_entered[index].set()
        assert self.read_released[index].wait(timeout=2.0)
        return self._report

    def write(self, report):
        with self._writes_changed:
            self.writes.append(bytes(report))
            self._writes_changed.notify_all()
        return len(report)

    def wait_for_writes(self, count):
        with self._writes_changed:
            return self._writes_changed.wait_for(
                lambda: len(self.writes) >= count,
                timeout=2.0,
            )

    def close(self):
        self.closed = True


def _legacy_report(layout, left=LEFT, right=RIGHT):
    report = bytearray(layout["size"])
    report[0] = layout["rid"]
    if layout["bt"]:
        report[1] = 0x02
    report[layout["flags"]] = TRIG_FLAGS
    for position, (mode, params) in ((layout["r"], right), (layout["l"], left)):
        report[position] = mode
        report[position + 1:position + 1 + len(params)] = params[:10]
    if layout["bt"]:
        crc = zlib.crc32(memoryview(report)[:74], _BT_CRC_SEED)
        struct.pack_into("<I", report, 74, crc)
    return report


@pytest.mark.parametrize("layout", [USB, BT], ids=["usb", "bluetooth"])
def test_trigger_only_report_matches_legacy_bytes(layout):
    controller = DualSense(enable_startup_pulse=False)
    controller.lay = layout

    assert controller._build(LEFT, RIGHT) == _legacy_report(layout)


def test_usb_trigger_only_layout_is_unchanged():
    controller = DualSense(enable_startup_pulse=False)
    controller.lay = USB
    report = controller._build(LEFT, RIGHT)

    assert len(report) == 64
    assert report[0] == 0x02
    assert report[1] == TRIG_FLAGS
    assert report[3:5] == b"\x00\x00"
    assert report[11:14] == bytes((RIGHT[0], 0, 40))
    assert report[22:25] == bytes((LEFT[0], 20, 30))


@pytest.mark.parametrize("layout", [USB, BT], ids=["usb", "bluetooth"])
@pytest.mark.parametrize(
    "rumble",
    [None, CompatibleRumble(low_frequency=0.5, high_frequency=0.25)],
    ids=["trigger-only", "compatible-rumble"],
)
def test_state_reports_never_claim_unverified_audio_control_fields(layout, rumble):
    controller = DualSense(enable_startup_pulse=False)
    controller.lay = layout

    report = controller._build(LEFT, RIGHT, rumble)

    assert report[layout["flags"]] & 0x20 == 0
    assert report[layout["vf1"]] & 0x20 == 0


def test_bluetooth_trigger_only_layout_and_crc_are_unchanged():
    controller = DualSense(enable_startup_pulse=False)
    controller.lay = BT
    report = controller._build(LEFT, RIGHT)

    assert len(report) == 78
    assert report[0] == 0x31
    assert report[1] == 0x02
    assert report[2] == TRIG_FLAGS
    assert report[4:6] == b"\x00\x00"
    assert report[12:15] == bytes((RIGHT[0], 0, 40))
    assert report[23:26] == bytes((LEFT[0], 20, 30))
    expected_crc = zlib.crc32(memoryview(report)[:74], _BT_CRC_SEED)
    assert struct.unpack_from("<I", report, 74)[0] == expected_crc


@pytest.mark.parametrize("layout", [USB, BT], ids=["usb", "bluetooth"])
def test_optional_visual_state_claims_only_lighting_fields(layout):
    controller = DualSense(enable_startup_pulse=False)
    controller.lay = layout
    visual = ControllerVisualState(lightbar=(57, 197, 187), player_leds=0x15)

    report = controller._build(LEFT, RIGHT, visual=visual)

    assert report[layout["flags"]] == TRIG_FLAGS
    assert report[layout["vf1"]] == 0x14
    assert report[layout["vf2"]] == 0x02
    assert report[layout["lb_setup"]] == 0x02
    assert report[layout["player_leds"]] == 0x35
    assert tuple(report[layout["lb_r"]:layout["lb_b"] + 1]) == (57, 197, 187)
    if layout["bt"]:
        expected_crc = zlib.crc32(memoryview(report)[:74], _BT_CRC_SEED)
        assert struct.unpack_from("<I", report, 74)[0] == expected_crc


def test_visual_state_normalizes_out_of_range_values():
    visual = ControllerVisualState(
        lightbar=(-5, 300, 100.4),
        player_leds=0xFF,
    ).normalized()

    assert visual.lightbar == (0, 255, 100)
    assert visual.player_leds == 0x1F


@pytest.mark.parametrize("layout", [USB, BT], ids=["usb", "bluetooth"])
def test_compatible_rumble_is_encoded_with_triggers(layout):
    controller = DualSense(enable_startup_pulse=False)
    controller.lay = layout
    rumble = CompatibleRumble(low_frequency=0.5, high_frequency=0.25)

    report = controller._build(LEFT, RIGHT, rumble)

    assert report[layout["flags"]] == TRIG_FLAGS | RUMBLE_FLAGS
    assert report[layout["motor_l"]] == 128
    assert report[layout["motor_r"]] == 64


def test_bluetooth_crc_covers_compatible_rumble_bytes():
    controller = DualSense(enable_startup_pulse=False)
    controller.lay = BT

    report = controller._build(
        LEFT,
        RIGHT,
        CompatibleRumble(low_frequency=1.0, high_frequency=0.5),
    )

    expected_crc = zlib.crc32(memoryview(report)[:74], _BT_CRC_SEED)
    assert struct.unpack_from("<I", report, 74)[0] == expected_crc


def test_bluetooth_rumble_release_then_trigger_only_claims_expected_fields():
    controller = DualSense(enable_startup_pulse=False)
    controller.lay = BT

    active = controller._build(
        LEFT,
        RIGHT,
        CompatibleRumble(low_frequency=0.5, high_frequency=0.25),
    )
    released = controller._build(LEFT, RIGHT, CompatibleRumble())
    trigger_only = controller._build(LEFT, RIGHT, None)

    assert active[BT["flags"]] == TRIG_FLAGS | RUMBLE_FLAGS
    assert active[BT["motor_l"]] == 128
    assert active[BT["motor_r"]] == 64
    assert released[BT["flags"]] == TRIG_FLAGS | RUMBLE_FLAGS
    assert released[BT["motor_l"]] == 0
    assert released[BT["motor_r"]] == 0
    assert trigger_only[BT["flags"]] == TRIG_FLAGS
    assert trigger_only[BT["motor_l"]] == 0
    assert trigger_only[BT["motor_r"]] == 0


def test_set_queues_trigger_and_rumble_as_one_pending_frame():
    controller = DualSense(enable_startup_pulse=False)
    rumble = CompatibleRumble(low_frequency=0.3, high_frequency=0.6)

    controller.set(LEFT, RIGHT, rumble)

    assert controller._left == LEFT
    assert controller._right == RIGHT
    assert controller._rumble == rumble
    assert controller._dirty is True


def test_io_preserves_rumble_release_before_following_trigger_only_frame():
    controller = DualSense(enable_startup_pulse=False)
    device = _GatedDevice(read_count=3)
    controller.dev = device
    _mark_connected(controller, InputTransport.BLUETOOTH)
    active_rumble = CompatibleRumble(low_frequency=0.5, high_frequency=0.25)
    controller.set(LEFT, RIGHT, active_rumble)
    controller._running = True
    thread = threading.Thread(target=controller._io)
    thread.start()

    try:
        assert device.read_entered[0].wait(timeout=2.0)
        device.read_released[0].set()
        assert device.wait_for_writes(1)

        assert device.read_entered[1].wait(timeout=2.0)
        controller.set(LEFT, RIGHT, CompatibleRumble())
        controller.set(LEFT, RIGHT, None)
        device.read_released[1].set()
        assert device.wait_for_writes(2)

        assert device.read_entered[2].wait(timeout=2.0)
        controller._running = False
        controller._wake.set()
        device.read_released[2].set()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
    finally:
        controller._running = False
        controller._wake.set()
        for release in device.read_released:
            release.set()
        thread.join(timeout=2.0)

    assert len(device.writes) == 4
    active, released, trigger_only = device.writes[:3]
    assert active[BT["flags"]] == TRIG_FLAGS | RUMBLE_FLAGS
    assert active[BT["motor_l"]] == 128
    assert active[BT["motor_r"]] == 64
    assert released[BT["flags"]] == TRIG_FLAGS | RUMBLE_FLAGS
    assert released[BT["motor_l"]] == 0
    assert released[BT["motor_r"]] == 0
    assert trigger_only[BT["flags"]] == TRIG_FLAGS


def test_close_drains_a_coalesced_rumble_release():
    device = _GatedDevice(read_count=0)
    controller = DualSense(enable_startup_pulse=False)
    controller.lay = BT
    controller.dev = device
    controller.set(
        LEFT,
        RIGHT,
        CompatibleRumble(low_frequency=0.5, high_frequency=0.25),
    )
    controller._dirty = False
    controller.set(LEFT, RIGHT, CompatibleRumble())
    controller.set(LEFT, RIGHT, None)

    controller.close()

    assert len(device.writes) == 1
    released = device.writes[0]
    assert released[BT["flags"]] == TRIG_FLAGS | RUMBLE_FLAGS
    assert released[BT["motor_l"]] == 0
    assert released[BT["motor_r"]] == 0
    assert device.closed is True


def test_new_rumble_claim_cancels_an_obsolete_pending_release():
    controller = DualSense(enable_startup_pulse=False)
    controller.set(
        LEFT,
        RIGHT,
        CompatibleRumble(low_frequency=0.5, high_frequency=0.25),
    )
    controller._dirty = False
    controller.set(LEFT, RIGHT, CompatibleRumble())
    controller.set(LEFT, RIGHT, None)

    replacement = CompatibleRumble(low_frequency=0.75, high_frequency=0.125)
    controller.set(LEFT, RIGHT, replacement)

    assert controller._take_pending_output() == (
        LEFT,
        RIGHT,
        replacement,
        NO_VISUAL_CONTROL,
    )
    assert controller._take_pending_output() is None


def test_transport_is_only_reported_while_connected():
    controller = DualSense(enable_startup_pulse=False)
    assert controller.transport is None

    controller.dev = object()
    _mark_connected(controller, InputTransport.USB)
    assert controller.transport == "usb"

    _mark_connected(controller, InputTransport.BLUETOOTH)
    assert controller.transport == "bluetooth"


def test_bluetooth_haptics_queue_keeps_only_the_freshest_audio_chunk():
    controller = DualSense(enable_startup_pulse=False)
    controller.dev = object()
    _mark_connected(controller, InputTransport.BLUETOOTH)

    assert controller.queue_bt_haptics(bytes([1]) * 64) is True
    assert controller.queue_bt_haptics(bytes([2]) * 64) is True

    assert controller.bt_haptics_dropped == 1
    assert controller._take_pending_bt_haptics() == bytes([2]) * 64
    assert controller._take_pending_bt_haptics() is None


def test_bluetooth_haptics_queue_rejects_usb_and_bad_payloads():
    controller = DualSense(enable_startup_pulse=False)
    controller.dev = object()
    controller.lay = USB

    assert controller.queue_bt_haptics(bytes(64)) is False
    with pytest.raises(ValueError, match="64 bytes"):
        controller.queue_bt_haptics(bytes(63))


def test_io_coalesces_trigger_state_into_bluetooth_haptics_report():
    controller = DualSense(enable_startup_pulse=False)
    device = _GatedDevice(read_count=2)
    controller.dev = device
    _mark_connected(controller, InputTransport.BLUETOOTH)
    controller.set(LEFT, RIGHT, None)
    assert controller.queue_bt_haptics(bytes(range(64))) is True
    controller._running = True
    thread = threading.Thread(target=controller._io)
    thread.start()

    try:
        assert device.read_entered[0].wait(timeout=2.0)
        device.read_released[0].set()
        assert device.wait_for_writes(1)

        assert device.read_entered[1].wait(timeout=2.0)
        assert len(device.writes) == 1
        controller._running = False
        controller._wake.set()
        device.read_released[1].set()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
    finally:
        controller._running = False
        controller._wake.set()
        for release in device.read_released:
            release.set()
        thread.join(timeout=2.0)

    haptics_report = device.writes[0]
    assert haptics_report[0] == 0x36
    assert haptics_report[78:142] == bytes(range(64))
    assert haptics_report[13 + 21] == LEFT[0]
    assert haptics_report[13 + 10] == RIGHT[0]
