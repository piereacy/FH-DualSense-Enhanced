"""Explicit, verified on-demand installation of the official HidHide driver."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import Request, urlopen

from ..config import paths
from ..xinput.driver import (
    InstallResult,
    InstallStatus,
    run_installer_elevated,
    verify_authenticode_cache_only,
)
from .hidhide import _detect, _open_driver


HIDHIDE_VERSION = "1.5.230"
HIDHIDE_INSTALLER_NAME = "HidHide_1.5.230_x64.exe"
HIDHIDE_INSTALLER_URL = (
    "https://github.com/nefarius/HidHide/releases/download/"
    "v1.5.230.0/HidHide_1.5.230_x64.exe"
)
HIDHIDE_INSTALLER_SIZE = 8_078_016
HIDHIDE_INSTALLER_SHA256 = (
    "F4BBBCB82E6258641B887C74BC81C4C5F66E4AA811808DFC304347687B7605F6"
)
HIDHIDE_PRODUCT_CODE = "{01E0AB21-D1CC-42B4-9DFF-84FFE4F26DAF}"
HIDHIDE_CLIENT_SIZE = 331_688
HIDHIDE_CLIENT_SHA256 = (
    "4AF4752F0564E9C2A2B139B05DA4BBFCC4AB111A03033319EB38B7EC9B070A45"
)
HIDHIDE_INSTALLER_CACHE = paths.DATA / "installers" / HIDHIDE_INSTALLER_NAME
HIDHIDE_INSTALL_TIMEOUT_MS = 120_000
HIDHIDE_DRIVER_UNAVAILABLE = (
    "HidHide is installed but its driver is unavailable; "
    "close the configuration client or restart Windows"
)


@dataclass(frozen=True)
class HidHideDetection:
    installed: bool
    driver_ready: bool


class HidHideInstallStage(Enum):
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    INSTALLING = "installing"
    PROBING = "probing"


@dataclass(frozen=True)
class HidHideInstallProgress:
    stage: HidHideInstallStage
    fraction: float | None = None


ProgressCallback = Callable[[HidHideInstallProgress], None]


def _report(
    callback: ProgressCallback | None,
    stage: HidHideInstallStage,
    fraction: float | None = None,
) -> None:
    if callback is not None:
        callback(HidHideInstallProgress(stage, fraction))


def detect_hidhide() -> HidHideDetection:
    """Keep installation detection separate from control-device readiness."""
    ready = probe_hidhide()
    return HidHideDetection(installed=ready or _detect(), driver_ready=ready)


def find_hidhide_client() -> Path | None:
    """Find the official client, including the verified MSI source when files are missing."""
    if sys.platform != "win32":
        return None
    install_root = (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        / "Nefarius Software Solutions"
        / "HidHide"
    )
    for path in (install_root / "x64" / "HidHideClient.exe", install_root / "HidHideClient.exe"):
        if path.is_file():
            return path
    return _find_cached_hidhide_client()


def _find_cached_hidhide_client() -> Path | None:
    """Advanced Installer keeps a signed client in the registered MSI source."""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            rf"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{HIDHIDE_PRODUCT_CODE}",
        ) as key:
            version = winreg.QueryValueEx(key, "DisplayVersion")[0]
            source = winreg.QueryValueEx(key, "InstallSource")[0]
        if version != HIDHIDE_VERSION or not isinstance(source, str):
            return None
        client = Path(source) / "x64" / "HidHideClient.exe"
        if client.stat().st_size != HIDHIDE_CLIENT_SIZE:
            return None
        digest = hashlib.sha256()
        with client.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return client if digest.hexdigest().upper() == HIDHIDE_CLIENT_SHA256 else None
    except (OSError, ValueError):
        return None


def open_hidhide_client() -> Path:
    """Open HidHide's own UI on an explicit action in the FHDS UI."""
    client = find_hidhide_client()
    if client is None:
        raise FileNotFoundError("HidHide Configuration Client is not installed")
    subprocess.Popen([str(client)], cwd=str(client.parent), close_fds=True)
    return client


def probe_hidhide() -> bool:
    if sys.platform != "win32":
        return False
    try:
        with _open_driver() as api:
            api.get_active()
    except Exception:
        return False
    return True


def verify_installer(
    path: Path,
    *,
    signature_verifier: Callable[[Path], bool] = verify_authenticode_cache_only,
) -> bool:
    try:
        if path.stat().st_size != HIDHIDE_INSTALLER_SIZE:
            return False
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return (
            digest.hexdigest().upper() == HIDHIDE_INSTALLER_SHA256
            and signature_verifier(path)
        )
    except (OSError, ValueError):
        return False


def download_installer(
    path: Path = HIDHIDE_INSTALLER_CACHE,
    *,
    signature_verifier: Callable[[Path], bool] = verify_authenticode_cache_only,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Cache only the fixed release asset after size, hash, and signature checks."""
    _report(on_progress, HidHideInstallStage.VERIFYING)
    if verify_installer(path, signature_verifier=signature_verifier):
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(HIDHIDE_INSTALLER_URL, headers={"User-Agent": "FHDS-HidHide-Installer"})
    for attempt in range(3):
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.part")
        try:
            digest = hashlib.sha256()
            count = 0
            with urlopen(request, timeout=30) as response, temporary.open("xb") as stream:
                if response.geturl() != HIDHIDE_INSTALLER_URL and not response.geturl().startswith(
                    "https://release-assets.githubusercontent.com/"
                ):
                    raise ValueError("HidHide download redirected outside the official release assets")
                _report(on_progress, HidHideInstallStage.DOWNLOADING, 0.0)
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    if count > HIDHIDE_INSTALLER_SIZE:
                        raise ValueError("HidHide installer exceeds its pinned size")
                    digest.update(chunk)
                    stream.write(chunk)
                    _report(
                        on_progress,
                        HidHideInstallStage.DOWNLOADING,
                        count / HIDHIDE_INSTALLER_SIZE,
                    )
                stream.flush()
                os.fsync(stream.fileno())
            if count != HIDHIDE_INSTALLER_SIZE or digest.hexdigest().upper() != HIDHIDE_INSTALLER_SHA256:
                raise ValueError("HidHide installer size or SHA-256 does not match the pinned release")
            _report(on_progress, HidHideInstallStage.VERIFYING)
            if not signature_verifier(temporary):
                raise ValueError("HidHide installer Authenticode verification failed")
            temporary.replace(path)
            return path
        except (URLError, TimeoutError, ConnectionError):
            if attempt == 2:
                raise
        finally:
            temporary.unlink(missing_ok=True)
    raise RuntimeError("HidHide download failed")


def install_and_probe(
    *,
    path: Path = HIDHIDE_INSTALLER_CACHE,
    probe: Callable[[], bool] = probe_hidhide,
    downloader: Callable[..., Path] = download_installer,
    runner: Callable[..., InstallResult] = run_installer_elevated,
    installed_marker: Callable[[], bool] = _detect,
    on_progress: ProgressCallback | None = None,
) -> InstallResult:
    """Download and elevate only after an explicit user action in the UI."""
    _report(on_progress, HidHideInstallStage.CHECKING)
    if sys.platform != "win32":
        return InstallResult(InstallStatus.FAILED, error="HidHide requires Windows x64")
    if probe():
        return InstallResult(InstallStatus.SUCCESS)
    if installed_marker():
        return InstallResult(
            InstallStatus.RESTART_REQUIRED,
            error=HIDHIDE_DRIVER_UNAVAILABLE,
        )
    try:
        installer = (
            downloader(path, on_progress=on_progress)
            if on_progress is not None
            else downloader(path)
        )
    except Exception as exc:
        return InstallResult(InstallStatus.FAILED, error=f"HidHide download or verification failed: {exc}")
    else:
        try:
            _report(on_progress, HidHideInstallStage.INSTALLING)
            result = runner(
                installer,
                parameters="/quiet /norestart",
                product_name="HidHide",
                timeout_ms=HIDHIDE_INSTALL_TIMEOUT_MS,
            )
        except Exception as exc:
            return InstallResult(InstallStatus.FAILED, error=f"HidHide installer could not start: {exc}")
        else:
            _report(on_progress, HidHideInstallStage.PROBING)
            if result.status is not InstallStatus.SUCCESS:
                if probe():
                    return InstallResult(InstallStatus.SUCCESS, exit_code=result.exit_code)
                return result
            if probe():
                return result
            return InstallResult(
                InstallStatus.RESTART_REQUIRED,
                exit_code=result.exit_code,
                error="Restart Windows to activate the HidHide driver",
            )
