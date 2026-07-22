from __future__ import annotations

import logging
import math
import struct
import sys
import threading
import time
import zlib
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Callable

# PyPI's hidapi Linux wheel uses libusb, which can't claim the gamepad interface
# (hid-playstation kernel driver owns it). Use a direct /dev/hidraw shim instead.
if sys.platform.startswith("linux"):
    from . import _hidraw as hid
else:
    import hid  # type: ignore[missing-import]  # hidapi exposes a native module without stubs

from . import hidhide
from .adaptive_trigger import off, rigid
from .bt_haptics import (
    BluetoothHapticsPacketBuilder,
    build_bluetooth_power_off_report,
)
from .controller_state import ControllerPhase, ControllerSnapshot
from .input_state import (
    BatteryStatus,
    DualSenseInputState,
    InputReportError,
    InputTransport,
    parse_input_report,
)
from .output_state import ControllerVisualState, NO_VISUAL_CONTROL
from .topology import StableTopology, path_key

if TYPE_CHECKING:
    from ..haptics.frame import CompatibleRumble

log = logging.getLogger("fhds.dualsense")

VENDOR_ID = 0x054C
PRODUCT_IDS = (0x0CE6, 0x0DF2)  # DualSense, DualSense Edge
HANDOVER_RETRY_DELAYS_S = (1.0, 2.0, 5.0)
HANDOVER_INPUT_TIMEOUT_S = 0.25
HANDOVER_INPUT_POLL_S = 0.005
USB_AUDIO_HANDOVER_SETTLE_S = 3.0
IO_RECOVERY_DELAYS_S = (0.25, 1.0, 5.0)

# valid_flag0: 0x01 (R motor), 0x02 (L motor), 0x04 (R trigger), 0x08 (L trigger).
RUMBLE_FLAGS = 0x01 | 0x02
TRIG_FLAGS = 0x04 | 0x08

# MARK: Layout maps — byte offsets per transport
# vf1 = valid_flag1, psav = power_save_control
USB = {"rid": 0x02, "flags": 1, "vf1": 2, "motor_r": 3, "motor_l": 4,
       "psav": 10, "r": 11, "l": 22, "vf2": 39, "lb_setup": 42,
       "player_leds": 44, "lb_r": 45, "lb_g": 46, "lb_b": 47,
       "size": 64, "bt": False}
BT  = {"rid": 0x31, "flags": 2, "vf1": 3, "motor_r": 4, "motor_l": 5,
       "psav": 11, "r": 12, "l": 23, "vf2": 40, "lb_setup": 43,
       "player_leds": 45, "lb_r": 46, "lb_g": 47, "lb_b": 48,
       "size": 78, "bt": True}

# Precomputed CRC of the BT report-header byte 0xA2. zlib.crc32(data, value)
# resumes from `value`, so this lets us CRC straight off the buffer without
# allocating "\xA2" + bytes(buf[:74]) on every write.
_BT_CRC_SEED = zlib.crc32(b"\xA2")

# Cached BT MAC per hidapi path. Populated lazily by _enumerate_dualsenses
# for USB DualSenses (Windows hidapi returns an empty serial for those).
# The lock serialises the open_path/feature-read section so the I/O thread and
# the UI thread don't both try to claim the same exclusive HID handle.
_mac_cache: dict[bytes, str] = {}
_mac_cache_lock = threading.Lock()


@dataclass(frozen=True, slots=True)
class _HandoverRetryState:
    failures: int
    retry_at: float


@dataclass(frozen=True, slots=True)
class _ValidatedHandover:
    info: dict[str, Any]
    device: Any
    report: bytes
    received_at: float


def _force_byte(value: float) -> int:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(value):
        return 0
    return round(max(0.0, min(1.0, value)) * 255.0)


def _safe_reconnect_interval(value: float, default: float = 5.0) -> float:
    try:
        interval = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(interval) or interval <= 0.0:
        return default
    return max(0.1, interval)



def _normalise_identity(value: Any) -> str:
    text = "" if value is None else str(value)
    compact = "".join(character for character in text.lower() if character in "0123456789abcdef")
    return compact if len(compact) == 12 else text.strip().lower()


def _raw_dualsense_interfaces() -> list[dict[str, Any]]:
    """Enumerate only game-pad interfaces and never open a HID handle."""
    return [
        dict(info)
        for info in hid.enumerate(VENDOR_ID, 0)
        if info.get("product_id") in PRODUCT_IDS
        and info.get("usage_page", 1) == 1
        and info.get("usage", 5) == 5
    ]


def _resolve_dualsense_identity(info: dict[str, Any]) -> str:
    """Resolve one interface identity, reading feature 0x09 only if needed."""
    existing = _normalise_identity(info.get("serial_number"))
    if existing:
        info["serial_number"] = existing
        return existing
    key = path_key(info)
    with _mac_cache_lock:
        cached = _mac_cache.get(key)
        if cached is not None:
            info["serial_number"] = cached
            return cached
        device = hid.device()
        try:
            device.open_path(info["path"])
            data = device.get_feature_report(0x09, 64)
        except (OSError, IOError) as exc:
            log.warning("feature 0x09 read failed on %r: %s", info.get("path"), exc)
            return ""
        finally:
            try:
                device.close()
            except Exception:
                pass
        # Feature 0x09 returns bytes 1-6 as the Bluetooth MAC in little-endian.
        if len(data) < 7:
            return ""
        identity = "".join(f"{byte:02x}" for byte in data[6:0:-1])
        _mac_cache[key] = identity
        info["serial_number"] = identity
        return identity


def _enumerate_dualsenses():
    """Resolve visible controllers and prefer USB for duplicate identities."""
    devices = _raw_dualsense_interfaces()
    for info in devices:
        _resolve_dualsense_identity(info)
    # A DualSense plugged in via USB while still paired/awake on BT enumerates
    # twice with the same serial. Prefer wired so the UI shows one row and the
    # connect path picks the cable.
    wired = {
        _normalise_identity(info.get("serial_number"))
        for info in devices
        if info.get("serial_number") and not _is_bluetooth(info)
    }
    return [
        info
        for info in devices
        if not (
            _is_bluetooth(info)
            and _normalise_identity(info.get("serial_number")) in wired
        )
    ]


def _is_bluetooth(info):
    """Detect BT across hidapi backends.

    bus_type values seen in the wild:
      - hidapi-windows:   USB=1, Bluetooth=2
      - hidapi-libusb:    follows libusb (USB always)
      - hidapi-hidraw (Linux): BUS_USB=3, BUS_BLUETOOTH=5
    """
    bus_type = info.get("bus_type")
    if bus_type in (2, 5):
        return True
    if bus_type in (1, 3):
        return False
    path = info.get("path", b"")
    if isinstance(path, str):
        path = path.encode()
    # Linux hidraw nodes don't carry bus info in the path; fall back to USB.
    return b"BTHENUM" in path.upper() or b"BLUETOOTH" in path.upper()


def _log_open_failure(err) -> None:
    # hidapi's "open failed" is opaque; on Linux it almost always means the
    # hidraw node is root-only because the udev rule isn't installed.
    if sys.platform.startswith("linux"):
        log.error(
            "DualSense open failed (%s). Install the udev rule:\n"
            "  sudo cp packaging/linux/70-dualsense.rules /etc/udev/rules.d/\n"
            "  sudo udevadm control --reload-rules && sudo udevadm trigger\n"
            "Then unplug/replug (USB) or re-pair (Bluetooth).", err,
        )
    else:
        log.warning("DualSense open failed (%s) — another app may be holding it open.", err)


def identify_pulse(info: dict, force: int = 180, duration_s: float = 0.2) -> bool:
    """Pulse both triggers briefly on a controller picked from a hidapi info dict.
    Best-effort; returns False if the open or write failed."""
    L = BT if _is_bluetooth(info) else USB
    dev = hid.device()
    try:
        dev.open_path(info["path"])
    except (OSError, IOError) as e:
        log.warning("identify_pulse: open_path failed on %r: %s", info.get("path"), e)
        return False
    try:
        # pulse on
        pulse = rigid(force)
        buf = bytearray(L["size"])
        buf[0] = L["rid"]
        if L["bt"]:
            buf[1] = 0x02
        buf[L["flags"]] = TRIG_FLAGS
        for pos, (mode, params) in ((L["r"], pulse), (L["l"], pulse)):
            buf[pos] = mode
            buf[pos + 1:pos + 1 + len(params)] = params[:10]
        if L["bt"]:
            crc = zlib.crc32(memoryview(buf)[:74], _BT_CRC_SEED)
            struct.pack_into("<I", buf, 74, crc)
        dev.write(buf)
        time.sleep(duration_s)
        # pulse off
        rest = off()
        buf = bytearray(L["size"])
        buf[0] = L["rid"]
        if L["bt"]:
            buf[1] = 0x02
        buf[L["flags"]] = TRIG_FLAGS
        for pos, (mode, params) in ((L["r"], rest), (L["l"], rest)):
            buf[pos] = mode
            buf[pos + 1:pos + 1 + len(params)] = params[:10]
        if L["bt"]:
            crc = zlib.crc32(memoryview(buf)[:74], _BT_CRC_SEED)
            struct.pack_into("<I", buf, 74, crc)
        dev.write(buf)
        return True
    except (OSError, IOError) as e:
        log.warning("identify_pulse: write failed on %r: %s", info.get("path"), e)
        return False
    finally:
        try:
            dev.close()
        except Exception as exc:
            log.debug("identify_pulse: close failed on %r: %s", info.get("path"), exc)


class DualSense:
    """DualSense trigger writer with optional compatible rumble.

    Resilient: starts without a controller and retries every
    ``reconnect_interval_s`` seconds. Drops writes silently while disconnected.
    Existing trigger-only callers leave all rumble bytes unclaimed.
    """

    def __init__(
        self,
        startup_pulse_force: int = 180,
        enable_startup_pulse: bool = True,
        reconnect_interval_s: float = 5.0,
        enable_reconnect: bool = False,
        controller_lock_serial: str = "",
        usb_handover_ready: Callable[[], bool] | None = None,
        usb_handover_settle_s: float = USB_AUDIO_HANDOVER_SETTLE_S,
    ):
        self.dev = None
        self.dev_path = None
        self.dev_serial = None
        self._current_info: dict[str, Any] | None = None
        self.lay = USB
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._snapshot = ControllerSnapshot()
        self._left = self._right = off()
        self._rumble: CompatibleRumble | None = None
        self._visual = NO_VISUAL_CONTROL
        self._pending_rumble_release = None
        self._bt_haptics_pending: bytes | None = None
        self._bt_haptics_dropped = 0
        self._bt_haptics_failed = False
        self._bt_haptics_failure_logged = False
        self._bt_haptics_streamed = False
        self._bt_haptics_builder = BluetoothHapticsPacketBuilder()
        self._dirty = False
        self._running = False
        self._thread: threading.Thread | None = None
        self._lifecycle_lock = threading.Lock()
        # Signalled by set() and close() so the I/O thread sleeps until a new
        # frame is ready instead of busy-polling at 1 kHz.
        self._wake = threading.Event()
        self._pulse_force = startup_pulse_force
        self._enable_startup_pulse = enable_startup_pulse
        self._reconnect_interval = _safe_reconnect_interval(reconnect_interval_s)
        self._enable_reconnect = enable_reconnect
        self._ever_connected = False
        self._open_hinted = False
        self._waiting_hinted = False
        self._last_attempt = -1e9
        # Idle-input watchdog. DualSense streams input reports continuously
        # (hundreds of Hz). When the controller drops, the stream stops and
        # the nonblocking read returns empty for `_input_idle_timeout`.
        self._input_idle_timeout = 3.0
        self._last_input_at = 0.0
        self._input_consumer: Callable[[DualSenseInputState, float], None] | None = None
        self._input_parse_errors = 0
        self._input_parse_error_streak = 0
        self._input_consumer_errors = 0
        self._io_recovery_count = 0
        self._reconnect_requested = False
        self._topology = StableTopology(required_observations=2)
        self._topology_interval = 1.0
        self._last_topology_scan = -1e9
        self._handover_retries: dict[bytes, _HandoverRetryState] = {}
        self._handover_settle_deadlines: dict[bytes, float] = {}
        self._handover_readiness_logged: set[bytes] = set()
        self._handover_input_timeout = HANDOVER_INPUT_TIMEOUT_S
        self._usb_handover_ready = usb_handover_ready
        try:
            settle_s = float(usb_handover_settle_s)
        except (TypeError, ValueError, OverflowError):
            settle_s = USB_AUDIO_HANDOVER_SETTLE_S
        self._usb_handover_settle_s = (
            settle_s
            if math.isfinite(settle_s) and settle_s >= 0.0
            else USB_AUDIO_HANDOVER_SETTLE_S
        )
        self._transport_recovery_identity = ""
        # Locked controller serial (empty = first-found). Persists across launches.
        self._lock_serial = controller_lock_serial

    @property
    def connected(self) -> bool:
        return self.snapshot().connected

    @property
    def transport(self) -> str | None:
        snapshot = self.snapshot()
        transport = snapshot.transport if snapshot.connected else None
        return transport.value if transport is not None else None

    @property
    def persistent(self) -> bool:
        # Compatibility property for older UI/tests. R7 never treats a held
        # HID handle as proof that a powered-off controller is still online.
        return False

    def snapshot(self) -> ControllerSnapshot:
        with self._state_lock:
            return self._snapshot

    def _update_snapshot(self, **changes) -> ControllerSnapshot:
        with self._state_lock:
            self._snapshot = replace(self._snapshot, **changes)
            return self._snapshot

    @property
    def bt_haptics_dropped(self) -> int:
        return self._bt_haptics_dropped

    @property
    def bt_haptics_failed(self) -> bool:
        return self._bt_haptics_failed

    def open(self):
        """Start the I/O thread. Never raises if the controller is absent."""
        with self._lifecycle_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            log.info("HidHide: %s", "detected" if hidhide.is_detected() else "not detected")
            self._log_reconnect_mode()
            self._wake.clear()
            self._running = True
            thread = threading.Thread(
                target=self._io,
                name="fhds-dualsense-io",
                daemon=True,
            )
            self._thread = thread
            thread.start()

    def _log_reconnect_mode(self) -> None:
        if self._enable_reconnect:
            log.info("Reconnect mode: auto-reconnect every %.0fs after drops",
                     self._reconnect_interval)
        else:
            log.info("Reconnect mode: automatic retry after a full drop is disabled.")

    def close(self):
        self._running = False
        self._wake.set()
        with self._lifecycle_lock:
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if thread is not None and thread.is_alive():
            log.error("DualSense I/O thread did not stop within 2 seconds")
            return
        with self._lifecycle_lock:
            if self._thread is thread:
                self._thread = None
        # The I/O thread normally owns disconnect and HID close in its finally
        # block. This fallback only covers an object that never had a live worker.
        if thread is None:
            self._disconnect()

    def set(
        self,
        left,
        right,
        rumble: CompatibleRumble | None = None,
        *,
        visual: ControllerVisualState | None = None,
    ):
        visual = (visual or NO_VISUAL_CONTROL).normalized()
        with self._lock:
            if rumble is None and self._dirty and self._is_rumble_release(self._rumble):
                self._pending_rumble_release = (
                    self._left,
                    self._right,
                    self._rumble,
                    self._visual,
                )
            elif rumble is not None:
                self._pending_rumble_release = None
            self._left = left
            self._right = right
            self._rumble = rumble
            self._visual = visual
            self._dirty = True
        self._wake.set()

    def queue_bt_haptics(self, samples: bytes) -> bool:
        samples = bytes(samples)
        if len(samples) != 64:
            raise ValueError("Bluetooth haptics payload must be exactly 64 bytes")
        if self.transport != "bluetooth" or self._bt_haptics_failed:
            return False
        with self._lock:
            if self._bt_haptics_pending is not None:
                self._bt_haptics_dropped += 1
            self._bt_haptics_pending = samples
        self._wake.set()
        return True

    @staticmethod
    def _is_rumble_release(rumble: CompatibleRumble | None) -> bool:
        return (
            rumble is not None
            and _force_byte(rumble.low_frequency) == 0
            and _force_byte(rumble.high_frequency) == 0
        )

    def _take_pending_output(self):
        with self._lock:
            if self._pending_rumble_release is not None:
                frame = self._pending_rumble_release
                self._pending_rumble_release = None
                # The latest trigger-only frame remains dirty and must follow
                # this explicit motor release without waiting for a watchdog tick.
                self._wake.set()
                return frame
            if not self._dirty:
                return None
            frame = self._left, self._right, self._rumble, self._visual
            self._dirty = False
            return frame

    def _take_pending_bt_haptics(self) -> bytes | None:
        with self._lock:
            samples = self._bt_haptics_pending
            self._bt_haptics_pending = None
            return samples

    def _has_pending_output(self) -> bool:
        with self._lock:
            return bool(
                self._pending_rumble_release is not None
                or self._dirty
                or self._bt_haptics_pending is not None
            )

    def set_reconnect_enabled(self, enabled: bool) -> None:
        """Live-toggle from the Settings tab and wake the HID I/O thread."""
        new = bool(enabled)
        if new == self._enable_reconnect:
            return
        self._enable_reconnect = new
        self._wake.set()
        if new:
            log.info("Auto-reconnect enabled - drops will retry every %.0fs.",
                     self._reconnect_interval)
        else:
            log.info("Auto-reconnect disabled.")

    def set_reconnect_interval(self, interval_s: float) -> None:
        new = _safe_reconnect_interval(interval_s)
        if new == self._reconnect_interval:
            return
        self._reconnect_interval = new
        self._wake.set()
        log.info("Reconnect interval = %.1fs", new)

    def set_input_consumer(
        self,
        consumer: Callable[[DualSenseInputState, float], None] | None,
    ) -> None:
        """Hot-switch the nonblocking consumer used by the XInput bridge.

        The callback runs on this object's existing HID I/O thread.  It must
        only publish a latest snapshot and return; ViGEm calls belong to the
        bridge worker.
        """
        with self._lock:
            self._input_consumer = consumer
        self._wake.set()

    def _publish_input(self, data, received_at: float) -> bool:
        transport = (
            InputTransport.BLUETOOTH if self.lay["bt"] else InputTransport.USB
        )
        try:
            state = parse_input_report(data, transport)
        except InputReportError as exc:
            self._input_parse_errors += 1
            self._input_parse_error_streak += 1
            streak = self._input_parse_error_streak
            if streak in (1, 8, 32, 128) or streak % 512 == 0:
                log.warning(
                    "DualSense input report rejected (%d consecutive, %d total): %s",
                    streak,
                    self._input_parse_errors,
                    exc,
                )
            return False
        if self._input_parse_error_streak >= 8:
            log.info(
                "DualSense input reports recovered after %d consecutive rejection(s)",
                self._input_parse_error_streak,
            )
        self._input_parse_error_streak = 0
        self._last_input_at = received_at
        self._ever_connected = True
        self._transport_recovery_identity = ""
        self._update_snapshot(
            phase=ControllerPhase.CONNECTED,
            transport=transport,
            identity=self.dev_serial or "",
            last_input_at=received_at,
            battery_level=state.battery_level,
            battery_status=state.battery_status,
            error="",
        )
        with self._lock:
            consumer = self._input_consumer
        if consumer is None:
            return True
        try:
            consumer(state, received_at)
        except Exception as exc:
            self._input_consumer_errors += 1
            if self._input_consumer_errors == 1:
                log.warning("DualSense input consumer failed: %s", exc)
        return True

    def _drain_input_queue(
        self,
        *,
        max_reports: int = 256,
        stop_when_not_running: bool = False,
        publish_latest_only: bool = False,
    ) -> bool:
        """Drain queued HID input without mistaking backlog for a live device.

        Windows can retain a short queue of reports after a controller powers
        off.  Reading one report per UI tick makes those stale reports look
        alive.  Draining in one I/O iteration bounds that stale period while
        retaining the existing contract that every valid report reaches the
        optional XInput consumer.  Xbox bridge mode can opt into
        ``publish_latest_only`` so an old Bluetooth backlog is collapsed to
        the newest valid controller state instead of being replayed as fresh
        input.

        Returns ``True`` when the safety limit was reached, which tells the I/O
        loop to run again immediately instead of sleeping with more input
        potentially queued.
        """
        count = 0
        limit = max(1, int(max_reports))
        queued: list[bytes | bytearray | memoryview | list[int]] = []
        while count < limit:
            data = self.dev.read(self.lay["size"], timeout_ms=0)
            if not data:
                break
            count += 1
            if publish_latest_only:
                queued.append(data)
            else:
                self._publish_input(data, time.monotonic())
            if stop_when_not_running and not self._running:
                break
            if not publish_latest_only and self._has_pending_output():
                break

        if publish_latest_only and queued:
            received_at = time.monotonic()
            # A malformed tail report must not hide the newest valid state
            # immediately before it.
            for data in reversed(queued):
                if self._publish_input(data, received_at):
                    break
        return count >= limit

    def set_selection(self, lock_serial: str) -> None:
        """Store new lock serial for the next connect attempt.
        Does not disconnect; call force_reconnect() to hot-swap."""
        self._lock_serial = _normalise_identity(lock_serial)

    def force_reconnect(self) -> None:
        """Queue a reconnect and revive the sole HID worker if it died."""
        with self._lock:
            self._reconnect_requested = True
        self._update_snapshot(phase=ControllerPhase.RECONNECTING, error="")
        self._wake.set()
        with self._lifecycle_lock:
            thread = self._thread
        if thread is None or not thread.is_alive():
            log.warning("DualSense reconnect is restarting an unavailable HID I/O worker")
            self.open()

    def _take_reconnect_request(self) -> bool:
        with self._lock:
            requested = self._reconnect_requested
            self._reconnect_requested = False
            return requested

    def _topology_handover_candidate(self, now: float) -> dict[str, Any] | None:
        """Return a stable same-controller transport candidate, if any."""
        if now - self._last_topology_scan < self._topology_interval:
            return None
        self._last_topology_scan = now
        try:
            visible = _raw_dualsense_interfaces()
        except Exception as exc:
            log.debug("DualSense topology enumerate failed: %s", exc)
            return None
        stable = self._topology.observe(visible)
        present_keys = {path_key(info) for info in visible}
        for key in tuple(self._handover_retries):
            if key not in present_keys:
                self._handover_retries.pop(key, None)
        for key in tuple(self._handover_settle_deadlines):
            if key not in present_keys:
                self._handover_settle_deadlines.pop(key, None)
                self._handover_readiness_logged.discard(key)

        snapshot = self.snapshot()
        current_identity = _normalise_identity(snapshot.identity or self.dev_serial)
        if not snapshot.connected or not current_identity or self.dev is None:
            return None

        current_is_bt = self.lay["bt"]
        current_present = self._topology.is_present(self.dev_path)
        input_age = snapshot.input_age(now) or 0.0
        for info in stable:
            if path_key(info) == path_key({"path": self.dev_path or b""}):
                continue
            candidate_identity = _normalise_identity(info.get("serial_number"))
            key = path_key(info)
            retry = self._handover_retries.get(key)
            if retry is not None and now < retry.retry_at:
                continue
            if not candidate_identity:
                candidate_identity = _mac_cache.get(key, "")
            if not candidate_identity:
                candidate_identity = _resolve_dualsense_identity(info)
            if not candidate_identity:
                delay = self._schedule_handover_retry(key, now)
                log.debug(
                    "DualSense candidate identity unavailable on %r; retaining current "
                    "transport and retrying in %.0fs",
                    info.get("path"),
                    delay,
                )
                continue
            if _normalise_identity(candidate_identity) != current_identity:
                continue
            info["serial_number"] = _normalise_identity(candidate_identity)

            candidate_is_bt = _is_bluetooth(info)
            if current_is_bt and not candidate_is_bt:
                if not self._usb_audio_handover_ready(key, now):
                    continue
                return info
            if (
                not current_is_bt
                and candidate_is_bt
                and not current_present
                and input_age >= 0.75
            ):
                return info
        return None

    def _usb_audio_handover_ready(self, key: bytes, now: float) -> bool:
        """Gate BT -> USB until the Windows USB audio endpoint is settled."""
        callback = self._usb_handover_ready
        if callback is None:
            return True

        deadline = self._handover_settle_deadlines.get(key)
        if deadline is None:
            deadline = now + self._usb_handover_settle_s
            self._handover_settle_deadlines[key] = deadline
            if self._usb_handover_settle_s > 0.0:
                log.info(
                    "DualSense USB audio settle window started (%.1fs); "
                    "retaining Bluetooth",
                    self._usb_handover_settle_s,
                )
                return False
        if now < deadline:
            return False

        try:
            ready = bool(callback())
        except Exception as exc:
            delay = self._schedule_handover_retry(key, now)
            log.warning(
                "DualSense USB audio readiness probe failed (%s); retained BT; "
                "retrying this path in %.0fs",
                exc,
                delay,
            )
            return False
        if not ready:
            delay = self._schedule_handover_retry(key, now)
            log.warning(
                "DualSense USB audio endpoint is not ready; retained BT; "
                "retrying this path in %.0fs",
                delay,
            )
            return False
        if key not in self._handover_readiness_logged:
            self._handover_readiness_logged.add(key)
            log.info("DualSense USB audio readiness gate passed")
        return True

    def _schedule_handover_retry(self, key: bytes, now: float) -> float:
        previous = self._handover_retries.get(key)
        failures = 1 if previous is None else previous.failures + 1
        delay = HANDOVER_RETRY_DELAYS_S[
            min(failures - 1, len(HANDOVER_RETRY_DELAYS_S) - 1)
        ]
        self._handover_retries[key] = _HandoverRetryState(
            failures=failures,
            retry_at=now + delay,
        )
        return delay

    @staticmethod
    def _close_candidate(device) -> None:
        try:
            device.close()
        except Exception:
            pass

    def _validate_handover_candidate(
        self,
        target: dict[str, Any],
    ) -> tuple[_ValidatedHandover | None, str]:
        """Open and validate a candidate without touching the active handle."""
        candidate = hid.device()
        try:
            candidate.open_path(target["path"])
            candidate.set_nonblocking(True)
        except (OSError, IOError) as exc:
            self._close_candidate(candidate)
            return None, f"open failed: {exc}"

        layout = BT if _is_bluetooth(target) else USB
        transport = (
            InputTransport.BLUETOOTH if layout["bt"] else InputTransport.USB
        )
        deadline = time.monotonic() + max(0.0, self._handover_input_timeout)
        last_error = "no input report"
        while True:
            try:
                report = candidate.read(layout["size"], timeout_ms=0)
            except (OSError, IOError) as exc:
                self._close_candidate(candidate)
                return None, f"read failed: {exc}"
            if report:
                try:
                    parse_input_report(report, transport)
                except InputReportError as exc:
                    last_error = str(exc)
                else:
                    received_at = time.monotonic()
                    return (
                        _ValidatedHandover(
                            info=dict(target),
                            device=candidate,
                            report=bytes(report),
                            received_at=received_at,
                        ),
                        "",
                    )
            if time.monotonic() >= deadline:
                self._close_candidate(candidate)
                return None, last_error
            time.sleep(HANDOVER_INPUT_POLL_S)

    def _silence_active_handle_for_handover(self) -> None:
        if self.dev is None:
            return
        if self.lay["bt"] and self._bt_haptics_streamed:
            try:
                self._safe_write(
                    self._bt_haptics_builder.build(
                        bytes(64),
                        left=off(),
                        right=off(),
                    )
                )
            except Exception as exc:
                log.debug("Bluetooth handover silence frame failed: %s", exc)
        with self._lock:
            rumble = self._rumble
        zero_rumble = type(rumble)() if rumble is not None else None
        try:
            self._safe_write(self._build(off(), off(), zero_rumble))
        except Exception as exc:
            log.debug("DualSense handover trigger release failed: %s", exc)

    def _end_bluetooth_session_for_usb_handover(self) -> tuple[bool, str]:
        """End the old Bluetooth session before USB takes haptics ownership."""
        if self.dev is None or not self.lay["bt"]:
            return False, "active Bluetooth handle unavailable"
        try:
            transferred = self.dev.send_feature_report(
                build_bluetooth_power_off_report()
            )
        except Exception as exc:
            return False, f"Bluetooth control feature report failed: {exc}"
        if not isinstance(transferred, int) or transferred <= 0:
            return False, f"Bluetooth control feature report returned {transferred!r}"
        log.info(
            "DualSense Bluetooth control teardown accepted (%s byte(s))",
            transferred,
        )
        return True, ""

    def _adopt_handover(
        self,
        validated: _ValidatedHandover,
    ) -> tuple[bool, str]:
        """Commit an already validated handle without a disconnected snapshot."""
        old_device = self.dev
        old_bus = "BT" if self.lay["bt"] else "USB"
        target = validated.info
        new_layout = BT if _is_bluetooth(target) else USB
        new_bus = "BT" if new_layout["bt"] else "USB"

        self._silence_active_handle_for_handover()
        if self.lay["bt"] and not new_layout["bt"]:
            ended, reason = self._end_bluetooth_session_for_usb_handover()
            if not ended:
                self._close_candidate(validated.device)
                return False, reason
        self.dev = validated.device
        self.dev_path = target.get("path")
        self.dev_serial = _normalise_identity(target.get("serial_number"))
        self._current_info = dict(target)
        self.lay = new_layout
        self._open_hinted = self._waiting_hinted = False
        with self._lock:
            self._bt_haptics_pending = None
            self._bt_haptics_failed = False
            self._bt_haptics_failure_logged = False
            self._bt_haptics_streamed = False
            self._bt_haptics_builder.reset()
            self._dirty = True
        if not self._publish_input(validated.report, validated.received_at):
            # The report was parsed during validation, so reaching this branch
            # would indicate an internal transport/layout regression.
            log.error("Validated DualSense handover report was rejected during commit")
        if old_device is not None:
            try:
                old_device.close()
            except Exception as exc:
                log.debug("Old DualSense handle close after handover failed: %s", exc)
        self._wake.set()
        log.info("DualSense transport handover complete: %s -> %s", old_bus, new_bus)
        return True, ""

    def _perform_handover(
        self,
        target: dict[str, Any],
        *,
        now: float | None = None,
    ) -> bool:
        """Validate then atomically switch transport on the sole I/O thread."""
        attempted_at = time.monotonic() if now is None else now
        target_key = path_key(target)
        old_bus = "BT" if self.lay["bt"] else "USB"
        new_bus = "BT" if _is_bluetooth(target) else "USB"
        validated, reason = self._validate_handover_candidate(target)
        if validated is None:
            delay = self._schedule_handover_retry(target_key, attempted_at)
            log.warning(
                "DualSense %s candidate validation failed (%s); retained %s; "
                "retrying this path in %.0fs",
                new_bus,
                reason,
                old_bus,
                delay,
            )
            return False
        adopted, reason = self._adopt_handover(validated)
        if not adopted:
            delay = self._schedule_handover_retry(target_key, attempted_at)
            log.warning(
                "DualSense %s handover teardown failed (%s); retained %s; "
                "retrying this path in %.0fs",
                new_bus,
                reason,
                old_bus,
                delay,
            )
            return False
        self._handover_retries.pop(target_key, None)
        self._handover_settle_deadlines.pop(target_key, None)
        self._handover_readiness_logged.discard(target_key)
        return True

    def _safe_write(self, buf) -> None:
        """Best-effort write — used for startup pulses, power-saver, and the
        off-pulse during disconnect, all of which run while the device may be
        about to go away."""
        try:
            self.dev.write(buf)
        except Exception:
            pass

    # MARK: connect / disconnect helpers
    def _try_connect(self, selected_info: dict[str, Any] | None = None, *, switching: bool = False) -> bool:
        self._update_snapshot(
            phase=(
                ControllerPhase.SWITCHING
                if switching
                else ControllerPhase.RECONNECTING
                if self._ever_connected
                else ControllerPhase.CONNECTING
            ),
            transport=None,
            identity="",
            last_input_at=None,
            battery_level=None,
            battery_status=BatteryStatus.UNKNOWN,
            error="",
        )
        try:
            devices = (
                [dict(selected_info)]
                if selected_info is not None
                else _enumerate_dualsenses()
            )
        except Exception as e:
            log.warning("DualSense enumeration failed: %s", e)
            self._update_snapshot(
                phase=ControllerPhase.ERROR,
                transport=None,
                identity="",
                last_input_at=None,
                battery_level=None,
                battery_status=BatteryStatus.UNKNOWN,
                error=str(e) or type(e).__name__,
            )
            return False
        # Log enumeration deltas so I can see if the OS hides/exposes the device.
        n = len(devices)
        if n != getattr(self, "_last_enum_count", -1):
            self._last_enum_count = n
            if n == 0:
                log.info("HID enumerate: 0 DualSense interfaces visible "
                         "(controller off, cable loose, or hidden by HidHide/Steam Input).")
            else:
                summary = ", ".join(
                    f"[pid=0x{d.get('product_id', 0):04x} "
                    f"up={d.get('usage_page')} u={d.get('usage')} "
                    f"bus={d.get('bus_type')}]"
                    for d in devices
                )
                log.info("HID enumerate: %d DualSense interface(s): %s", n, summary)

        # Selection: empty list -> wait; lock match -> use it; else first device.
        if not devices:
            if not self._waiting_hinted:
                log.info("Waiting for DualSense - retrying every %.0fs", self._reconnect_interval)
                self._waiting_hinted = True
            self._update_snapshot(
                phase=(ControllerPhase.RECONNECTING if self._ever_connected else ControllerPhase.WAITING),
                transport=None,
                identity="",
                last_input_at=None,
                battery_level=None,
                battery_status=BatteryStatus.UNKNOWN,
            )
            return False
        info = None
        recovery_identity = _normalise_identity(self._transport_recovery_identity)
        if recovery_identity:
            info = next(
                (
                    item
                    for item in devices
                    if _normalise_identity(item.get("serial_number")) == recovery_identity
                ),
                None,
            )
            if info is None:
                return False
        elif self._lock_serial:
            locked_identity = _normalise_identity(self._lock_serial)
            info = next((d for d in devices
                         if _normalise_identity(d.get("serial_number")) == locked_identity), None)
        if info is None:
            info = devices[0]
        dev = None
        try:
            dev = hid.device()
            dev.open_path(info["path"])
            dev.set_nonblocking(True)
        except (OSError, IOError) as e:
            try:
                if dev is not None:
                    dev.close()
            except Exception:
                pass
            if not self._open_hinted:
                _log_open_failure(e)
                log.warning("open_path failed on %r - another process likely holds the "
                            "device exclusive (Steam Input, SISR, reWASD).",
                            info.get("path"))
                self._open_hinted = True
            self._update_snapshot(
                phase=ControllerPhase.ERROR,
                transport=None,
                identity="",
                last_input_at=None,
                battery_level=None,
                battery_status=BatteryStatus.UNKNOWN,
                error=str(e) or type(e).__name__,
            )
            return False
        self.dev = dev
        self.dev_path = info.get("path")
        self.dev_serial = _normalise_identity(info.get("serial_number"))
        self._current_info = dict(info)
        self.lay = BT if _is_bluetooth(info) else USB
        self._open_hinted = self._waiting_hinted = False
        self._last_input_at = time.monotonic()
        transport = InputTransport.BLUETOOTH if self.lay["bt"] else InputTransport.USB
        self._update_snapshot(
            phase=ControllerPhase.SWITCHING if switching else ControllerPhase.CONNECTING,
            transport=transport,
            identity=self.dev_serial,
            last_input_at=None,
            battery_level=None,
            battery_status=BatteryStatus.UNKNOWN,
            error="",
        )
        with self._lock:
            self._bt_haptics_pending = None
            self._bt_haptics_failed = False
            self._bt_haptics_failure_logged = False
            self._bt_haptics_streamed = False
            self._bt_haptics_builder.reset()
        bus = "BT" if self.lay["bt"] else "USB"
        product_id = int((self._current_info or {}).get("product_id") or 0)
        log.info(
            "DualSense HID opened (%s, pid=0x%04x); waiting for a valid input report",
            bus,
            product_id,
        )

        if self._enable_startup_pulse and not switching:
            pulse = rigid(self._pulse_force)
            self._safe_write(self._build(pulse, pulse))
            time.sleep(0.2)
            self._safe_write(self._build(off(), off()))
        # The previously sent frame may not change while the device is absent.
        # Requeue it explicitly so a reconnect restores triggers and rumble.
        with self._lock:
            self._dirty = True
        self._wake.set()
        # MARK: Power saver — one-shot at connect
        # self._safe_write(self._build_power_saver()) # Commented out due to report discussions/27
        return True

    def _disconnect(
        self,
        reason: str = "",
        *,
        next_phase: ControllerPhase | None = None,
    ):
        was_connected = self.dev is not None
        if was_connected:
            if self.lay["bt"] and self._bt_haptics_streamed:
                try:
                    self._safe_write(
                        self._bt_haptics_builder.build(
                            bytes(64),
                            left=off(),
                            right=off(),
                        )
                    )
                except Exception as exc:
                    log.debug("Bluetooth haptics shutdown frame failed: %s", exc)
                self._bt_haptics_streamed = False
            with self._lock:
                rumble = self._rumble
                pending_release = self._pending_rumble_release
                self._pending_rumble_release = None
            if rumble is not None:
                zero_rumble = type(rumble)()
            elif pending_release is not None:
                zero_rumble = type(pending_release[2])()
            else:
                zero_rumble = None
            try:
                self._safe_write(self._build(off(), off(), zero_rumble))
            except Exception as exc:
                log.debug("DualSense shutdown frame failed: %s", exc)
            try:
                self.dev.close()
            except Exception:
                pass
        self.dev = None
        self.dev_path = None
        self.dev_serial = None
        self._current_info = None
        self._handover_retries.clear()
        self._handover_settle_deadlines.clear()
        self._handover_readiness_logged.clear()
        with self._lock:
            self._bt_haptics_pending = None
        self._update_snapshot(
            phase=(
                next_phase
                if next_phase is not None
                else ControllerPhase.RECONNECTING
                if self._running
                and (self._enable_reconnect or self._transport_recovery_identity)
                and self._ever_connected
                else ControllerPhase.WAITING
            ),
            transport=None,
            identity="",
            last_input_at=None,
            battery_level=None,
            battery_status=BatteryStatus.UNKNOWN,
            error=reason,
        )
        # Skip the "disconnected" warning during intentional shutdown
        if was_connected and self._running and next_phase is not ControllerPhase.SWITCHING:
            suffix = f" ({reason})" if reason else ""
            if self._enable_reconnect:
                log.warning("DualSense disconnected%s — retrying every %.0fs",
                            suffix, self._reconnect_interval)
            else:
                log.warning("DualSense disconnected%s — auto-reconnect is disabled "
                            "(enable it in the Settings tab to recover automatically).",
                            suffix)

    # MARK: I/O thread — reconnect when missing, write when dirty, watchdog on idle input
    def _io(self):
        failures = 0
        try:
            while self._running:
                try:
                    self._io_loop()
                    break
                except Exception as exc:
                    if not self._running:
                        break
                    failures += 1
                    self._io_recovery_count += 1
                    delay = IO_RECOVERY_DELAYS_S[
                        min(failures - 1, len(IO_RECOVERY_DELAYS_S) - 1)
                    ]
                    failure = str(exc) or type(exc).__name__
                    log.exception(
                        "DualSense I/O session failed; recovering in %.2fs",
                        delay,
                    )
                    self._disconnect(
                        f"I/O failure: {failure}",
                        next_phase=(
                            ControllerPhase.RECONNECTING
                            if self._enable_reconnect
                            else ControllerPhase.ERROR
                        ),
                    )
                    self._last_attempt = -1e9
                    self._wake.clear()
                    if self._running:
                        self._wake.wait(delay)
        finally:
            self._running = False
            self._disconnect(
                next_phase=ControllerPhase.WAITING,
            )

    def _io_loop(self):
        manual_attempt = False
        while self._running:
            now = time.monotonic()

            if self._take_reconnect_request():
                self._disconnect("user-initiated reconnect")
                self._last_attempt = -1e9
                manual_attempt = True

            # --- Disconnected: throttle reconnect attempts ---
            # Initial connect always retries on the reconnect_interval — the
            # user needs the controller to come up at startup. The toggle only
            # gates *re*connects: once we've been connected at least once,
            # subsequent drops are not retried when enable_reconnect is False.
            if self.dev is None:
                if (
                    self._enable_reconnect
                    or not self._ever_connected
                    or manual_attempt
                    or bool(self._transport_recovery_identity)
                ):
                    if now - self._last_attempt >= self._reconnect_interval:
                        self._last_attempt = now
                        self._try_connect()  # logs success / waiting / open-failure itself
                        manual_attempt = False
                self._wake.wait(0.5)
                self._wake.clear()
                continue

            handover = self._topology_handover_candidate(now)
            if handover is not None:
                self._perform_handover(handover, now=now)
                continue

            # --- Connected: drain one input report for the liveness watchdog.
            # timeout_ms=0 forces a truly nonblocking read — set_nonblocking()
            # is unreliable on Windows Bluetooth, where read() would otherwise
            # block until the BT stack times out (~30 s after a drop).
            try:
                with self._lock:
                    input_consumer_enabled = self._input_consumer is not None
                # The Xbox bridge consumes only the newest controller state.
                # Continuous Bluetooth 0x36 haptics must not reduce this to a
                # one-report drain and turn the Windows HID queue into latency.
                read_limit = (
                    256
                    if input_consumer_enabled
                    else (1 if self._has_pending_output() else 256)
                )
                input_backlog = self._drain_input_queue(
                    max_reports=read_limit,
                    stop_when_not_running=True,
                    publish_latest_only=input_consumer_enabled,
                )
            except OSError as e:
                self._disconnect(f"read failed: {e}")
                continue
            watchdog_now = time.monotonic()
            if watchdog_now - self._last_input_at >= self._input_idle_timeout:
                self._disconnect(f"no input for {self._input_idle_timeout:.0f}s")
                continue

            # A newly opened handle is not public connectivity until one full,
            # validated input report arrives. Do not restore output earlier.
            if not self.connected:
                self._wake.wait(0.01)
                self._wake.clear()
                continue

            # A saturated batch means older input may still be queued.  Catch
            # up to the newest physical state before spending time on BT HID
            # output; the producer already coalesces output to its latest frame.
            if input_consumer_enabled and input_backlog:
                continue

            # --- Write the latest queued frame, if any ---
            pending = self._take_pending_output()
            haptics = self._take_pending_bt_haptics()
            haptics_will_send = bool(
                haptics is not None and self.lay["bt"] and not self._bt_haptics_failed
            )
            if pending is not None:
                left, right, rumble, visual = pending
                # Report 0x36 already carries the latest trigger and visual
                # state.  Keep normal BT reports only when they also carry a
                # compatible-rumble command (including an explicit release).
                if not (haptics_will_send and rumble is None):
                    try:
                        n = self.dev.write(
                            self._build(left, right, rumble, visual=visual)
                        )
                    except Exception as e:
                        self._disconnect(f"write failed: {e}")
                        continue
                    if n is not None and n <= 0:
                        self._disconnect(f"write returned {n}")
                        continue

            if haptics_will_send:
                try:
                    n = self.dev.write(self._build_bt_haptics(haptics))
                except Exception as e:
                    self._mark_bt_haptics_failed(f"write failed: {e}")
                else:
                    if n is not None and n <= 0:
                        self._mark_bt_haptics_failed(f"write returned {n}")
                    else:
                        self._bt_haptics_streamed = True

            # Clear before checking the queue so a producer cannot set the event
            # between wait() returning and clear(). That race used to lose roughly
            # one third of 94 Hz Bluetooth audio wakes on Windows.
            self._wake.clear()
            if self._has_pending_output():
                continue
            if input_backlog:
                continue
            # Sleep until set()/queue_bt_haptics() publishes a new frame, or wake
            # periodically to recheck the input watchdog.
            if input_consumer_enabled:
                poll_interval = 0.004 if self.lay["bt"] else 0.001
            else:
                poll_interval = 0.05
            self._wake.wait(poll_interval)

    def _new_report(self):
        L = self.lay
        buf = bytearray(L["size"])
        buf[0] = L["rid"]
        if L["bt"]:
            buf[1] = 0x02
        return buf

    def _finalize_bt_crc(self, buf):
        if self.lay["bt"]:
            crc = zlib.crc32(memoryview(buf)[:74], _BT_CRC_SEED)
            struct.pack_into("<I", buf, 74, crc)

    def _build(
        self,
        left,
        right,
        rumble: CompatibleRumble | None = None,
        *,
        visual: ControllerVisualState | None = None,
    ):
        L = self.lay
        buf = self._new_report()
        flags = TRIG_FLAGS
        if rumble is not None:
            flags |= RUMBLE_FLAGS
            buf[L["motor_r"]] = _force_byte(rumble.high_frequency)
            buf[L["motor_l"]] = _force_byte(rumble.low_frequency)
        buf[L["flags"]] = flags
        for pos, (mode, params) in ((L["r"], right), (L["l"], left)):
            buf[pos] = mode
            # params elements are already clamped to 0-255 by triggers.py;
            # bytearray slice-assignment accepts a tuple of ints directly.
            buf[pos + 1:pos + 1 + len(params)] = params[:10]
        visual = (visual or NO_VISUAL_CONTROL).normalized()
        if visual.lightbar is not None:
            buf[L["vf1"]] |= 0x04
            buf[L["vf2"]] |= 0x02
            buf[L["lb_setup"]] = 0x02
            buf[L["lb_r"]], buf[L["lb_g"]], buf[L["lb_b"]] = visual.lightbar
        if visual.player_leds is not None:
            buf[L["vf1"]] |= 0x10
            buf[L["player_leds"]] = visual.player_leds | 0x20
        self._finalize_bt_crc(buf)
        return buf  # hidapi accepts bytearray — skip the bytes() copy.

    def _build_bt_haptics(self, samples: bytes):
        with self._lock:
            left = self._left
            right = self._right
            visual = self._visual
        return self._bt_haptics_builder.build(
            samples, left=left, right=right, visual=visual
        )

    def _mark_bt_haptics_failed(self, reason: str) -> None:
        self._bt_haptics_failed = True
        with self._lock:
            self._bt_haptics_pending = None
        if not self._bt_haptics_failure_logged:
            self._bt_haptics_failure_logged = True
            log.warning(
                "Bluetooth HD body haptics unavailable for this connection (%s); "
                "adaptive triggers remain active.",
                reason,
            )

    def _build_power_saver(self):
        """Build a minimal HID report that enables the power-save flag only."""
        L = self.lay
        buf = self._new_report()
        buf[L["vf1"]] |= 0x02          # bit 1 = POWER_SAVE_CONTROL enable
        buf[L["psav"]] |= 0x10         # bit 4 = hardware power save
        self._finalize_bt_crc(buf)
        return buf
