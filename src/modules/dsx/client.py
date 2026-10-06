"""DSX (DualSenseX) UDP client.

Drop-in for DualSense at the set/open/close/connected boundary so the loop can
swap backends. Sends adaptive-trigger data to DSX over UDP instead of writing
HID directly; while active, DSX owns the controller and this never touches HID.

UDP is fire-and-forget — DSX sends no ack — so `connected` means "socket open",
not "DSX is listening". That's the most the transport allows.
"""
import json
import logging
import socket
import threading
from dataclasses import dataclass

from modules.dualsense.adaptive_trigger import off, rigid

from . import dsx_wrapper as tm

log = logging.getLogger("fhds.dsx")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 6969


@dataclass(frozen=True, slots=True)
class DSXDiagnosticsSnapshot:
    connected: bool
    target_host: str
    target_port: int
    packet_count: int
    send_error_count: int
    last_error: str


class DSXClient:
    # The loop checks this capability flag instead of sniffing the class name.
    is_dsx = True

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 startup_pulse_force=180, enable_startup_pulse=True):
        host = str(host).strip()
        port = int(port)
        if not host or not 1 <= port <= 65535:
            raise ValueError("DSX target must use a non-empty host and port 1..65535")
        self._addr = (host, port)
        self._sock = None
        self._connected = False
        self._lock = threading.Lock()
        self._pulse_force = startup_pulse_force
        self._enable_pulse = enable_startup_pulse
        self._pulse_sent = False
        self._pulse_cancel = threading.Event()
        self._sent = 0
        self._send_errors = 0
        self._last_error = ""

    @property
    def connected(self) -> bool:
        return self._connected

    def diagnostics_snapshot(self) -> DSXDiagnosticsSnapshot:
        with self._lock:
            return DSXDiagnosticsSnapshot(
                connected=self._connected,
                target_host=self._addr[0],
                target_port=self._addr[1],
                packet_count=self._sent,
                send_error_count=self._send_errors,
                last_error=self._last_error,
            )

    def open(self):
        if self._sock is not None:
            return
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except OSError as e:
            log.warning("DSX client open failed: %s", e)
            self._connected = False
            self._last_error = str(e)
            raise
        self._connected = True
        log.info("DSX client -> %s:%d (fire-and-forget UDP, no ack)", *self._addr)
        # Only ever send trigger data — the lightbar/RGB belongs to DSX, not me.
        if self._enable_pulse:
            self.request_startup_pulse()

    def request_startup_pulse(self):
        if not self._enable_pulse or self._pulse_sent or not self._connected:
            return
        self._pulse_sent = True
        self._pulse_cancel.clear()
        pulse = rigid(self._pulse_force)
        self.set(pulse, pulse)
        self._pulse_cancel.wait(0.2)
        self.set(off(), off())

    def cancel_startup_pulse(self):
        self._pulse_cancel.set()

    def close(self):
        self._pulse_cancel.set()
        if self._sock is not None:
            self._send(tm.reset_packet())
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._connected = False
        log.info("DSX client closed (%d packets sent)", self._sent)
        return True

    def set(self, left, right, rumble=None, *, visual=None):
        # Keep the native writer's call shape. DSX owns body-haptics output.
        del rumble, visual
        self._send(tm.frames_to_packet(left, right))

    # DSX owns the device and manages its own reconnect/controller selection, so
    # the rest of the DualSense control surface is a no-op here. Implementing it
    # (rather than omitting it) lets the settings tabs call these unconditionally.
    def set_reconnect_enabled(self, enabled): pass
    def set_reconnect_interval(self, interval_s): pass
    def set_selection(self, lock_serial): pass
    def force_reconnect(self): pass

    def _send(self, packet):
        if not self._connected or self._sock is None:
            return
        data = json.dumps(packet, separators=(",", ":")).encode("ascii")
        with self._lock:
            try:
                self._sock.sendto(data, self._addr)
                self._sent += 1
            except (OSError, OverflowError, ValueError) as e:
                self._send_errors += 1
                self._last_error = str(e) or type(e).__name__
                log.debug("DSX send failed: %s", e)
