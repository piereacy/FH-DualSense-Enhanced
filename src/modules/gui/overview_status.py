"""Pure presentation helpers for the Overview runtime cards."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from modules.forzahorizon import TelemetryPhase
from modules.update import UpdatePhase
from modules.update.presentation import localized_status


@dataclass(frozen=True, slots=True)
class CardStatus:
    value: str
    hint: str


@dataclass(frozen=True, slots=True)
class ActionStatus:
    label: str
    enabled: bool


def _short_error(message: str, limit: int = 64) -> str:
    compact = " ".join(str(message).split())
    compact = compact.replace("<urlopen error ", "").removesuffix(">")
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def controller_status(ds, settings, translate: Callable[[str], str], *, error: str = "") -> CardStatus:
    if error:
        return CardStatus(translate("Controller backend error"), _short_error(error))
    if bool(getattr(settings, "use_dsx", False)):
        target = f"{settings.dsx_host}:{settings.dsx_port}"
        if ds is not None and bool(getattr(ds, "connected", False)):
            value = translate("DSX enabled")
        else:
            value = translate("DSX unavailable")
        return CardStatus(
            value,
            translate("Target {target}; fire-and-forget UDP has no acknowledgement").format(
                target=target
            ),
        )
    if ds is not None and bool(getattr(ds, "connected", False)):
        transport = (getattr(ds, "transport", None) or "?").upper()
        return CardStatus(
            translate("Connected"),
            translate("Transport: {transport}").format(transport=transport),
        )
    if bool(getattr(settings, "enable_reconnect", False)):
        return CardStatus(
            translate("Waiting for controller"),
            translate("Retrying every {seconds:g} seconds").format(
                seconds=float(settings.reconnect_interval_s)
            ),
        )
    return CardStatus(
        translate("Waiting for controller"),
        translate("Automatic reconnect is off"),
    )


def telemetry_status(listener, settings, translate: Callable[[str], str], *, error: str = "") -> CardStatus:
    if error:
        return CardStatus(translate("UDP bind failed"), _short_error(error))
    if listener is None:
        return CardStatus(
            translate("Starting listener"),
            translate("UDP port {port}").format(port=settings.udp_port),
        )
    snapshot = listener.snapshot()
    if snapshot.phase is TelemetryPhase.WAITING:
        value = translate("Waiting for packets")
        hint = translate("UDP port {port}; enable Forza Data Out").format(
            port=snapshot.listen_port
        )
    elif snapshot.phase is TelemetryPhase.RECEIVING:
        value = translate("Receiving telemetry")
        hint = translate("Packet {count} from {source}").format(
            count=snapshot.packet_count,
            source=snapshot.source_host or "?",
        )
    else:
        value = translate("Telemetry lost")
        hint = translate("Last packet {seconds:.1f} seconds ago on UDP {port}").format(
            seconds=snapshot.last_packet_age_s or 0.0,
            port=snapshot.listen_port,
        )
    return CardStatus(value, hint)


def profile_status(name: str, translate: Callable[[str], str], *, error: str = "") -> CardStatus:
    if error:
        return CardStatus(translate("Profile unavailable"), _short_error(error))
    return CardStatus(
        name or translate("(none)"),
        translate("Changes save instantly"),
    )


def update_status(service, settings, translate: Callable[[str], str]) -> CardStatus:
    snapshot = service.snapshot()
    if not service.supported:
        return CardStatus(
            translate("Unavailable in this runtime"),
            translate("Built-in updates require the Windows standalone EXE"),
        )
    if snapshot.phase is UpdatePhase.IDLE:
        if bool(getattr(settings, "check_for_updates", True)):
            return CardStatus(
                translate("Waiting for automatic check"),
                translate("Built-in updater"),
            )
        return CardStatus(
            translate("Update checks disabled"),
            translate("Use Check now in System and updates"),
        )
    if snapshot.phase is UpdatePhase.ERROR:
        return CardStatus(
            translate("Update failed"),
            _short_error(snapshot.message) or translate("Built-in updater"),
        )
    hint = translate("Built-in updater")
    if snapshot.phase is UpdatePhase.AVAILABLE and snapshot.release is not None:
        hint = snapshot.release.tag
    elif snapshot.phase is UpdatePhase.DOWNLOADING:
        hint = translate("Downloaded {progress:.0f}%").format(
            progress=snapshot.progress * 100.0
        )
    return CardStatus(localized_status(snapshot, translate), hint)


def fh6_launch_button_status(
    translate: Callable[[str], str],
    *,
    supported: bool,
    scanning: bool,
    installed: bool,
    running: bool,
    launching: bool,
) -> ActionStatus:
    if running:
        return ActionStatus(translate("FH6 is running"), False)
    if launching:
        return ActionStatus(translate("Starting FH6..."), False)
    if scanning:
        return ActionStatus(translate("Finding FH6..."), False)
    if supported and installed:
        return ActionStatus(translate("Launch FH6"), True)
    return ActionStatus(translate("FH6 not found"), False)
