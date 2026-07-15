"""Minimal Windows self-update helper, packaged separately from the main EXE."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wait_for_pid_windows(pid: int, timeout: float) -> None:
    """Wait without sending a signal to the process.

    ``os.kill(pid, 0)`` is a harmless existence probe on POSIX, but Windows
    treats non-console-control signals as process termination. Use a waitable
    process handle instead so the updater can never kill the main app while
    merely checking whether it has exited.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    wait_for_single_object.restype = wintypes.DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    synchronize = 0x00100000
    wait_object_0 = 0x00000000
    wait_timeout = 0x00000102
    handle = open_process(synchronize, False, int(pid))
    if not handle:
        # The process is already gone, or cannot be opened. The helper only
        # receives the PID of its own parent, so a failed open is safe to treat
        # as exited and the atomic rename remains the final authority.
        return
    try:
        result = wait_for_single_object(handle, max(0, int(timeout * 1000)))
    finally:
        close_handle(handle)
    if result == wait_object_0:
        return
    if result == wait_timeout:
        raise TimeoutError(f"process {pid} did not exit")
    raise OSError(f"WaitForSingleObject failed with result 0x{result:08x}")


def wait_for_pid(pid: int, timeout: float = 30.0) -> None:
    if os.name == "nt":
        _wait_for_pid_windows(pid, timeout)
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.2)
    raise TimeoutError(f"process {pid} did not exit")


def apply(plan_path: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    pid = int(plan["pid"])
    staged = Path(plan["staged"]).resolve()
    target = Path(plan["target"]).resolve()
    expected = str(plan["sha256"]).lower()
    if not staged.is_file() or sha256(staged).lower() != expected:
        raise ValueError("staged update failed checksum validation")
    if staged == target:
        raise ValueError("invalid update paths")
    if staged.suffix.lower() != ".exe" or target.suffix.lower() != ".exe":
        raise ValueError("update paths must point to Windows executables")

    wait_for_pid(pid)
    old = Path(str(target) + ".old")
    old.unlink(missing_ok=True)
    moved_old = False
    try:
        if target.exists():
            target.replace(old)
            moved_old = True
        staged.replace(target)
        subprocess.Popen([str(target), *plan.get("args", [])], cwd=str(target.parent))
        plan_path.unlink(missing_ok=True)
    except Exception:
        try:
            if target.exists():
                target.unlink()
            if moved_old and old.exists():
                old.replace(target)
        finally:
            raise


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        apply(Path(sys.argv[1]).resolve())
    except Exception as exc:
        log = Path(sys.argv[1]).with_name("update-helper-error.log")
        log.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
