"""Per-frame loop: telemetry, bounded Lab preview, and output ownership."""

import logging
import time

from modules import dualsense, forzahorizon
from modules.forzahorizon import ProcessWatcher
from modules.haptics import HapticManager, HapticMixer, SILENT_FRAME

log = logging.getLogger("fhds")


def _max_abs(t, prefix):
    return max(abs(t[f"{prefix}_{wheel}"]) for wheel in ("fl", "fr", "rl", "rr"))


def run(
    ds,
    listener,
    s,
    stop_event=None,
    usb_audio=None,
    haptics_lab=None,
    diagnostics=None,
):
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
    lab_output_active = False
    last_diagnostics = -1e9

    watcher = ProcessWatcher(s.game_process_name_contains, s.game_poll_interval_s)
    dsx_mode = getattr(ds, "is_dsx", False)

    def publish_haptics_diagnostics(timestamp, *, force=False):
        nonlocal last_diagnostics
        if diagnostics is None or (not force and timestamp - last_diagnostics < 1.0):
            return
        publish = getattr(diagnostics, "publish_haptics", None)
        snapshot = getattr(haptic_manager, "diagnostics_snapshot", None)
        if not callable(publish) or not callable(snapshot):
            return
        try:
            publish(snapshot())
            last_diagnostics = timestamp
        except Exception as exc:
            log.debug("haptic diagnostics snapshot failed: %s", exc)

    def recv_latest(*, preview_active=False):
        if preview_active and isinstance(listener, forzahorizon.UDPListener):
            return listener.recv_latest(wait_timeout_s=0.05)
        return listener.recv_latest()

    def pause_haptics():
        pause = getattr(haptic_manager, "pause", None)
        if not callable(pause):
            return
        try:
            pause()
        except Exception as exc:
            log.debug("haptic pause failed: %s", exc)

    def silence_output(timestamp, *, reset_transients=True, force_haptics=False):
        if reset_transients:
            try:
                haptic_mixer.reset()
            except Exception as exc:
                log.debug("haptic mixer reset failed: %s", exc)
            redline_detector.reset_transients()
        try:
            stop_rumble = (
                haptic_manager.route(SILENT_FRAME, force=True)
                if force_haptics
                else haptic_manager.route(SILENT_FRAME)
            )
        except Exception as exc:
            log.debug("haptic silence failed: %s", exc)
            stop_rumble = None
        stop_visual = lighting.update({"on": False}, s, timestamp)
        stop_state = (OFF, OFF, stop_rumble, stop_visual)
        if stop_state != prev:
            try:
                ds.set(OFF, OFF, stop_rumble, visual=stop_visual)
            except Exception as exc:
                log.debug("ds.set silence failed: %s", exc)
        return stop_state

    publish_haptics_diagnostics(now, force=True)

    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break

            lab_output = None
            if haptics_lab is not None:
                try:
                    snapshot = haptics_lab.snapshot(now=now)
                    if snapshot.active:
                        if bool(getattr(ds, "connected", True)):
                            lab_output = haptics_lab.sample(now=now)
                        else:
                            haptics_lab.stop("controller_disconnected", now=now)
                except Exception as exc:
                    log.warning("Haptics Lab preview failed closed: %s", exc)
                    try:
                        haptics_lab.stop("error", now=now)
                    except Exception:
                        pass

            if lab_output is not None:
                if not lab_output_active:
                    log.info("Haptics Lab preview started")
                try:
                    rumble = haptic_manager.route(lab_output.frame, force=True)
                except Exception as exc:
                    log.debug("Haptics Lab body route failed: %s", exc)
                    rumble = None
                visual = lighting.update({"on": False}, s, now)
                state = (
                    lab_output.left_trigger,
                    lab_output.right_trigger,
                    rumble,
                    visual,
                )
                if state != prev:
                    try:
                        ds.set(
                            lab_output.left_trigger,
                            lab_output.right_trigger,
                            rumble,
                            visual=visual,
                        )
                        prev = state
                    except Exception as exc:
                        log.debug("Haptics Lab controller write failed: %s", exc)
                lab_output_active = True
                publish_haptics_diagnostics(now)
            elif lab_output_active:
                prev = silence_output(now, force_haptics=True)
                pause_haptics()
                lab_output_active = False
                publish_haptics_diagnostics(now, force=True)
                log.info("Haptics Lab preview stopped")

            if s.exit_on_game_close:
                try:
                    if watcher.should_exit():
                        log.info("Game process closed - exiting.")
                        break
                except Exception as exc:
                    log.warning("game-close watcher error: %s", exc)

            pkt, addr = recv_latest(preview_active=lab_output_active)
            now = time.monotonic()
            source_host = addr[0] if addr is not None else "unknown"
            source_port = addr[1] if addr is not None else 0

            telemetry = None
            if pkt is not None:
                try:
                    telemetry = forzahorizon.parse_packet(pkt)
                except ValueError as exc:
                    log.warning(
                        "Bad packet from %s:%d (%d bytes): %s",
                        source_host,
                        source_port,
                        len(pkt),
                        exc,
                    )

            if telemetry is None:
                if lab_output_active:
                    continue
                idle = now - last_pkt
                if idle > 5.0 and not getattr(listener, "lost", False):
                    log.warning(
                        "No UDP packets yet - check Forza Horizon Data Out "
                        "IP/port and Windows Firewall"
                    )
                    listener.lost = True
                if idle > 1.0 and not idle_silenced and pkt_count > 0:
                    try:
                        haptic_mixer.reset()
                    except Exception as exc:
                        log.debug("haptic mixer reset failed: %s", exc)
                    redline_detector.reset_transients()
                    try:
                        rumble = haptic_manager.route(SILENT_FRAME)
                    except Exception as exc:
                        log.debug("haptic silence failed: %s", exc)
                        rumble = None
                    state = (OFF, OFF, rumble, lighting.update({"on": False}, s, now))
                    if state != prev:
                        try:
                            ds.set(state[0], state[1], state[2], visual=state[3])
                            prev = state
                        except Exception as exc:
                            log.debug("ds.set idle failed: %s", exc)
                    idle_silenced = True
                if (
                    s.exit_on_game_close
                    and pkt_count > 0
                    and idle > s.telemetry_lost_exit_s
                ):
                    log.info("Telemetry lost for %.0fs - exiting.", idle)
                    break
                continue

            if lab_output_active and haptics_lab is not None:
                try:
                    haptics_lab.preempt_for_telemetry(now=now)
                except Exception as exc:
                    log.debug("Haptics Lab telemetry preemption failed: %s", exc)
                lab_output_active = False
                log.info("Haptics Lab stopped because live game telemetry arrived")

            pkt_count += 1
            last_pkt = now
            idle_silenced = False
            listener.lost = False
            if pkt_count == 1:
                log.info(
                    "First packet from %s:%d (%d bytes)%s",
                    source_host,
                    source_port,
                    len(pkt),
                    " [DSX]" if dsx_mode else "",
                )

            t = telemetry
            try:
                redline = redline_detector.update(t, now)
                t["effective_redline_rpm"] = redline.effective_rpm
                t["rev_limiter_active"] = redline.limiter_active
                t["redline_confidence"] = redline.confidence
                t["redline_alert_allowed"] = redline.redline_alert_allowed
            except Exception as exc:
                log.debug("dynamic redline detector failed: %s", exc)

            collision_signal = None
            try:
                collision_signal = collision_detector.update(t, s, now)
                left, right = controller.update(t, s, collision_signal)
            except Exception as exc:
                log.warning("controller.update failed: %s", exc)
                left, right = OFF, OFF

            try:
                haptic_frame = haptic_mixer.update(t, s, now, collision_signal)
            except Exception as exc:
                log.warning("haptic mixer failed: %s", exc)
                haptic_frame = SILENT_FRAME
            try:
                rumble = haptic_manager.route(haptic_frame)
            except Exception as exc:
                log.debug("haptic route failed: %s", exc)
                rumble = None

            visual = lighting.update(t, s, now)
            state = (left, right, rumble, visual)
            if state != prev:
                try:
                    ds.set(left, right, rumble, visual=visual)
                    prev = state
                except Exception as exc:
                    log.debug("ds.set failed: %s", exc)

            if now - last_log >= 1.0:
                last_log = now
                publish_haptics_diagnostics(now)
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
        prev = silence_output(
            now,
            reset_transients=False,
            force_haptics=lab_output_active,
        )
        if haptics_lab is not None:
            try:
                haptics_lab.stop("shutdown", now=now)
            except Exception:
                pass
        try:
            haptic_manager.close()
        except Exception as exc:
            log.debug("haptic manager close failed: %s", exc)
        publish_haptics_diagnostics(now, force=True)
