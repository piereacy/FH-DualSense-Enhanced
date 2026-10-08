"""UDP listener for Forza Horizon telemetry.

Packet = 324 bytes; offsets verified against FH Data Out spec.
Always returns the *latest* packet (drains queued ones) so I never react
to stale telemetry.
"""
import ipaddress
import logging
import math
import socket
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass
from enum import StrEnum

from .udp_forward import UDPForwarder

log = logging.getLogger("fhds.udp")

PACKET_SIZE = 324
MAX_DRAIN_DATAGRAMS = 64

_WILDCARD_HOSTS = {"", "0.0.0.0", "::"}
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _normalized_host(host: str) -> str:
    return str(host).strip().strip("[]").rstrip(".").casefold()


def _is_loopback_host(host: str) -> bool:
    normalized = _normalized_host(host)
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _is_obvious_self_forward(
    listen_host: str,
    listen_port: int,
    target: tuple[str, int],
) -> bool:
    target_host, target_port = target
    if target_port != listen_port:
        return False
    listen = _normalized_host(listen_host)
    forwarded = _normalized_host(target_host)
    if listen == forwarded:
        return True
    if listen in _WILDCARD_HOSTS and (
        forwarded in _WILDCARD_HOSTS or _is_loopback_host(forwarded)
    ):
        return True
    return _is_loopback_host(listen) and _is_loopback_host(forwarded)


class TelemetryPhase(StrEnum):
    """Observable receive state for status surfaces."""

    WAITING = "waiting"
    RECEIVING = "receiving"
    LOST = "lost"


@dataclass(frozen=True, slots=True)
class TelemetrySnapshot:
    phase: TelemetryPhase
    packet_count: int
    last_packet_age_s: float | None
    source_host: str
    source_port: int | None
    listen_port: int
    packet_rate_hz: float = 0.0
    invalid_packet_count: int = 0
    drained_packet_count: int = 0
    receive_error_count: int = 0


def parse_packet(p: bytes) -> dict:
    if len(p) < 323:
        raise ValueError(f"Packet too short: {len(p)}")

    def f(offset: int) -> float:
        value = struct.unpack_from("<f", p, offset)[0]
        # UDP is not a trusted numeric boundary. A malformed NaN used to turn
        # some min/max clamps into full-strength feedback and could crash the
        # optional lighting path. Invalid floats carry no useful telemetry.
        return value if math.isfinite(value) else 0.0

    i = lambda o: struct.unpack_from("<i", p, o)[0]  # noqa: E731
    b = lambda o: struct.unpack_from("<b", p, o)[0]  # noqa: E731
    u32 = lambda o: struct.unpack_from("<I", p, o)[0]  # noqa: E731
    u16 = lambda o: struct.unpack_from("<H", p, o)[0]  # noqa: E731

    # Format specified by the Forza Motorsport Data Out documentation
    return {
        "on": i(0) != 0,
        "timestamp_ms": u32(4),
        "max_rpm": f(8),
        "idle_rpm": f(12),
        "rpm": f(16),
        "accel_x": f(20),
        "accel_y": f(24),
        "accel_z": f(28),
        "velocity_x": f(32),
        "velocity_y": f(36),
        "velocity_z": f(40),
        "angular_velocity_x": f(44),
        "angular_velocity_y": f(48),
        "angular_velocity_z": f(52),
        "yaw": f(56),
        "pitch": f(60),
        "roll": f(64),
        "norm_suspension_travel_fl": f(68),
        "norm_suspension_travel_fr": f(72),
        "norm_suspension_travel_rl": f(76),
        "norm_suspension_travel_rr": f(80),
        "tire_slip_ratio_fl": f(84),
        "tire_slip_ratio_fr": f(88),
        "tire_slip_ratio_rl": f(92),
        "tire_slip_ratio_rr": f(96),
        "wheel_rotation_speed_fl": f(100),
        "wheel_rotation_speed_fr": f(104),
        "wheel_rotation_speed_rl": f(108),
        "wheel_rotation_speed_rr": f(112),
        "wheel_on_rumble_strip_fl": i(116),
        "wheel_on_rumble_strip_fr": i(120),
        "wheel_on_rumble_strip_rl": i(124),
        "wheel_on_rumble_strip_rr": i(128),
        "wheel_in_puddle_fl": f(132),
        "wheel_in_puddle_fr": f(136),
        "wheel_in_puddle_rl": f(140),
        "wheel_in_puddle_rr": f(144),
        "surface_rumble_fl": f(148),
        "surface_rumble_fr": f(152),
        "surface_rumble_rl": f(156),
        "surface_rumble_rr": f(160),
        "tire_slip_angle_fl": f(164),
        "tire_slip_angle_fr": f(168),
        "tire_slip_angle_rl": f(172),
        "tire_slip_angle_rr": f(176),
        "tire_combined_slip_fl": f(180),
        "tire_combined_slip_fr": f(184),
        "tire_combined_slip_rl": f(188),
        "tire_combined_slip_rr": f(192),
        "suspension_travel_meters_fl": f(196),
        "suspension_travel_meters_fr": f(200),
        "suspension_travel_meters_rl": f(204),
        "suspension_travel_meters_rr": f(208),
        "car_ordinal": i(212),
        "car_class": i(216),
        "car_performance_index": i(220),
        "drive_train": i(224),
        "num_cylinders": i(228),
        # Horizon's 324-byte Dash layout keeps a 12-byte extension here.
        # The first word is community-mapped as a car category/group; the
        # remaining values are useful collision signals where populated.
        "car_group": u32(232),
        "smashable_vel_diff": f(236),
        "smashable_mass": f(240),
        "position_x": f(244),
        "position_y": f(248),
        "position_z": f(252),
        "speed": f(256) * 3.6,  # m/s to km/h
        "power": f(260),
        "torque": f(264),
        "tire_temp_fl": f(268),
        "tire_temp_fr": f(272),
        "tire_temp_rl": f(276),
        "tire_temp_rr": f(280),
        "boost": f(284),
        "fuel": f(288),
        "distance_traveled": f(292),
        "best_lap_time": f(296),
        "last_lap_time": f(300),
        "current_lap_time": f(304),
        "current_race_time": f(308),
        "lap_number": u16(312),
        "race_position": p[314],
        "accel": p[315],
        "brake": p[316],
        "clutch": p[317],
        "handbrake": p[318],
        "gear": p[319],
        "steer": b(320),
        "normalized_driving_line": b(321),
        "normalized_ai_brake_difference": b(322),
    }


class UDPListener:
    """UDP listener that always returns the most recent packet.

    Binds the configured address exactly. An explicit IPv4 or IPv6 address
    stays in that family; only the IPv6 wildcard uses a dual-stack socket.
    """

    def __init__(self, host: str, port: int, timeout: float = 0.5,
                 forward_to: str = "", forward_enabled: bool = True,
                 *, clock=None):
        self.host = str(host)
        self.port = int(port)
        self.timeout = float(timeout)
        if not 1 <= self.port <= 65535:
            raise ValueError("UDP port must be between 1 and 65535")
        if not math.isfinite(self.timeout) or self.timeout <= 0.0:
            raise ValueError("UDP timeout must be a positive finite number")
        self.sock: socket.socket | None = None
        self.lost = False
        self._warned_sizes: set[int] = set()
        self._fwd = UDPForwarder(forward_to, forward_enabled)
        safe_targets = []
        for target in self._fwd.targets:
            if _is_obvious_self_forward(self.host, self.port, target):
                log.warning(
                    "Ignoring UDP forward target %s:%d because it matches the listener endpoint",
                    target[0],
                    target[1],
                )
                continue
            safe_targets.append(target)
        self._fwd.targets = safe_targets
        self._clock = clock or time.monotonic
        self._state_lock = threading.Lock()
        self._packet_count = 0
        self._last_packet_at: float | None = None
        self._source_host = ""
        self._source_port: int | None = None
        self._recent_packet_times: deque[float] = deque(maxlen=256)
        self._invalid_packet_count = 0
        self._drained_packet_count = 0
        self._receive_error_count = 0

    def snapshot(self, *, now: float | None = None) -> TelemetrySnapshot:
        """Return a consistent, read-only view without touching the socket."""
        timestamp = self._clock() if now is None else now
        with self._state_lock:
            count = self._packet_count
            last = self._last_packet_at
            source_host = self._source_host
            source_port = self._source_port
            cutoff = timestamp - 2.0
            while self._recent_packet_times and self._recent_packet_times[0] < cutoff:
                self._recent_packet_times.popleft()
            recent = tuple(self._recent_packet_times)
            invalid_count = self._invalid_packet_count
            drained_count = self._drained_packet_count
            receive_errors = self._receive_error_count
        rate_hz = 0.0
        if len(recent) >= 2:
            span = recent[-1] - recent[0]
            if span > 0.0:
                rate_hz = (len(recent) - 1) / span
        age = None if last is None else max(0.0, timestamp - last)
        if count == 0:
            phase = TelemetryPhase.WAITING
        elif age is not None and age <= 1.0:
            phase = TelemetryPhase.RECEIVING
        else:
            phase = TelemetryPhase.LOST
        return TelemetrySnapshot(
            phase=phase,
            packet_count=count,
            last_packet_age_s=age,
            source_host=source_host,
            source_port=source_port,
            listen_port=self.port,
            packet_rate_hz=round(rate_hz, 2),
            invalid_packet_count=invalid_count,
            drained_packet_count=drained_count,
            receive_error_count=receive_errors,
        )

    def _record_valid_packet(self, addr) -> None:
        with self._state_lock:
            received_at = self._clock()
            self._packet_count += 1
            self._last_packet_at = received_at
            self._recent_packet_times.append(received_at)
            self._source_host = str(addr[0]) if addr else ""
            self._source_port = int(addr[1]) if addr and len(addr) > 1 else None

    def _accept_datagram(self, pkt: bytes, addr) -> bool:
        if len(pkt) == PACKET_SIZE:
            self._record_valid_packet(addr)
            return True
        with self._state_lock:
            self._invalid_packet_count += 1
        if len(pkt) not in self._warned_sizes:
            self._warned_sizes.add(len(pkt))
            log.warning(
                "Unexpected %d-byte packet from %s:%d (expected %d - may be from another app, or a new FH format)",
                len(pkt), addr[0], addr[1], PACKET_SIZE,
            )
        return False

    def _open_dual_stack(self) -> socket.socket | None:
        s = None
        try:
            s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            s.bind(("::", self.port))
            log.info("UDP listening on [::]:%d (IPv4+IPv6)", self.port)
            return s
        except OSError as e:
            if s is not None:
                s.close()
            log.warning("Dual-stack bind failed, falling back to IPv4: %s", e)
            return None

    def _open_ipv6(self) -> socket.socket | None:
        s = None
        try:
            s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            s.bind((self.host, self.port))
            log.info("UDP listening on [%s]:%d (IPv6)", self.host, self.port)
            return s
        except OSError as e:
            if s is not None:
                s.close()
            log.warning("IPv6 bind on [%s]:%d failed: %s", self.host, self.port, e)
            return None

    def _open_ipv4(self) -> socket.socket | None:
        # MARK: return None on bind failure so __enter__ can raise with context
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            except OSError as e:
                log.warning("SO_RCVBUF rejected: %s", e)
            s.bind((self.host, self.port))
            log.info("UDP listening on %s:%d (IPv4)", self.host, self.port)
            return s
        except OSError as e:
            if s is not None:
                s.close()
            log.warning("IPv4 bind on %s:%d failed: %s", self.host, self.port, e)
            return None

    def __enter__(self):
        if self.host in ("", "::"):
            self.sock = self._open_dual_stack()
            if self.sock is None:
                original_host = self.host
                self.host = "0.0.0.0"
                try:
                    self.sock = self._open_ipv4()
                finally:
                    self.host = original_host
        elif ":" in self.host:
            self.sock = self._open_ipv6()
        else:
            self.sock = self._open_ipv4()
        if self.sock is None:
            raise OSError(
                f"UDP port {self.port} could not be bound (in use, blocked, or invalid host {self.host!r})"
            )
        try:
            self.sock.settimeout(self.timeout)
            if self._fwd.targets:
                bound_host, bound_port, *_ = self.sock.getsockname()
                self._fwd.open(
                    target_filter=lambda target: not _is_obvious_self_forward(bound_host, bound_port, target),
                )
        except Exception:
            # A failed __enter__ is not followed by __exit__ by Python.
            self.__exit__()
            raise
        return self

    def __exit__(self, *args):
        if self.sock:
            self.sock.close()
            self.sock = None
        self._fwd.close()

    def recv_latest(self, *, wait_timeout_s: float | None = None):
        """Block up to ``timeout`` for at least one packet, then drain the
        socket and return only the most recent one. Returns ``(pkt, addr)``
        or ``(None, None)`` on timeout. Non-Forza packets (wrong size) are
        dropped with a one-time warning per distinct size."""
        timeout = self.timeout
        if wait_timeout_s is not None:
            try:
                requested_timeout = float(wait_timeout_s)
            except (TypeError, ValueError, OverflowError):
                requested_timeout = self.timeout
            if math.isfinite(requested_timeout) and requested_timeout > 0.0:
                timeout = requested_timeout
        if timeout != self.timeout:
            self.sock.settimeout(timeout)
        try:
            pkt, addr = self.sock.recvfrom(1500)
        except socket.timeout:
            if timeout != self.timeout:
                self.sock.settimeout(self.timeout)
            return None, None
        except OSError as e:
            # MARK: NIC change, sleep/wake, route flap - log once and skip frame
            with self._state_lock:
                self._receive_error_count += 1
            if timeout != self.timeout:
                self.sock.settimeout(self.timeout)
            log.warning("UDP recvfrom error: %s", e)
            return None, None
        forwarding = self._fwd.active
        if forwarding:
            self._fwd.send(pkt)
        latest = (pkt, addr) if self._accept_datagram(pkt, addr) else None
        self.sock.setblocking(False)
        try:
            for _ in range(MAX_DRAIN_DATAGRAMS):
                pkt, addr = self.sock.recvfrom(1500)
                with self._state_lock:
                    self._drained_packet_count += 1
                if forwarding:
                    self._fwd.send(pkt)
                if self._accept_datagram(pkt, addr):
                    latest = (pkt, addr)
        except (BlockingIOError, OSError):
            pass
        finally:
            self.sock.setblocking(True)
            self.sock.settimeout(self.timeout)
        return latest if latest is not None else (None, None)
