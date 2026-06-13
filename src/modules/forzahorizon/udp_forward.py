"""Mirror raw UDP packets to downstream apps (e.g. SimHub) without consuming
the source. The listener owns the receive port; this just relays a byte-exact
copy of each packet on. Localhost UDP sends never block, so it stays inline in
the hot loop - no thread needed.
"""
import logging
import socket

log = logging.getLogger("fhds.udp")


def _parse_targets(spec: str) -> list[tuple[str, int]]:
    """Parse 'host:port, host:port, ...' into (host, port) tuples. Bad
    entries are warned and skipped so one typo never kills forwarding."""
    out: list[tuple[str, int]] = []
    for raw in spec.split(","):
        raw = raw.strip()
        if not raw:
            continue
        host, _, port = raw.rpartition(":")
        try:
            out.append((host, int(port)))
        except ValueError:
            log.warning("Ignoring bad forward target %r (expected host:port)", raw)
    return out


class UDPForwarder:
    """Relays raw packets to one or more host:port targets via a single IPv4
    send socket. A no-op when disabled or no valid targets are configured."""

    def __init__(self, forward_to: str = "", enabled: bool = True):
        self.targets = _parse_targets(forward_to) if enabled else []
        self._sock: socket.socket | None = None
        self._warned = False

    @property
    def active(self) -> bool:
        return bool(self.targets)

    def open(self):
        if self.targets:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            for host, port in self.targets:
                log.info("Forwarding raw telemetry to %s:%d", host, port)

    def send(self, pkt: bytes):
        # MARK: never let a forward error stall telemetry - warn once, keep going
        for addr in self.targets:
            try:
                self._sock.sendto(pkt, addr)
            except OSError as e:
                if not self._warned:
                    self._warned = True
                    log.warning("UDP forward failed (further errors suppressed): %s", e)

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None
