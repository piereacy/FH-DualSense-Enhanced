import socket

import pytest

from modules.forzahorizon import udp_forward
from modules.forzahorizon.udp_listener import UDPListener


class SendSocket:
    def __init__(self):
        self.blocking = True
        self.closed = False
        self.sent = []

    def setblocking(self, blocking):
        self.blocking = blocking

    def sendto(self, packet, address):
        if address[0] == "192.0.2.1":
            assert self.blocking is False, "congested target must not block telemetry"
            raise BlockingIOError("send buffer full")
        self.sent.append((packet, address))

    def close(self):
        self.closed = True


def test_forwarder_resolves_once_and_keeps_sending_after_congestion(monkeypatch):
    sock = SendSocket()
    lookups = []

    def resolve(host):
        lookups.append(host)
        return {"slow.example": "192.0.2.1", "good.example": "192.0.2.2"}[host]

    monkeypatch.setattr(udp_forward.socket, "gethostbyname", resolve)
    monkeypatch.setattr(udp_forward.socket, "socket", lambda *_args: sock)
    forwarder = udp_forward.UDPForwarder("slow.example:5301,good.example:5302")
    forwarder.open()
    for _ in range(3):
        forwarder.send(b"raw packet")

    assert lookups == ["slow.example", "good.example"]
    assert sock.sent == [(b"raw packet", ("192.0.2.2", 5302))] * 3
    forwarder.close()
    assert not forwarder.active
    assert sock.closed


@pytest.mark.parametrize("failure", [socket.gaierror("unresolved"), UnicodeError("invalid host")])
def test_invalid_forward_host_does_not_disable_valid_targets(monkeypatch, failure):
    sock = SendSocket()

    def resolve(host):
        if host == "bad.example":
            raise failure
        return "192.0.2.2"

    monkeypatch.setattr(udp_forward.socket, "gethostbyname", resolve)
    monkeypatch.setattr(udp_forward.socket, "socket", lambda *_args: sock)
    forwarder = udp_forward.UDPForwarder("bad.example:5301,good.example:5302")
    forwarder.open()
    forwarder.send(b"raw packet")

    assert sock.sent == [(b"raw packet", ("192.0.2.2", 5302))]


@pytest.mark.parametrize("fail_at", ["create", "configure"])
def test_forward_socket_setup_failure_is_optional_and_closes_partial_socket(monkeypatch, fail_at):
    sock = SendSocket()

    def fail(*_args):
        raise OSError("socket unavailable")

    monkeypatch.setattr(udp_forward.socket, "gethostbyname", lambda _host: "192.0.2.2")
    if fail_at == "create":
        monkeypatch.setattr(udp_forward.socket, "socket", fail)
    else:
        monkeypatch.setattr(sock, "setblocking", fail)
        monkeypatch.setattr(udp_forward.socket, "socket", lambda *_args: sock)
    forwarder = udp_forward.UDPForwarder("good.example:5302")
    forwarder.open()
    forwarder.send(b"raw packet")

    assert not forwarder.active
    assert forwarder._sock is None
    if fail_at == "configure":
        assert sock.closed


def test_listener_rejects_resolved_alias_of_its_receive_endpoint(monkeypatch):
    sender = SendSocket()

    class Receiver:
        def settimeout(self, _timeout):
            pass

        def getsockname(self):
            return ("127.0.0.1", 5300)

        def close(self):
            pass

    monkeypatch.setattr(udp_forward.socket, "gethostbyname", lambda _host: "127.0.0.1")
    monkeypatch.setattr(udp_forward.socket, "socket", lambda *_args: sender)
    listener = UDPListener("127.0.0.1", 5300, forward_to="alias.example:5300,alias.example:5301")
    monkeypatch.setattr(listener, "_open_ipv4", Receiver)

    with listener:
        listener._fwd.send(b"raw packet")
        assert sender.sent == [(b"raw packet", ("127.0.0.1", 5301))]


def test_listener_closes_bound_socket_when_timeout_configuration_fails(monkeypatch):
    sock = SendSocket()

    def fail(_timeout):
        raise OSError("timeout configuration failed")

    sock.settimeout = fail
    listener = UDPListener("127.0.0.1", 5300)
    monkeypatch.setattr(listener, "_open_ipv4", lambda: sock)

    with pytest.raises(OSError, match="timeout configuration failed"):
        listener.__enter__()

    assert sock.closed
    assert listener.sock is None


def test_real_nonblocking_forward_preserves_raw_datagram():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1.0)
        _, port = receiver.getsockname()
        forwarder = udp_forward.UDPForwarder(f"127.0.0.1:{port}")
        forwarder.open()
        try:
            payload = bytes(range(256)) + bytes(68)
            forwarder.send(payload)
            assert receiver.recvfrom(1500)[0] == payload
        finally:
            forwarder.close()
