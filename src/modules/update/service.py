from __future__ import annotations

import logging
import hashlib
import json
import re
import threading
import time
from dataclasses import asdict, replace
from pathlib import Path

from modules.config import paths, preferences

from .github import GitHubReleaseClient
from .install import launch_update_helper
from .model import UpdatePhase, UpdateRelease, UpdateSnapshot

log = logging.getLogger("fhds.update")


def _current_version() -> int:
    match = re.match(r"^R(\d+)$", preferences._release_version())
    return int(match.group(1)) if match else 0


class UpdateService:
    def __init__(self, settings, *, variant: str, client=None):
        self.settings = settings
        self.variant = variant
        self.client = client or GitHubReleaseClient()
        self._lock = threading.Lock()
        self._snapshot = UpdateSnapshot()
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_sha256 = ""
        self._load_pending()

    def snapshot(self) -> UpdateSnapshot:
        with self._lock:
            return self._snapshot

    def _set(self, **changes) -> None:
        with self._lock:
            self._snapshot = replace(self._snapshot, **changes)

    def _start(self, target, *, name: str) -> bool:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return False
            self._worker = threading.Thread(target=target, name=name, daemon=True)
            self._worker.start()
        return True

    def start_background(self, *, initial_delay: float = 10.0) -> None:
        if not bool(getattr(self.settings, "check_for_updates", True)):
            return

        def delayed_check():
            if self._stop.wait(max(0.0, initial_delay)):
                return
            self._start(
                lambda: self._check_impl(background=True),
                name="fhds-update-background-check",
            )

        threading.Thread(
            target=delayed_check,
            name="fhds-update-background-delay",
            daemon=True,
        ).start()

    def stop(self) -> None:
        self._stop.set()

    def check_now(self) -> bool:
        return self._start(lambda: self._check_impl(background=False), name="fhds-update-check")

    def _check_impl(self, *, background: bool) -> None:
        self._set(phase=UpdatePhase.CHECKING, message="Checking for updates")
        try:
            release = self.client.latest(
                current_version=_current_version(), variant=self.variant
            )
        except Exception as exc:
            log.warning("Update check failed: %s", exc)
            self._set(phase=UpdatePhase.ERROR, message=str(exc), last_checked_at=time.time())
            return
        now = time.time()
        if release is None:
            self._set(
                phase=UpdatePhase.UP_TO_DATE,
                message="You are up to date",
                release=None,
                last_checked_at=now,
            )
            return
        self._set(
            phase=UpdatePhase.AVAILABLE,
            message=f"{release.tag} is available",
            release=release,
            downloaded=0,
            total=release.asset_size,
            last_checked_at=now,
        )
        if background and bool(getattr(self.settings, "auto_download_updates", False)):
            self._download_impl()

    def download(self) -> bool:
        snapshot = self.snapshot()
        if snapshot.release is None:
            return False
        return self._start(self._download_impl, name="fhds-update-download")

    def _download_impl(self) -> None:
        release = self.snapshot().release
        if release is None:
            return
        update_dir = paths.DATA / "updates"
        destination = update_dir / release.asset_name
        self._set(
            phase=UpdatePhase.DOWNLOADING,
            message="Downloading update",
            downloaded=0,
            total=release.asset_size,
        )

        def progress(downloaded, total):
            self._set(downloaded=downloaded, total=total or release.asset_size)

        try:
            self._set(phase=UpdatePhase.DOWNLOADING)
            digest = self.client.download(release, destination, progress=progress)
            self._set(phase=UpdatePhase.VERIFYING, message="Verifying update")
            self._last_sha256 = digest
            self._save_pending(release, destination, digest)
            self._set(
                phase=UpdatePhase.READY,
                message="Update ready to install",
                staged_path=str(destination),
                downloaded=release.asset_size,
                total=release.asset_size,
            )
        except Exception as exc:
            log.warning("Update download failed: %s", exc)
            self._set(phase=UpdatePhase.ERROR, message=str(exc))

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 256), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @property
    def _pending_meta(self) -> Path:
        return paths.DATA / "updates" / "pending.json"

    def _save_pending(self, release: UpdateRelease, staged: Path, digest: str) -> None:
        payload = {
            "release": asdict(release),
            "staged_path": str(Path(staged).resolve()),
            "sha256": digest.lower(),
        }
        self._pending_meta.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._pending_meta.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self._pending_meta)

    def _load_pending(self) -> None:
        meta = self._pending_meta
        if not meta.is_file():
            return
        try:
            payload = json.loads(meta.read_text(encoding="utf-8"))
            release = UpdateRelease(**payload["release"])
            staged = Path(payload["staged_path"]).resolve()
            digest = str(payload["sha256"]).lower()
            update_root = (paths.DATA / "updates").resolve()
            if staged.parent != update_root or not staged.is_file():
                raise ValueError("pending update path is invalid")
            if self._hash_file(staged).lower() != digest:
                raise ValueError("pending update checksum is invalid")
            if release.version <= _current_version():
                raise ValueError("pending update is stale")
            expected_marker = {
                "console": "mikuconsole",
                "stage": "mikustage",
                "studio": "mikustudio",
            }.get(self.variant, "")
            if not expected_marker or expected_marker not in release.asset_name.lower().replace("-", ""):
                raise ValueError("pending update belongs to another UI variant")
            self._last_sha256 = digest
            self._snapshot = UpdateSnapshot(
                phase=UpdatePhase.READY,
                message="Update ready to install",
                release=release,
                downloaded=release.asset_size,
                total=release.asset_size,
                staged_path=str(staged),
            )
        except Exception as exc:
            log.warning("Discarding invalid pending update: %s", exc)
            try:
                meta.unlink(missing_ok=True)
            except OSError:
                pass

    def install_on_exit(self) -> Path:
        snapshot = self.snapshot()
        if snapshot.phase is not UpdatePhase.READY or not snapshot.staged_path:
            raise RuntimeError("no verified update is ready")
        if not self._last_sha256:
            raise RuntimeError("verified update digest is missing")
        self._set(phase=UpdatePhase.INSTALLING, message="Restarting to install")
        return launch_update_helper(
            Path(snapshot.staged_path), expected_sha256=self._last_sha256
        )
