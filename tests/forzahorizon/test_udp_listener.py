import struct

import pytest

from modules.forzahorizon.udp_listener import TelemetryPhase, UDPListener, parse_packet


def test_puddle_depth_fields_are_parsed_as_float32():
    packet = bytearray(324)
    expected = {
        "wheel_in_puddle_fl": 0.25,
        "wheel_in_puddle_fr": 0.5,
        "wheel_in_puddle_rl": 0.75,
        "wheel_in_puddle_rr": 1.0,
    }
    for offset, value in zip((132, 136, 140, 144), expected.values()):
        struct.pack_into("<f", packet, offset, value)

    telemetry = parse_packet(packet)

    for name, value in expected.items():
        assert telemetry[name] == pytest.approx(value)


def test_listener_snapshot_tracks_only_valid_packets_and_detects_loss():
    now = [10.0]
    listener = UDPListener("127.0.0.1", 5300, clock=lambda: now[0])

    initial = listener.snapshot()
    assert initial.phase is TelemetryPhase.WAITING
    assert initial.packet_count == 0
    assert initial.last_packet_age_s is None

    listener._record_valid_packet(("127.0.0.1", 60123))
    receiving = listener.snapshot()
    assert receiving.phase is TelemetryPhase.RECEIVING
    assert receiving.packet_count == 1
    assert receiving.source_host == "127.0.0.1"
    assert receiving.source_port == 60123

    now[0] = 11.01
    lost = listener.snapshot()
    assert lost.phase is TelemetryPhase.LOST
    assert lost.last_packet_age_s == pytest.approx(1.01)


def test_wrong_size_datagrams_do_not_advance_the_runtime_snapshot():
    listener = UDPListener("127.0.0.1", 5300, clock=lambda: 4.0)

    assert listener._accept_datagram(b"wrong", ("127.0.0.1", 60000)) is False
    snapshot = listener.snapshot()

    assert snapshot.phase is TelemetryPhase.WAITING
    assert snapshot.packet_count == 0
