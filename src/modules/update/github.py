from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path

from .model import UpdateRelease

API_URL = "https://api.github.com/repos/piereacy/FH-DualSense-Enhanced/releases"
MAX_API_BYTES = 2 * 1024 * 1024
MAX_CHECKSUM_BYTES = 64 * 1024
MAX_EXE_BYTES = 300 * 1024 * 1024
TAG_RE = re.compile(r"^R(\d+)$", re.IGNORECASE)


class UpdateError(RuntimeError):
    pass


def _request(url: str, *, timeout: float, max_bytes: int):
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise UpdateError("update requests require an HTTPS URL without credentials")
    if not math.isfinite(timeout) or timeout <= 0.0 or max_bytes <= 0:
        raise UpdateError("invalid update request limits")
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "FH-DualSense-Enhanced-Updater",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except (OSError, urllib.error.URLError) as exc:
        raise UpdateError(f"network request failed: {exc}") from exc
    final_url = response.geturl()
    final = urllib.parse.urlsplit(final_url)
    if (
        final.scheme.casefold() != "https"
        or not final.hostname
        or final.username is not None
        or final.password is not None
    ):
        response.close()
        raise UpdateError("update request redirected to an unsafe URL")
    length = response.headers.get("Content-Length")
    if length:
        try:
            declared_size = int(length)
        except (TypeError, ValueError, OverflowError) as exc:
            response.close()
            raise UpdateError("response has an invalid Content-Length") from exc
        if declared_size < 0 or declared_size > max_bytes:
            response.close()
            raise UpdateError("response is larger than the allowed limit")
    return response


class GitHubReleaseClient:
    def __init__(self, *, api_url: str = API_URL, timeout: float = 12.0):
        self.api_url = api_url
        self.timeout = float(timeout)

    def latest(self, *, current_version: int) -> UpdateRelease | None:
        with _request(self.api_url, timeout=self.timeout, max_bytes=MAX_API_BYTES) as response:
            raw = response.read(MAX_API_BYTES + 1)
        if len(raw) > MAX_API_BYTES:
            raise UpdateError("release response exceeded the allowed limit")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpdateError("release response is not valid JSON") from exc
        if not isinstance(payload, list):
            raise UpdateError("release response must be a list")

        candidates: list[UpdateRelease] = []
        for item in payload:
            release = self._parse_release(item)
            if release is not None and release.version > int(current_version):
                candidates.append(release)
        return max(candidates, key=lambda release: release.version, default=None)

    @staticmethod
    def _parse_release(item) -> UpdateRelease | None:
        if not isinstance(item, dict) or item.get("draft") or item.get("prerelease"):
            return None
        tag = str(item.get("tag_name", ""))
        match = TAG_RE.fullmatch(tag)
        if not match:
            return None
        version = int(match.group(1))
        expected = f"FH-DualSense-Enhanced-R{version}.exe"
        assets = item.get("assets")
        if not isinstance(assets, list):
            return None
        by_name = {
            str(asset.get("name", "")): asset
            for asset in assets
            if isinstance(asset, dict)
        }
        asset = by_name.get(expected)
        checksum = by_name.get(expected + ".sha256")
        if asset is None or checksum is None:
            return None
        url = str(asset.get("browser_download_url", ""))
        checksum_url = str(checksum.get("browser_download_url", ""))
        try:
            size = int(asset.get("size", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            return None
        if not url.startswith("https://") or not checksum_url.startswith("https://"):
            return None
        if size <= 0 or size > MAX_EXE_BYTES:
            return None
        return UpdateRelease(
            version=version,
            tag=tag,
            body=str(item.get("body", "")),
            html_url=str(item.get("html_url", "")),
            asset_name=expected,
            asset_url=url,
            asset_size=size,
            checksum_url=checksum_url,
        )

    def download(
        self,
        release: UpdateRelease,
        destination: Path,
        *,
        progress: Callable[[int, int], None] | None = None,
    ) -> str:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Separate app instances may check/download concurrently. A unique
        # partial avoids one instance truncating or deleting another's stream.
        part = destination.with_name(
            f".{destination.name}.{uuid.uuid4().hex}.part"
        )
        hasher = hashlib.sha256()
        downloaded = 0
        try:
            with _request(
                release.asset_url,
                timeout=max(30.0, self.timeout),
                max_bytes=MAX_EXE_BYTES,
            ) as response, part.open("wb") as output:
                while True:
                    chunk = response.read(1024 * 256)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_EXE_BYTES:
                        raise UpdateError("download exceeded the allowed limit")
                    output.write(chunk)
                    hasher.update(chunk)
                    if progress is not None:
                        progress(downloaded, release.asset_size)
            if downloaded != release.asset_size:
                raise UpdateError(
                    f"download size mismatch: expected {release.asset_size}, got {downloaded}"
                )
            expected = self._download_checksum(release)
            actual = hasher.hexdigest().lower()
            if actual != expected:
                raise UpdateError("SHA-256 verification failed")
            with part.open("rb") as stream:
                if stream.read(2) != b"MZ":
                    raise UpdateError("download is not a Windows executable")
            part.replace(destination)
            return actual
        except Exception:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _download_checksum(self, release: UpdateRelease) -> str:
        with _request(
            release.checksum_url,
            timeout=self.timeout,
            max_bytes=MAX_CHECKSUM_BYTES,
        ) as response:
            raw = response.read(MAX_CHECKSUM_BYTES + 1)
        if len(raw) > MAX_CHECKSUM_BYTES:
            raise UpdateError("checksum response exceeded the allowed limit")
        text = raw.decode("ascii", errors="strict").strip()
        match = re.search(r"(?i)\b([0-9a-f]{64})\b", text)
        if not match:
            raise UpdateError("checksum file does not contain SHA-256")
        return match.group(1).lower()
