"""Offline ViGEmBus detection and explicitly elevated installation."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from enum import Enum
import hashlib
from pathlib import Path
import sys
from typing import Callable

from ..config import paths
from .vigem_client import ViGEmClient, ViGEmError, ViGEmErrorCode


VIGEM_BUS_INSTALLER_SHA256 = (
    "89220A7865076B342892F98865F3499FB7C4CFD673159E89D352C360FD014C6A"
)
REBOOT_REQUIRED_EXIT_CODES = frozenset({1641, 3010})


class DriverProbeStatus(str, Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    ERROR = "error"


class InstallStatus(str, Enum):
    SUCCESS = "success"
    CANCELLED = "cancelled"
    RESTART_REQUIRED = "restart_required"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DriverProbe:
    status: DriverProbeStatus
    error: str = ""


@dataclass(frozen=True, slots=True)
class InstallResult:
    status: InstallStatus
    exit_code: int | None = None
    error: str = ""


class DriverInstallError(RuntimeError):
    pass


_DRIVER_UNAVAILABLE_CODES = frozenset(
    {
        ViGEmErrorCode.BUS_NOT_FOUND,
        ViGEmErrorCode.BUS_VERSION_MISMATCH,
        ViGEmErrorCode.BUS_ACCESS_FAILED,
    }
)


def probe_vigem_bus(
    client_factory: Callable[[], ViGEmClient] = ViGEmClient,
) -> DriverProbe:
    client = None
    try:
        client = client_factory()
        client.connect()
    except Exception as exc:
        if isinstance(exc, ViGEmError) and exc.code in _DRIVER_UNAVAILABLE_CODES:
            return DriverProbe(DriverProbeStatus.MISSING, str(exc))
        return DriverProbe(DriverProbeStatus.ERROR, str(exc))
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
    return DriverProbe(DriverProbeStatus.AVAILABLE)


def verify_installer_hash(path: Path = paths.VIGEM_BUS_INSTALLER) -> bool:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    except OSError:
        return False
    return digest == VIGEM_BUS_INSTALLER_SHA256


class _GUID(ctypes.Structure):
    _fields_ = (
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    )


class _WINTRUST_FILE_INFO(ctypes.Structure):
    _fields_ = (
        ("cbStruct", wintypes.DWORD),
        ("pcwszFilePath", wintypes.LPCWSTR),
        ("hFile", wintypes.HANDLE),
        ("pgKnownSubject", ctypes.POINTER(_GUID)),
    )


class _WINTRUST_DATA(ctypes.Structure):
    _fields_ = (
        ("cbStruct", wintypes.DWORD),
        ("pPolicyCallbackData", ctypes.c_void_p),
        ("pSIPClientData", ctypes.c_void_p),
        ("dwUIChoice", wintypes.DWORD),
        ("fdwRevocationChecks", wintypes.DWORD),
        ("dwUnionChoice", wintypes.DWORD),
        ("pFile", ctypes.POINTER(_WINTRUST_FILE_INFO)),
        ("dwStateAction", wintypes.DWORD),
        ("hWVTStateData", wintypes.HANDLE),
        ("pwszURLReference", wintypes.LPCWSTR),
        ("dwProvFlags", wintypes.DWORD),
        ("dwUIContext", wintypes.DWORD),
    )


_GENERIC_VERIFY_V2 = _GUID(
    0x00AAC56B,
    0xCD44,
    0x11D0,
    (ctypes.c_ubyte * 8)(0x8C, 0xC2, 0x00, 0xC0, 0x4F, 0xC2, 0x95, 0xEE),
)
_WTD_UI_NONE = 2
_WTD_REVOKE_NONE = 0
_WTD_CHOICE_FILE = 1
_WTD_STATEACTION_VERIFY = 1
_WTD_STATEACTION_CLOSE = 2
_WTD_CACHE_ONLY_URL_RETRIEVAL = 0x00001000


def verify_authenticode_cache_only(path: Path) -> bool:
    """Verify Authenticode without network-backed certificate retrieval."""
    if sys.platform != "win32" or not path.is_file():
        return False
    wintrust = ctypes.WinDLL("wintrust", use_last_error=True)
    verify = wintrust.WinVerifyTrust
    verify.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(_GUID),
        ctypes.POINTER(_WINTRUST_DATA),
    )
    verify.restype = ctypes.c_long
    file_info = _WINTRUST_FILE_INFO(
        cbStruct=ctypes.sizeof(_WINTRUST_FILE_INFO),
        pcwszFilePath=str(path),
        hFile=None,
        pgKnownSubject=None,
    )
    trust_data = _WINTRUST_DATA(
        cbStruct=ctypes.sizeof(_WINTRUST_DATA),
        pPolicyCallbackData=None,
        pSIPClientData=None,
        dwUIChoice=_WTD_UI_NONE,
        fdwRevocationChecks=_WTD_REVOKE_NONE,
        dwUnionChoice=_WTD_CHOICE_FILE,
        pFile=ctypes.pointer(file_info),
        dwStateAction=_WTD_STATEACTION_VERIFY,
        hWVTStateData=None,
        pwszURLReference=None,
        dwProvFlags=_WTD_CACHE_ONLY_URL_RETRIEVAL,
        dwUIContext=0,
    )
    result = verify(None, ctypes.byref(_GENERIC_VERIFY_V2), ctypes.byref(trust_data))
    trust_data.dwStateAction = _WTD_STATEACTION_CLOSE
    verify(None, ctypes.byref(_GENERIC_VERIFY_V2), ctypes.byref(trust_data))
    return result == 0


def validate_installer(
    path: Path = paths.VIGEM_BUS_INSTALLER,
    *,
    signature_verifier: Callable[[Path], bool] = verify_authenticode_cache_only,
) -> None:
    if not verify_installer_hash(path):
        raise DriverInstallError("ViGEmBus installer SHA-256 verification failed")
    if not signature_verifier(path):
        raise DriverInstallError("ViGEmBus installer Authenticode verification failed")


class _SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = (
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    )


_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SW_SHOWNORMAL = 1
_INFINITE = 0xFFFFFFFF
_ERROR_CANCELLED = 1223


def run_installer_elevated(path: Path) -> InstallResult:
    """Show the official installer via UAC and wait for its process exit."""
    if sys.platform != "win32":
        return InstallResult(InstallStatus.FAILED, error="Windows is required")
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    shell_execute = shell32.ShellExecuteExW
    shell_execute.argtypes = (ctypes.POINTER(_SHELLEXECUTEINFOW),)
    shell_execute.restype = wintypes.BOOL
    info = _SHELLEXECUTEINFOW(
        cbSize=ctypes.sizeof(_SHELLEXECUTEINFOW),
        fMask=_SEE_MASK_NOCLOSEPROCESS,
        hwnd=None,
        lpVerb="runas",
        lpFile=str(path),
        lpParameters=None,
        lpDirectory=str(path.parent),
        nShow=_SW_SHOWNORMAL,
        hInstApp=None,
        lpIDList=None,
        lpClass=None,
        hkeyClass=None,
        dwHotKey=0,
        hIconOrMonitor=None,
        hProcess=None,
    )
    if not shell_execute(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == _ERROR_CANCELLED:
            return InstallResult(InstallStatus.CANCELLED, error="UAC was cancelled")
        return InstallResult(
            InstallStatus.FAILED,
            error=f"ShellExecuteExW failed with Windows error {error}",
        )
    if not info.hProcess:
        return InstallResult(InstallStatus.FAILED, error="installer process handle is missing")
    try:
        kernel32.WaitForSingleObject(info.hProcess, _INFINITE)
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code)):
            error = ctypes.get_last_error()
            return InstallResult(
                InstallStatus.FAILED,
                error=f"GetExitCodeProcess failed with Windows error {error}",
            )
    finally:
        kernel32.CloseHandle(info.hProcess)
    code = int(exit_code.value)
    if code == 0:
        return InstallResult(InstallStatus.SUCCESS, exit_code=code)
    if code in REBOOT_REQUIRED_EXIT_CODES:
        return InstallResult(InstallStatus.RESTART_REQUIRED, exit_code=code)
    return InstallResult(
        InstallStatus.FAILED,
        exit_code=code,
        error=f"ViGEmBus installer exited with code {code}",
    )


def install_and_probe(
    path: Path = paths.VIGEM_BUS_INSTALLER,
    *,
    signature_verifier: Callable[[Path], bool] = verify_authenticode_cache_only,
    runner: Callable[[Path], InstallResult] = run_installer_elevated,
    probe: Callable[[], DriverProbe] = probe_vigem_bus,
) -> InstallResult:
    """Validate, explicitly elevate, then require a working bus or a restart."""
    try:
        validate_installer(path, signature_verifier=signature_verifier)
    except DriverInstallError as exc:
        return InstallResult(InstallStatus.FAILED, error=str(exc))
    result = runner(path)
    if result.status is not InstallStatus.SUCCESS:
        return result
    post_install = probe()
    if post_install.status is DriverProbeStatus.AVAILABLE:
        return result
    return InstallResult(
        InstallStatus.RESTART_REQUIRED,
        exit_code=result.exit_code,
        error=post_install.error or "ViGEmBus is not available until Windows restarts",
    )
