import struct

import pytest

from modules.forzahorizon.udp_forward import UDPForwarder, _parse_targets
from modules.forzahorizon.udp_listener import TelemetryPhase, UDPListener, parse_packet


class _FakeSocket:
    def __init__(self):
        self.timeout = None
        self.closed = False

    def settimeout(self, timeout):
        self.timeout = timeout

    def close(self):
        self.closed = True


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


def test_non_finite_udp_floats_are_sanitized_at_the_parser_boundary():
    packet = bytearray(324)
    struct.pack_into("<f", packet, 8, float("nan"))
    struct.pack_into("<f", packet, 16, float("inf"))
    struct.pack_into("<f", packet, 84, float("-inf"))

    telemetry = parse_packet(packet)

    assert telemetry["max_rpm"] == 0.0
    assert telemetry["rpm"] == 0.0
    assert telemetry["tire_slip_ratio_fl"] == 0.0


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


def test_explicit_ipv4_host_does_not_expand_to_all_interfaces(monkeypatch):
    listener = UDPListener("127.0.0.1", 5300)
    sock = _FakeSocket()
    monkeypatch.setattr(
        listener,
        "_open_dual_stack",
        lambda: pytest.fail("explicit IPv4 must not use the wildcard dual-stack bind"),
    )
    monkeypatch.setattr(listener, "_open_ipv4", lambda: sock)

    with listener as opened:
        assert opened.sock is sock
        assert sock.timeout == pytest.approx(0.5)

    assert sock.closed is True


def test_wildcard_ipv6_host_keeps_dual_stack_behavior(monkeypatch):
    listener = UDPListener("::", 5300)
    sock = _FakeSocket()
    monkeypatch.setattr(listener, "_open_dual_stack", lambda: sock)
    monkeypatch.setattr(
        listener,
        "_open_ipv4",
        lambda: pytest.fail("working dual-stack bind must not fall back"),
    )

    with listener as opened:
        assert opened.sock is sock


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_invalid_udp_ports_are_rejected_before_socket_creation(port):
    with pytest.raises(ValueError):
        UDPListener("127.0.0.1", port)


def test_forward_targets_reject_empty_hosts_and_invalid_ports():
    assert _parse_targets("127.0.0.1:5301, :5302, host:0, host:65536") == [
        ("127.0.0.1", 5301)
    ]


def test_forward_send_errors_never_escape_into_telemetry_loop():
    class _BrokenSocket:
        def sendto(self, _packet, _address):
            raise OverflowError("synthetic address failure")

    forwarder = UDPForwarder("127.0.0.1:5301")
    forwarder._sock = _BrokenSocket()

    forwarder.send(b"packet")
