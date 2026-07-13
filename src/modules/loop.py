"""Per-frame loop: idle/lost handling, write-gate, once-per-second debug log."""

import logging
import time

from modules import dualsense, forzahorizon
from modules.forzahorizon import ProcessWatcher
from modules.haptics import HapticManager, HapticMixer, SILENT_FRAME

log = logging.getLogger("fhds")


def _max_abs(t, prefix):
    return max(abs(t[f"{prefix}_{wheel}"]) for wheel in ("fl", "fr", "rl", "rr"))


def run(ds, listener, s, stop_event=None, usb_audio=None):
    OFF = dualsense.adaptive_trigger.off()
    controller = forzahorizon.Controller(s)
    haptic_mixer = HapticMixer()
    if usb_audio is None:
        haptic_manager = HapticManager(ds, s)
    else:
        haptic_manager = HapticManager(ds, s, audio=usb_audio)
    prev = None
    last_pkt = time.monotonic()
    last_log = 0.0
    pkt_count = 0
    idle_silenced = False

    watcher = ProcessWatcher(s.game_process_name_contains, s.game_poll_interval_s)
    dsx_mode = getattr(ds, "is_dsx", False)

    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            now = time.monotonic()
            if s.exit_on_game_close:
                # Never let watcher errors kill the loop silently.
                try:
                    if watcher.should_exit():
                        log.info("Game process closed - exiting.")
                        break
                except Exception as e:
                    log.warning("game-close watcher error: %s", e)

            pkt, addr = listener.recv_latest()

            if pkt is None:
                idle = now - last_pkt
                if idle > 5.0 and not getattr(listener, "lost", False):
                    log.warning("No UDP packets yet - check Forza Horizon Data Out IP/port and Windows Firewall")
                    listener.lost = True
                if idle > 1.0 and not idle_silenced and pkt_count > 0:
                    try:
                        haptic_mixer.reset()
                    except Exception as e:
                        log.debug("haptic mixer reset failed: %s", e)
                    try:
                        rumble = haptic_manager.route(SILENT_FRAME)
                    except Exception as e:
                        log.debug("haptic silence failed: %s", e)
                        rumble = None
                    state = (OFF, OFF, rumble)
                    if state != prev:
                        try:
                            ds.set(*state)
                            prev = state
                        except Exception as e:
                            log.debug("ds.set idle failed: %s", e)
                    idle_silenced = True
                # Fallback exit when telemetry was flowing and then stopped.
                if pkt_count > 0 and idle > s.telemetry_lost_exit_s:
                    log.info("Telemetry lost for %.0fs - exiting.", idle)
                    break
                continue

            pkt_count += 1
            last_pkt = now
            idle_silenced = False
            listener.lost = False
            if pkt_count == 1:
                log.info(
                    "First packet from %s:%d (%d bytes)%s",
                    addr[0],
                    addr[1],
                    len(pkt),
                    " [DSX]" if dsx_mode else "",
                )

            try:
                t = forzahorizon.parse_packet(pkt)
            except ValueError as e:
                log.warning("Bad packet from %s:%d (%d bytes): %s", addr[0], addr[1], len(pkt), e)
                continue

            # Never let controller logic block later telemetry frames.
            try:
                left, right = controller.update(t, s)
            except Exception as e:
                log.warning("controller.update failed: %s", e)
                continue

            try:
                haptic_frame = haptic_mixer.update(t, s, now)
            except Exception as e:
                log.warning("haptic mixer failed: %s", e)
                haptic_frame = SILENT_FRAME
            try:
                rumble = haptic_manager.route(haptic_frame)
            except Exception as e:
                log.debug("haptic route failed: %s", e)
                rumble = None

            state = (left, right, rumble)
            if state != prev:
                try:
                    ds.set(*state)
                    prev = state
                except Exception as e:
                    # HID reconnect logic owns recovery after a failed write.
                    log.debug("ds.set failed: %s", e)

            if now - last_log >= 1.0:
                last_log = now
                tag = "RACE" if t["on"] else "MENU"
                slip_r = _max_abs(t, "tire_slip_ratio")
                slip_c = _max_abs(t, "tire_combined_slip")
                log.debug(
                    "[%s] %6.1f km/h | gear %d | gas %3d R=%s | brake %3d L=%s | "
                    "slip %.2f combined %.2f",
                    tag,
                    t["speed"],
                    t["gear"],
                    t["accel"],
                    right,
                    t["brake"],
                    left,
                    slip_r,
                    slip_c,
                )
    finally:
        try:
            stop_rumble = haptic_manager.route(SILENT_FRAME)
        except Exception as e:
            log.debug("haptic shutdown silence failed: %s", e)
            stop_rumble = None
        stop_state = (OFF, OFF, stop_rumble)
        if stop_state != prev:
            try:
                ds.set(*stop_state)
            except Exception as e:
                log.debug("ds.set shutdown failed: %s", e)
        try:
            haptic_manager.close()
        except Exception as e:
            log.debug("haptic manager close failed: %s", e)
