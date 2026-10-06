from types import SimpleNamespace

import pytest

from modules.dualsense import main as native
from modules.dualsense.adaptive_trigger import off, rigid, vibrate
from modules.dualsense.controller_state import ControllerPhase
from modules.dualsense.input_state import InputTransport
from modules.dualsense.output_state import ControllerVisualState
from modules.haptics.frame import CompatibleRumble
from modules.haptics.trigger_pulse import TriggerPulse

IDENTITY = "001122334455"


def _controller(transport=InputTransport.USB):
    controller = native.DualSense(enable_startup_pulse=False)
    controller.lay = native.USB if transport is InputTransport.USB else native.BT
    controller._update_snapshot(
        phase=ControllerPhase.CONNECTED, transport=transport,
        identity=IDENTITY, last_input_at=10.0,
    )
    return controller


def test_identification_uses_the_current_connection_without_opening_hid(monkeypatch):
    monkeypatch.setattr(native.hid, "device", lambda: pytest.fail("opened a second handle"))
    controller = _controller()
    pulse = TriggerPulse()

    assert pulse.identify(controller, "00:11:22:33:44:55", force=180, now=10.0)
    output = pulse.sample_output(now=10.1, controller=controller)

    assert output.effect == rigid(180)
    assert output.guard.connection_generation == controller.snapshot().connection_generation
    assert output.guard.expires_at == pytest.approx(10.3)
    assert controller._take_pending_output() is None
    assert pulse.sample_output(now=10.301, controller=controller) is None


@pytest.mark.parametrize("selection", ["", "aabbccddeeff"])
def test_identification_rejects_other_or_unselected_devices(selection):
    pulse = TriggerPulse()
    assert not pulse.identify(_controller(), selection, force=180, now=10.0)


@pytest.mark.parametrize("controller", [None, SimpleNamespace(is_dsx=True), native.DualSense()])
def test_identification_does_not_wait_for_an_unavailable_native_connection(controller):
    pulse = TriggerPulse()
    pulse.request(True)
    assert not pulse.identify(controller, IDENTITY, force=180, now=10.0)
    assert pulse.sample_output(now=10.1, controller=controller) is None


def test_identification_discards_requests_not_consumed_before_the_deadline():
    controller = _controller()
    pulse = TriggerPulse()
    assert pulse.identify(controller, IDENTITY, force=180, now=10.0)
    assert pulse.sample_output(now=10.75, controller=controller) is None


@pytest.mark.parametrize("change", ["disconnect", "reconnect", "transport", "identity", "backend"])
def test_identification_is_cancelled_when_its_connection_changes(change):
    controller = _controller()
    pulse = TriggerPulse()
    assert pulse.identify(controller, IDENTITY, force=180, now=10.0)
    if change in {"disconnect", "reconnect"}:
        controller._update_snapshot(phase=ControllerPhase.RECONNECTING)
        if change == "reconnect":
            controller._update_snapshot(phase=ControllerPhase.CONNECTED)
    elif change == "transport":
        controller._update_snapshot(transport=InputTransport.BLUETOOTH)
    elif change == "identity":
        controller._update_snapshot(identity="aabbccddeeff")
    else:
        controller = _controller()

    assert pulse.sample_output(now=10.1, controller=controller) is None


def test_fresh_input_and_battery_updates_do_not_cancel_identification():
    controller = _controller()
    pulse = TriggerPulse()
    assert pulse.identify(controller, IDENTITY, force=180, now=10.0)
    controller._update_snapshot(last_input_at=10.05, battery_level=6)
    assert pulse.sample_output(now=10.1, controller=controller).effect == rigid(180)


@pytest.mark.parametrize("invalidation", ["expired", "reconnected"])
def test_native_output_guard_discards_queued_identification_without_losing_other_fields(
    monkeypatch, invalidation,
):
    clock = [10.0]
    monkeypatch.setattr(native.time, "monotonic", lambda: clock[0])
    controller = _controller()
    pulse = TriggerPulse()
    assert pulse.identify(controller, IDENTITY, force=180, now=clock[0])
    output = pulse.sample_output(now=clock[0], controller=controller)
    rumble = CompatibleRumble(0.3, 0.2)
    visual = ControllerVisualState(lightbar=(20, 30, 40))
    controller.set(output.effect, output.effect, rumble, visual=visual, trigger_guard=output.guard)
    if invalidation == "expired":
        clock[0] = 10.3
    else:
        controller._update_snapshot(phase=ControllerPhase.RECONNECTING)
        controller._update_snapshot(phase=ControllerPhase.CONNECTED)

    assert controller._take_pending_output() == (off(), off(), rumble, visual)


def test_native_output_guard_releases_an_already_sent_identification(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(native.time, "monotonic", lambda: clock[0])
    controller = _controller()
    pulse = TriggerPulse()
    assert pulse.identify(controller, IDENTITY, force=180, now=clock[0])
    output = pulse.sample_output(now=clock[0], controller=controller)
    controller.set(output.effect, output.effect, trigger_guard=output.guard)
    assert controller._take_pending_output()[:2] == (rigid(180),) * 2
    assert not controller._has_pending_output()

    clock[0] = 10.3

    assert controller._has_pending_output()
    assert controller._take_pending_output()[:2] == (off(),) * 2
    assert not controller._has_pending_output()


def test_guard_does_not_leak_through_a_queued_rumble_release(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(native.time, "monotonic", lambda: clock[0])
    controller = _controller()
    pulse = TriggerPulse()
    assert pulse.identify(controller, IDENTITY, force=180, now=clock[0])
    output = pulse.sample_output(now=clock[0], controller=controller)
    controller.set(output.effect, output.effect, CompatibleRumble(), trigger_guard=output.guard)
    telemetry = (rigid(30), vibrate(40, 20))
    controller.set(*telemetry)
    clock[0] = 10.3

    assert controller._take_pending_output()[:3] == (off(), off(), CompatibleRumble())
    assert controller._take_pending_output()[:2] == telemetry


def test_bluetooth_haptics_packets_cannot_restore_expired_identification(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(native.time, "monotonic", lambda: clock[0])
    controller = _controller(InputTransport.BLUETOOTH)
    pulse = TriggerPulse()
    assert pulse.identify(controller, IDENTITY, force=180, now=clock[0])
    output = pulse.sample_output(now=clock[0], controller=controller)
    controller.set(output.effect, output.effect, trigger_guard=output.guard)
    first = controller._build_bt_haptics(bytes(64))
    assert (first[23], first[34]) == (rigid(180)[0],) * 2
    clock[0] = 10.3

    expired = controller._build_bt_haptics(bytes(64))

    assert (expired[23], expired[34]) == (off()[0],) * 2
