from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class UpdatePhase(StrEnum):
    IDLE = "idle"
    CHECKING = "checking"
    UP_TO_DATE = "up_to_date"
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    READY = "ready"
    INSTALLING = "installing"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class UpdateRelease:
    version: int
    tag: str
    body: str
    html_url: str
    asset_name: str
    asset_url: str
    asset_size: int
    checksum_url: str


@dataclass(frozen=True, slots=True)
class UpdateSnapshot:
    phase: UpdatePhase = UpdatePhase.IDLE
    message: str = ""
    release: UpdateRelease | None = None
    downloaded: int = 0
    total: int = 0
    staged_path: str = ""
    last_checked_at: float | None = None

    @property
    def progress(self) -> float:
        if self.total <= 0:
            return 0.0
        return max(0.0, min(1.0, self.downloaded / self.total))

