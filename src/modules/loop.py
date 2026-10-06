"""Per-frame loop: telemetry, bounded Lab preview, and output ownership."""

import logging
import time

from modules import dualsense, forzahorizon
from modules.dualsense.output_state import ControllerVisualState, NO_VISUAL_CONTROL
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
    trigger_pulse=None,
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
    previous_trigger_guard = None
    last_pkt = time.monotonic()
    now = last_pkt
    last_log = 0.0
    pkt_count = 0
    idle_silenced = False
    lab_output_active = False
    pulse_output_active = False
    telemetry_state = None
    last_visual = NO_VISUAL_CONTROL
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

    def write_state(state, *, context, trigger_guard=None):
        nonlocal prev, previous_trigger_guard
        if state == prev and trigger_guard == previous_trigger_guard:
            return
        try:
            kwargs = {"trigger_guard": trigger_guard} if trigger_guard is not None else {}
            ds.set(state[0], state[1], state[2], visual=state[3], **kwargs)
            prev = state
            previous_trigger_guard = trigger_guard
        except Exception as exc:
            log.debug("ds.set %s failed: %s", context, exc)

    def render_visual(telemetry, timestamp):
        nonlocal last_visual
        try:
            last_visual = lighting.update(telemetry, s, timestamp)
        except Exception as exc:  # noqa: BLE001 - isolate optional lighting failures
            log.warning("lighting update failed: %s", exc)
            # Release only fields the application owned or has enabled. A bad
            # lighting setting must not interrupt triggers, input or grip audio.
            last_visual = ControllerVisualState(
                lightbar=(0, 0, 0) if (
                    last_visual.lightbar is not None or s.enable_tachometer_lightbar
                ) else None,
                player_leds=0 if (
                    last_visual.player_leds is not None or s.enable_gear_player_leds
                ) else None,
            )
        return last_visual

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
        stop_visual = render_visual({"on": False}, timestamp)
        stop_state = (OFF, OFF, stop_rumble, stop_visual)
        write_state(stop_state, context="silence")
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
                visual = render_visual({"on": False}, now)
                left = lab_output.left_trigger if s.enable_trigger_feedback else OFF
                right = lab_output.right_trigger if s.enable_trigger_feedback else OFF
                state = (
                    left,
                    right,
                    rumble,
                    visual,
                )
                write_state(state, context="Haptics Lab")
                lab_output_active = True
                publish_haptics_diagnostics(now)
            elif lab_output_active:
                prev = silence_output(now, force_haptics=True)
                pause_haptics()
                lab_output_active = False
                publish_haptics_diagnostics(now, force=True)
                log.info("Haptics Lab preview stopped")

            pulse = None
            pulse_guard = None
            if trigger_pulse is not None:
                if (
                    not s.enable_trigger_feedback
                    or not bool(getattr(ds, "connected", True))
                    or lab_output_active
                ):
                    trigger_pulse.stop()
                else:
                    output = trigger_pulse.sample_output(now=now, controller=ds)
                    if output is not None:
                        pulse, pulse_guard = output.effect, output.guard
                if pulse is not None:
                    state = (pulse, pulse, *(prev[2:] if prev is not None else (None, None)))
                    write_state(state, context="UI pulse", trigger_guard=pulse_guard)
                    pulse_output_active = True
                elif pulse_output_active:
                    if not lab_output_active:
                        if telemetry_state is not None and now - last_pkt <= 1.0:
                            state = telemetry_state
                            if not s.enable_trigger_feedback:
                                state = (OFF, OFF, *state[2:])
                            write_state(state, context="UI pulse restore")
                        else:
                            prev = silence_output(now)
                    pulse_output_active = False

            if s.exit_on_game_close:
                try:
                    if watcher.should_exit():
                        log.info("Game process closed - exiting.")
                        break
                except Exception as exc:
                    log.warning("game-close watcher error: %s", exc)

            pkt, addr = recv_latest(preview_active=lab_output_active or pulse_output_active)
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
                    state = (OFF, OFF, rumble, render_visual({"on": False}, now))
                    write_state(state, context="idle")
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

            visual = render_visual(t, now)
            telemetry_state = (left, right, rumble, visual)
            if pulse is not None:
                # UDP waiting and rendering can outlive the request or a UI
                # change. Recheck immediately before publishing its effect.
                if s.enable_trigger_feedback:
                    output = trigger_pulse.sample_output(now=now, controller=ds)
                else:
                    trigger_pulse.stop()
                    output = None
                pulse_guard = output.guard if output is not None else None
                if output is not None:
                    left = right = output.effect
            if not s.enable_trigger_feedback:
                left = right = OFF
            state = (left, right, rumble, visual)
            write_state(state, context="telemetry", trigger_guard=pulse_guard)

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
        if trigger_pulse is not None:
            trigger_pulse.stop()
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
