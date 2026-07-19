"""Pure presentation helpers for the Overview runtime cards."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from modules.forzahorizon import TelemetryPhase
from modules.update import UpdatePhase
from modules.update.presentation import localized_status
from modules.xinput.bridge import BridgeStatus
from modules.xinput.service import STEAM_PLATFORM


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


def xinput_bridge_status(service, platform: str, translate: Callable[[str], str]) -> CardStatus:
    if platform == STEAM_PLATFORM:
        return CardStatus(
            translate("Steam Input mode"),
            translate("XInput bridge is off"),
        )
    if service is None:
        return CardStatus(
            translate("XInput bridge unavailable"),
            translate("Controller backend is still starting"),
        )
    snapshot = service.snapshot()
    if snapshot.status is BridgeStatus.DRIVER_MISSING:
        return CardStatus(
            translate("ViGEmBus required"),
            translate("Install the bundled driver to use Xbox App"),
        )
    if snapshot.status is BridgeStatus.INSTALLING:
        return CardStatus(
            translate("Installing ViGEmBus"),
            translate("Complete the Windows installer"),
        )
    if snapshot.status is BridgeStatus.RESTART_REQUIRED:
        return CardStatus(
            translate("Windows restart required"),
            translate("Restart Windows before using the Xbox App bridge"),
        )
    if snapshot.status is BridgeStatus.WAITING_CONTROLLER:
        return CardStatus(
            translate("Waiting for DualSense input"),
            translate("The virtual Xbox 360 controller starts after input"),
        )
    if snapshot.status is BridgeStatus.ACTIVE:
        return CardStatus(
            translate("Xbox 360 controller active"),
            translate("Forwarded {count} input reports").format(
                count=snapshot.forwarded_reports
            ),
        )
    if snapshot.status is BridgeStatus.STALE:
        return CardStatus(
            translate("Controller input paused"),
            translate("Neutral state sent to prevent stuck controls"),
        )
    if snapshot.status is BridgeStatus.ERROR:
        return CardStatus(
            translate("XInput bridge error"),
            _short_error(snapshot.last_error),
        )
    return CardStatus(
        translate("XInput bridge unavailable"),
        _short_error(snapshot.last_error),
    )


def forza_launch_button_status(
    translate: Callable[[str], str],
    *,
    game_label: str,
    supported: bool,
    scanning: bool,
    installed: bool,
    running: bool,
    launching: bool,
) -> ActionStatus:
    if running:
        return ActionStatus(
            translate("{game} is running").format(game=game_label),
            False,
        )
    if launching:
        return ActionStatus(
            translate("Starting {game}...").format(game=game_label),
            False,
        )
    if scanning:
        return ActionStatus(
            translate("Finding {game}...").format(game=game_label),
            False,
        )
    if supported and installed:
        return ActionStatus(
            translate("Launch {game}").format(game=game_label),
            True,
        )
    return ActionStatus(
        translate("{game} not found").format(game=game_label),
        False,
    )


def should_scan_forza_install(
    *,
    supported: bool,
    installed: bool,
    scanning: bool,
    launching: bool,
    has_result: bool,
    now: float,
    last_scan: float,
    retry_interval: float,
) -> bool:
    """Return whether the selected Steam game needs one discovery worker."""
    return bool(
        supported
        and not installed
        and not scanning
        and not launching
        and (not has_result or now - last_scan >= retry_interval)
    )


def fh6_launch_button_status(
    translate: Callable[[str], str],
    **state,
) -> ActionStatus:
    """Compatibility wrapper for integrations importing the R5 helper."""
    return forza_launch_button_status(translate, game_label="FH6", **state)
