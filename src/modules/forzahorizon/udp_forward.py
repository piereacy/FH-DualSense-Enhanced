"""Mirror raw UDP packets to downstream apps (e.g. SimHub) without consuming
the source. Resolve targets at startup and use non-blocking sends so a stalled
downstream target cannot stall the telemetry loop.
"""
import logging
import socket
from collections.abc import Callable

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
            parsed_port = int(port)
        except ValueError:
            log.warning("Ignoring bad forward target %r (expected host:port)", raw)
            continue
        if not host or not 1 <= parsed_port <= 65535:
            log.warning("Ignoring bad forward target %r (expected host:port)", raw)
            continue
        out.append((host, parsed_port))
    return out


class UDPForwarder:
    """Relays raw packets to one or more host:port targets via a single IPv4
    send socket. A no-op when disabled or no valid targets are configured."""

    def __init__(self, forward_to: str = "", enabled: bool = True):
        self.targets = _parse_targets(forward_to) if enabled else []
        self._sock: socket.socket | None = None
        self._resolved_targets: list[tuple[str, int]] = []
        self._warned = False

    @property
    def active(self) -> bool:
        return self._sock is not None and bool(self._resolved_targets)

    def open(self, *, target_filter: Callable[[tuple[str, int]], bool] | None = None):
        self.close()
        self._warned = False
        for host, port in self.targets:
            try:
                target = (socket.gethostbyname(host), port)
            except (OSError, UnicodeError, ValueError) as exc:
                log.warning("Ignoring unresolved UDP forward target %r: %s", host, exc)
                continue
            if target_filter is not None and not target_filter(target):
                log.warning("Ignoring UDP forward target %s:%d because it matches the listener endpoint", host, port)
                continue
            if target not in self._resolved_targets:
                self._resolved_targets.append(target)
        if not self._resolved_targets:
            return
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setblocking(False)
        except OSError as exc:
            self.close()
            log.warning("UDP forwarding unavailable: %s", exc)
            return
        for host, port in self._resolved_targets:
            log.info("Forwarding raw telemetry to %s:%d", host, port)

    def send(self, pkt: bytes):
        # MARK: never let a forward error stall telemetry - warn once, keep going
        if self._sock is None:
            return
        for addr in self._resolved_targets:
            try:
                self._sock.sendto(pkt, addr)
            except (OSError, OverflowError) as e:
                if not self._warned:
                    self._warned = True
                    log.warning("UDP forward failed (further errors suppressed): %s", e)

    def close(self):
        self._resolved_targets.clear()
        if self._sock:
            self._sock.close()
            self._sock = None
