import threading

import pytest

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


def test_socket_creation_failure_reaches_startup_health_boundary(monkeypatch):
    client = DSXClient(enable_startup_pulse=False)

    def fail_socket(*_args):
        raise OSError("socket unavailable")

    monkeypatch.setattr("modules.dsx.client.socket.socket", fail_socket)

    with pytest.raises(OSError, match="socket unavailable"):
        client.open()
    assert client.connected is False
    assert client.diagnostics_snapshot().last_error == "socket unavailable"


def test_startup_pulse_request_is_idempotent(monkeypatch):
    client = DSXClient(enable_startup_pulse=True)
    sent = []
    client._connected = True
    monkeypatch.setattr(
        client,
        "set",
        lambda left, right, *_args, **_kwargs: sent.append((left, right)),
    )
    monkeypatch.setattr(client._pulse_cancel, "wait", lambda _duration: False)

    client.request_startup_pulse()
    client.request_startup_pulse()

    assert len(sent) == 2


def test_startup_pulse_can_be_cancelled_before_its_full_duration(monkeypatch):
    client = DSXClient(enable_startup_pulse=True)
    client._connected = True
    sent = []
    pulse_started = threading.Event()
    monkeypatch.setattr(
        client,
        "set",
        lambda left, right, *_args, **_kwargs: (
            sent.append((left, right)),
            pulse_started.set(),
        ),
    )

    worker = threading.Thread(target=client.request_startup_pulse)
    worker.start()
    assert pulse_started.wait(0.5)
    client.cancel_startup_pulse()
    worker.join(timeout=0.1)

    assert not worker.is_alive()
    assert len(sent) == 2


def test_zoned_abs_wall_falls_back_to_dynamic_vibration_in_dsx():
    packet = dsx_wrapper.frames_to_packet(vibrate_zones(3, 42, 3), off())

    left = packet["instructions"][0]
    assert left["parameters"] == [
        0,
        dsx_wrapper.T_LEFT,
        dsx_wrapper.TM_VIBRATE,
        42,
    ]


@pytest.mark.parametrize("host,port", [("", 6969), ("127.0.0.1", 0), ("127.0.0.1", 65536)])
def test_invalid_dsx_targets_are_rejected_before_open(host, port):
    with pytest.raises(ValueError):
        DSXClient(host=host, port=port, enable_startup_pulse=False)
