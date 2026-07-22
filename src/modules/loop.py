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
    collision_detector = forzahorizon.CollisionDetector()
    redline_detector = forzahorizon.RedlineDetector()
    lighting = forzahorizon.LightingController()
    if usb_audio is None:
        haptic_manager = HapticManager(ds, s)
    else:
        haptic_manager = HapticManager(ds, s, audio=usb_audio)
    prev = None
    last_pkt = time.monotonic()
    now = last_pkt
    last_log = 0.0
    pkt_count = 0
    idle_silenced = False

    watcher = ProcessWatcher(s.game_process_name_contains, s.game_poll_interval_s)
    dsx_mode = getattr(ds, "is_dsx", False)

    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            if s.exit_on_game_close:
                # Never let watcher errors kill the loop silently.
                try:
                    if watcher.should_exit():
                        log.info("Game process closed - exiting.")
                        break
                except Exception as e:
                    log.warning("game-close watcher error: %s", e)

            pkt, addr = listener.recv_latest()
            now = time.monotonic()

            telemetry = None
            if pkt is not None:
                try:
                    telemetry = forzahorizon.parse_packet(pkt)
                except ValueError as e:
                    log.warning(
                        "Bad packet from %s:%d (%d bytes): %s",
                        addr[0],
                        addr[1],
                        len(pkt),
                        e,
                    )

            # A datagram is not proof of live telemetry until it parses. This
            # keeps malformed traffic from holding the previous trigger and
            # haptic frame indefinitely.
            if telemetry is None:
                idle = now - last_pkt
                if idle > 5.0 and not getattr(listener, "lost", False):
                    log.warning("No UDP packets yet - check Forza Horizon Data Out IP/port and Windows Firewall")
                    listener.lost = True
                if idle > 1.0 and not idle_silenced and pkt_count > 0:
                    try:
                        haptic_mixer.reset()
                    except Exception as e:
                        log.debug("haptic mixer reset failed: %s", e)
                    redline_detector.reset_transients()
                    try:
                        rumble = haptic_manager.route(SILENT_FRAME)
                    except Exception as e:
                        log.debug("haptic silence failed: %s", e)
                        rumble = None
                    state = (OFF, OFF, rumble, lighting.update({"on": False}, s, now))
                    if state != prev:
                        try:
                            ds.set(state[0], state[1], state[2], visual=state[3])
                            prev = state
                        except Exception as e:
                            log.debug("ds.set idle failed: %s", e)
                    idle_silenced = True
                # Fallback exit when telemetry was flowing and then stopped.
                # This belongs to the same user-facing behavior as process
                # watching, so disabling exit_on_game_close disables both.
                if (s.exit_on_game_close
                        and pkt_count > 0
                        and idle > s.telemetry_lost_exit_s):
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

            t = telemetry

            try:
                redline = redline_detector.update(t, now)
                t["effective_redline_rpm"] = redline.effective_rpm
                t["rev_limiter_active"] = redline.limiter_active
                t["redline_confidence"] = redline.confidence
            except Exception as e:
                # The raw max_rpm path remains a safe fallback if inference
                # sees malformed or incomplete telemetry.
                log.debug("dynamic redline detector failed: %s", e)

            # Never let controller logic block later telemetry frames.
            collision_signal = None
            try:
                collision_signal = collision_detector.update(t, s, now)
                left, right = controller.update(t, s, collision_signal)
            except Exception as e:
                log.warning("controller.update failed: %s", e)
                # Fail closed instead of leaving the last adaptive-trigger
                # effect latched while independent body haptics keep running.
                left, right = OFF, OFF

            try:
                haptic_frame = haptic_mixer.update(t, s, now, collision_signal)
            except Exception as e:
                log.warning("haptic mixer failed: %s", e)
                haptic_frame = SILENT_FRAME
            try:
                rumble = haptic_manager.route(haptic_frame)
            except Exception as e:
                log.debug("haptic route failed: %s", e)
                rumble = None

            visual = lighting.update(t, s, now)
            state = (left, right, rumble, visual)
            if state != prev:
                try:
                    ds.set(left, right, rumble, visual=visual)
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
        # Reuse the last loop timestamp. Besides avoiding one unnecessary clock
        # read, this keeps shutdown deterministic for tests and for telemetry
        # replays that inject their own monotonic clock.
        stop_visual = lighting.update({"on": False}, s, now)
        stop_state = (OFF, OFF, stop_rumble, stop_visual)
        if stop_state != prev:
            try:
                ds.set(OFF, OFF, stop_rumble, visual=stop_visual)
            except Exception as e:
                log.debug("ds.set shutdown failed: %s", e)
        try:
            haptic_manager.close()
        except Exception as e:
            log.debug("haptic manager close failed: %s", e)
