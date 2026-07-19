"""Minimal, hash-pinned ViGEmClient ctypes adapter.

Only the client and Xbox 360 target functions needed by FH-DualSense-Enhanced
are exposed.  No vibration callback is registered, so game rumble is neither
captured nor forwarded by this layer.
"""
from __future__ import annotations

import ctypes
import hashlib
import platform
import sys
from enum import IntEnum
from pathlib import Path
from typing import Any

from ..config import paths
from .report import XUSBReport


VIGEM_CLIENT_SHA256 = "2BF0CB1D809039573C922737D298A1653D4DBC61408060FF45A9BCFDE82E97D2"


class ViGEmErrorCode(IntEnum):
    NONE = 0x20000000
    BUS_NOT_FOUND = 0xE0000001
    NO_FREE_SLOT = 0xE0000002
    INVALID_TARGET = 0xE0000003
    REMOVAL_FAILED = 0xE0000004
    ALREADY_CONNECTED = 0xE0000005
    TARGET_UNINITIALIZED = 0xE0000006
    TARGET_NOT_PLUGGED_IN = 0xE0000007
    BUS_VERSION_MISMATCH = 0xE0000008
    BUS_ACCESS_FAILED = 0xE0000009
    CALLBACK_ALREADY_REGISTERED = 0xE0000010
    CALLBACK_NOT_FOUND = 0xE0000011
    BUS_ALREADY_CONNECTED = 0xE0000012
    BUS_INVALID_HANDLE = 0xE0000013
    XUSB_USERINDEX_OUT_OF_RANGE = 0xE0000014
    INVALID_PARAMETER = 0xE0000015
    NOT_SUPPORTED = 0xE0000016


class ViGEmError(RuntimeError):
    def __init__(self, operation: str, code: int | None = None):
        self.operation = operation
        self.code = None if code is None else ctypes.c_uint32(code).value
        if self.code is None:
            detail = operation
        else:
            try:
                name = ViGEmErrorCode(self.code).name
            except ValueError:
                name = "UNKNOWN"
            detail = f"{operation} failed: {name} (0x{self.code:08X})"
        super().__init__(detail)


def is_supported_platform() -> bool:
    return sys.platform == "win32" and platform.machine().casefold() in {
        "amd64",
        "x86_64",
    }


def verify_client_hash(path: Path = paths.VIGEM_CLIENT_DLL) -> bool:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
    except OSError:
        return False
    return digest == VIGEM_CLIENT_SHA256


def _bind(dll: Any, name: str, argtypes: tuple[Any, ...], restype: Any):
    try:
        function = getattr(dll, name)
    except AttributeError as exc:
        raise ViGEmError(f"missing ViGEmClient export {name}") from exc
    function.argtypes = argtypes
    function.restype = restype
    return function


class ViGEmClient:
    """One ViGEm bus connection and its owned Xbox 360 targets."""

    def __init__(self, dll_path: Path = paths.VIGEM_CLIENT_DLL, *, dll: Any = None):
        if dll is None:
            if not is_supported_platform():
                raise ViGEmError("ViGEm is supported only on Windows x64")
            if not verify_client_hash(dll_path):
                raise ViGEmError("ViGEmClient.dll SHA-256 verification")
            try:
                dll = ctypes.CDLL(str(dll_path))
            except OSError as exc:
                raise ViGEmError(f"load {dll_path.name}") from exc
        self._dll = dll
        self._alloc = _bind(dll, "vigem_alloc", (), ctypes.c_void_p)
        self._free = _bind(dll, "vigem_free", (ctypes.c_void_p,), None)
        self._connect = _bind(dll, "vigem_connect", (ctypes.c_void_p,), ctypes.c_uint32)
        self._disconnect = _bind(dll, "vigem_disconnect", (ctypes.c_void_p,), None)
        self._target_alloc = _bind(dll, "vigem_target_x360_alloc", (), ctypes.c_void_p)
        self._target_free = _bind(dll, "vigem_target_free", (ctypes.c_void_p,), None)
        self._target_add = _bind(
            dll,
            "vigem_target_add",
            (ctypes.c_void_p, ctypes.c_void_p),
            ctypes.c_uint32,
        )
        self._target_remove = _bind(
            dll,
            "vigem_target_remove",
            (ctypes.c_void_p, ctypes.c_void_p),
            ctypes.c_uint32,
        )
        self._target_update = _bind(
            dll,
            "vigem_target_x360_update",
            (ctypes.c_void_p, ctypes.c_void_p, XUSBReport),
            ctypes.c_uint32,
        )
        self._handle: int | None = None
        self._targets: list[X360Target] = []

    @property
    def connected(self) -> bool:
        return self._handle is not None

    def connect(self) -> None:
        if self.connected:
            return
        handle = self._alloc()
        if not handle:
            raise ViGEmError("vigem_alloc returned null")
        self._handle = handle
        try:
            self._check("vigem_connect", self._connect(handle))
        except Exception:
            self._free(handle)
            self._handle = None
            raise

    def create_x360_target(self) -> "X360Target":
        if not self.connected:
            raise ViGEmError("create target without a connected client")
        handle = self._target_alloc()
        if not handle:
            raise ViGEmError("vigem_target_x360_alloc returned null")
        target = X360Target(self, handle)
        try:
            self._check("vigem_target_add", self._target_add(self._handle, handle))
        except Exception:
            self._target_free(handle)
            raise
        target._attached = True
        self._targets.append(target)
        return target

    def close(self) -> None:
        for target in tuple(self._targets):
            target.close(suppress_errors=True)
        handle = self._handle
        self._handle = None
        if handle is not None:
            try:
                self._disconnect(handle)
            finally:
                self._free(handle)

    @staticmethod
    def _check(operation: str, result: int) -> None:
        code = ctypes.c_uint32(result).value
        if code != ViGEmErrorCode.NONE:
            raise ViGEmError(operation, code)

    def __enter__(self) -> "ViGEmClient":
        self.connect()
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()


class X360Target:
    def __init__(self, client: ViGEmClient, handle: int):
        self._client = client
        self._handle: int | None = handle
        self._attached = False

    @property
    def attached(self) -> bool:
        return self._attached and self._handle is not None

    def update(self, report: XUSBReport) -> None:
        if not self.attached or not self._client.connected:
            raise ViGEmError("update detached Xbox 360 target")
        self._client._check(
            "vigem_target_x360_update",
            self._client._target_update(
                self._client._handle,
                self._handle,
                report,
            ),
        )

    def close(self, *, suppress_errors: bool = False) -> None:
        handle = self._handle
        if handle is None:
            return
        self._handle = None
        remove_error: Exception | None = None
        if self._attached and self._client.connected:
            try:
                self._client._check(
                    "vigem_target_remove",
                    self._client._target_remove(self._client._handle, handle),
                )
            except Exception as exc:
                remove_error = exc
        self._attached = False
        self._client._target_free(handle)
        try:
            self._client._targets.remove(self)
        except ValueError:
            pass
        if remove_error is not None and not suppress_errors:
            raise remove_error
