from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from .model import UpdatePhase, UpdateSnapshot


UpdateAction = Literal["download", "install"]


@dataclass(frozen=True, slots=True)
class UpdateStatusPresentation:
    """Stable GUI-facing values derived from an updater snapshot."""

    status: str
    progress: float
    action: UpdateAction | None
    release_visible: bool


def has_update_notice(snapshot: UpdateSnapshot) -> bool:
    """Whether the persistent white navigation dot should be visible."""
    return snapshot.release is not None and snapshot.phase in {
        UpdatePhase.AVAILABLE,
        UpdatePhase.DOWNLOADING,
        UpdatePhase.VERIFYING,
        UpdatePhase.READY,
        UpdatePhase.ERROR,
    }


def localized_status(
    snapshot: UpdateSnapshot,
    translate: Callable[[str], str],
) -> str:
    """Turn updater state into a localized, user-facing status line."""
    if snapshot.phase is UpdatePhase.IDLE and snapshot.message:
        return translate(snapshot.message)
    if snapshot.phase is UpdatePhase.AVAILABLE and snapshot.release is not None:
        return translate("Update available: {tag}").format(tag=snapshot.release.tag)
    keys = {
        UpdatePhase.IDLE: "Update status: idle",
        UpdatePhase.CHECKING: "Checking for updates",
        UpdatePhase.UP_TO_DATE: "You are up to date",
        UpdatePhase.DOWNLOADING: "Downloading update",
        UpdatePhase.VERIFYING: "Verifying update",
        UpdatePhase.READY: "Update ready to install",
        UpdatePhase.INSTALLING: "Restarting to install",
    }
    if snapshot.phase is UpdatePhase.ERROR:
        return snapshot.message or translate("Update failed")
    return translate(keys.get(snapshot.phase, snapshot.message or "Update status: idle"))


def update_status_presentation(
    snapshot: UpdateSnapshot,
    translate: Callable[[str], str],
) -> UpdateStatusPresentation:
    """Build the values whose changes are allowed to redraw the update card."""
    action: UpdateAction | None = None
    if snapshot.phase is UpdatePhase.AVAILABLE:
        action = "download"
    elif snapshot.phase is UpdatePhase.READY:
        action = "install"
    return UpdateStatusPresentation(
        status=localized_status(snapshot, translate),
        progress=snapshot.progress,
        action=action,
        release_visible=snapshot.release is not None,
    )
