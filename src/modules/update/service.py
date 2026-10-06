from __future__ import annotations

import logging
import hashlib
import json
import re
import threading
import time
import urllib.parse
import uuid
from dataclasses import asdict, replace
from pathlib import Path

from modules.config import paths, preferences

from .github import GitHubReleaseClient
from .install import launch_update_helper
from .model import UpdatePhase, UpdateRelease, UpdateSnapshot

log = logging.getLogger("fhds.update")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _current_version() -> int:
    match = re.match(r"^R(\d+)$", preferences._release_version())
    return int(match.group(1)) if match else 0


class UpdateService:
    def __init__(self, settings, *, client=None, supported: bool = True):
        self.settings = settings
        self.supported = bool(supported)
        self.client = client or GitHubReleaseClient()
        self._lock = threading.Lock()
        self._snapshot = UpdateSnapshot(
            message=(
                "Built-in updates require the Windows standalone EXE"
                if not self.supported else ""
            )
        )
        self._worker: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_sha256 = ""
        if self.supported:
            self._load_pending()

    def snapshot(self) -> UpdateSnapshot:
        with self._lock:
            return self._snapshot

    def _set(self, **changes) -> None:
        with self._lock:
            self._snapshot = replace(self._snapshot, **changes)

    def _start(self, target, *, name: str) -> bool:
        with self._lock:
            if self._stop.is_set() or self._snapshot.phase is UpdatePhase.INSTALLING:
                return False
            if self._worker is not None and self._worker.is_alive():
                return False
            self._worker = threading.Thread(target=target, name=name, daemon=True)
            self._worker.start()
        return True

    def start_background(self, *, initial_delay: float = 10.0) -> None:
        if (
            not self.supported
            or not bool(getattr(self.settings, "check_for_updates", True))
        ):
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
        with self._lock:
            self._stop.set()

    def check_now(self) -> bool:
        if not self.supported:
            return False
        return self._start(lambda: self._check_impl(background=False), name="fhds-update-check")

    def _check_impl(self, *, background: bool) -> None:
        with self._lock:
            cached = self._snapshot
            if self._stop.is_set() or cached.phase is UpdatePhase.INSTALLING:
                return
            if cached.phase is not UpdatePhase.READY:
                self._snapshot = replace(
                    cached, phase=UpdatePhase.CHECKING, message="Checking for updates"
                )

        def publish(**changes):
            # Installation may have been requested while the HTTP check ran.
            with self._lock:
                if not self._stop.is_set() and self._snapshot.phase is not UpdatePhase.INSTALLING:
                    self._snapshot = replace(self._snapshot, **changes)

        def keep_cached(release=None):
            if not self._verified_cache(cached):
                return False
            if release is not None and not self._same_asset(cached.release, release):
                return False
            publish(
                phase=UpdatePhase.READY,
                message="Update ready to install",
                release=release or cached.release,
                last_checked_at=time.time(),
            )
            return True

        try:
            release = self.client.latest(current_version=_current_version())
        except Exception as exc:
            log.warning("Update check failed: %s", exc)
            if not keep_cached():
                publish(phase=UpdatePhase.ERROR, message=str(exc), last_checked_at=time.time())
            return
        if keep_cached(release):
            return
        now = time.time()
        if release is None:
            publish(
                phase=UpdatePhase.UP_TO_DATE,
                message="You are up to date",
                release=None,
                staged_path="",
                last_checked_at=now,
            )
            return
        publish(
            phase=UpdatePhase.AVAILABLE,
            message=f"{release.tag} is available",
            release=release,
            downloaded=0,
            total=release.asset_size,
            staged_path="",
            last_checked_at=now,
        )
        if (
            self.snapshot().phase is UpdatePhase.AVAILABLE
            and background
            and bool(getattr(self.settings, "auto_download_updates", False))
        ):
            self._download_impl()

    @staticmethod
    def _same_asset(left: UpdateRelease | None, right: UpdateRelease) -> bool:
        fields = ("version", "tag", "asset_name", "asset_url", "asset_size", "checksum_url")
        return left is not None and all(getattr(left, key) == getattr(right, key) for key in fields)

    def _verified_cache(self, snapshot: UpdateSnapshot) -> bool:
        if snapshot.phase is not UpdatePhase.READY or snapshot.release is None:
            return False
        if not snapshot.staged_path or not self._last_sha256:
            return False
        try:
            staged = Path(snapshot.staged_path)
            return (
                snapshot.release.version > _current_version()
                and staged.stat().st_size == snapshot.release.asset_size
                and self._hash_file(staged) == self._last_sha256
            )
        except OSError:
            return False

    def download(self) -> bool:
        if not self.supported:
            return False
        snapshot = self.snapshot()
        if snapshot.release is None:
            return False
        return self._start(self._download_impl, name="fhds-update-download")

    def _download_impl(self) -> None:
        with self._lock:
            if self._stop.is_set() or self._snapshot.phase is UpdatePhase.INSTALLING:
                return
            release = self._snapshot.release
            if release is None:
                return
            self._snapshot = replace(
                self._snapshot,
                phase=UpdatePhase.DOWNLOADING,
                message="Downloading update",
                downloaded=0,
                total=release.asset_size,
            )
        update_dir = paths.DATA / "updates"
        destination = update_dir / release.asset_name

        def progress(downloaded, total):
            self._set(downloaded=downloaded, total=total or release.asset_size)

        try:
            digest = self.client.download(release, destination, progress=progress)
            self._set(phase=UpdatePhase.VERIFYING, message="Verifying update")
            self._save_pending(release, destination, digest)
            with self._lock:
                self._last_sha256 = digest
                self._snapshot = replace(
                    self._snapshot,
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
        tmp = self._pending_meta.with_name(
            f".{self._pending_meta.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self._pending_meta)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def _load_pending(self) -> None:
        meta = self._pending_meta
        if not meta.is_file():
            return
        try:
            payload = json.loads(meta.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not isinstance(payload.get("release"), dict):
                raise ValueError("pending update metadata is malformed")
            release = UpdateRelease(**payload["release"])
            staged = Path(payload["staged_path"]).resolve()
            digest_value = payload["sha256"]
            if not isinstance(digest_value, str):
                raise ValueError("pending update checksum is invalid")
            digest = digest_value.lower()
            if not _SHA256_RE.fullmatch(digest):
                raise ValueError("pending update checksum is invalid")
            if type(release.version) is not int or release.version <= 0:
                raise ValueError("pending update version is invalid")
            if type(release.asset_size) is not int or release.asset_size <= 0:
                raise ValueError("pending update size is invalid")
            string_fields = (
                release.tag,
                release.body,
                release.html_url,
                release.asset_name,
                release.asset_url,
                release.checksum_url,
            )
            if any(not isinstance(value, str) for value in string_fields):
                raise ValueError("pending update release metadata is malformed")
            for url in (release.asset_url, release.checksum_url):
                parsed = urllib.parse.urlsplit(url)
                if (
                    parsed.scheme.casefold() != "https"
                    or not parsed.hostname
                    or parsed.username is not None
                    or parsed.password is not None
                ):
                    raise ValueError("pending update URL is invalid")
            update_root = (paths.DATA / "updates").resolve()
            if staged.parent != update_root or not staged.is_file():
                raise ValueError("pending update path is invalid")
            if staged.stat().st_size != release.asset_size:
                raise ValueError("pending update size is invalid")
            with staged.open("rb") as stream:
                if stream.read(2) != b"MZ":
                    raise ValueError("pending update is not a Windows executable")
            if self._hash_file(staged).lower() != digest:
                raise ValueError("pending update checksum is invalid")
            if release.version <= _current_version():
                raise ValueError("pending update is stale")
            expected_name = f"FH-DualSense-Enhanced-R{release.version}.exe"
            if (
                release.tag.casefold() != f"r{release.version}"
                or release.asset_name != expected_name
                or staged.name != expected_name
            ):
                raise ValueError("pending update does not use the canonical asset name")
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
        if not self.supported:
            raise RuntimeError("built-in updates require the Windows standalone EXE")
        # Claim the path, digest and phase together. A background check may
        # otherwise replace the ready release and begin another download here.
        with self._lock:
            if self._stop.is_set():
                raise RuntimeError("update service is stopped")
            snapshot = self._snapshot
            if snapshot.phase is not UpdatePhase.READY or not snapshot.staged_path:
                raise RuntimeError("no verified update is ready")
            digest = self._last_sha256
            if not digest:
                raise RuntimeError("verified update digest is missing")
            self._snapshot = replace(
                snapshot, phase=UpdatePhase.INSTALLING, message="Restarting to install"
            )
        try:
            return launch_update_helper(
                Path(snapshot.staged_path), expected_sha256=digest
            )
        except Exception:
            # The GUI/TUI deliberately stays open when the helper cannot be
            # scheduled. Restore the actionable state so the user can close a
            # conflicting instance and retry without restarting this process.
            self._set(phase=UpdatePhase.READY, message="Update ready to install")
            raise
