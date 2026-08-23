"""Forza process-table and Windows foreground-window observation helpers."""
import logging
import math
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

import psutil

log = logging.getLogger("fhds")


@dataclass(frozen=True, slots=True)
class GameProcess:
    name: str
    exe: str
    pid: int | None


class ProcessScanError(RuntimeError):
    """Operating-system process or foreground state could not be read reliably."""


def _windows_foreground_pid() -> int | None:
    """Return the foreground-window PID without importing a Win32 package."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    get_foreground_window = user32.GetForegroundWindow
    get_foreground_window.argtypes = ()
    get_foreground_window.restype = wintypes.HWND
    get_window_thread_process_id = user32.GetWindowThreadProcessId
    get_window_thread_process_id.argtypes = (
        wintypes.HWND,
        ctypes.POINTER(wintypes.DWORD),
    )
    get_window_thread_process_id.restype = wintypes.DWORD

    window = get_foreground_window()
    if not window:
        return None
    pid = wintypes.DWORD()
    if not get_window_thread_process_id(window, ctypes.byref(pid)):
        return None
    return int(pid.value) or None


def find_foreground_process(
    *,
    exact_names: tuple[str, ...] = (),
    strict: bool = False,
    platform: str | None = None,
    foreground_pid: Callable[[], int | None] | None = None,
    process_factory: Callable[[int], object] = psutil.Process,
) -> GameProcess | None:
    """Return the exact executable that owns the Windows foreground window.

    A missing foreground window or a window that vanishes during the query is
    a normal inactive edge. API/access failures can be distinguished with
    ``strict=True`` so controller output fails closed.
    """
    if (platform or sys.platform) != "win32":
        return None
    pid_getter = foreground_pid or _windows_foreground_pid
    try:
        pid = pid_getter()
    except Exception as exc:
        if strict:
            raise ProcessScanError(f"foreground window query failed: {exc}") from exc
        log.warning("foreground window query failed: %s", exc)
        return None
    if pid is None:
        return None

    try:
        process = process_factory(int(pid))
        name_getter = getattr(process, "name")
        name = str(name_getter() or "")
        try:
            exe_getter = getattr(process, "exe")
            exe = str(exe_getter() or "")
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError, AttributeError):
            exe = ""
    except psutil.NoSuchProcess:
        # Focus can change between the two Win32 calls and the psutil lookup.
        return None
    except (psutil.AccessDenied, psutil.ZombieProcess, OSError, AttributeError) as exc:
        if strict:
            raise ProcessScanError(f"foreground process lookup failed: {exc}") from exc
        log.warning("foreground process lookup failed: %s", exc)
        return None
    except Exception as exc:
        if strict:
            raise ProcessScanError(f"foreground process lookup failed: {exc}") from exc
        log.warning("foreground process lookup failed: %s", exc)
        return None

    exacts = frozenset(name.casefold() for name in exact_names if str(name).strip())
    exe_base = os.path.basename(exe)
    if exacts and name.casefold() not in exacts and exe_base.casefold() not in exacts:
        return None
    return GameProcess(name=name or exe_base, exe=exe, pid=int(pid))


def find_game_process(
    name_contains=("forza",),
    *,
    exact_name: str = "",
    exact_names: tuple[str, ...] = (),
    strict: bool = False,
) -> GameProcess | None:
    """Return a matching process while tolerating protected/vanishing entries.

    With ``strict=True``, a process-table failure is distinguished from a
    successful scan with no match. Mutating game-file tools use that mode so
    an OS query failure cannot be mistaken for "the game is closed".
    """
    needles = tuple(n.lower() for n in name_contains)
    exacts = frozenset(
        name.casefold()
        for name in (exact_name, *exact_names)
        if str(name).strip()
    )
    try:
        iterator = psutil.process_iter(["name", "exe"])
    except Exception as e:
        if strict:
            raise ProcessScanError(f"process_iter failed: {e}") from e
        log.warning("process_iter failed: %s", e)
        return None
    try:
        for process in iterator:
            try:
                name = process.info.get("name") or ""
                exe = process.info.get("exe") or ""
                exe_base = os.path.basename(exe)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError):
                continue
            except Exception:
                continue
            if exacts:
                if name.casefold() not in exacts and exe_base.casefold() not in exacts:
                    continue
            else:
                haystack = (name + " " + exe_base).lower()
                if not any(needle in haystack for needle in needles):
                    continue
            try:
                pid = int(process.pid)
            except (AttributeError, TypeError, ValueError):
                pid = None
            return GameProcess(name=name or exe_base, exe=exe, pid=pid)
    except Exception as e:
        if strict:
            raise ProcessScanError(f"process table iteration failed: {e}") from e
        log.warning("process table iteration failed: %s", e)
    return None


class ProcessWatcher:
    def __init__(self, name_contains=("forza",), poll_interval_s: float = 1.0):
        self.needles = tuple(n.lower() for n in name_contains)
        try:
            interval = float(poll_interval_s)
        except (TypeError, ValueError, OverflowError):
            interval = 1.0
        self.poll_interval = interval if math.isfinite(interval) and interval >= 0.1 else 1.0
        self._last_check = 0.0
        self._matched = None  # actual process name we locked onto

    def _find(self) -> str | None:
        found = find_game_process(self.needles, strict=True)
        return found.name if found is not None else None

    def should_exit(self) -> bool:
        """True once the watched process has been seen and then disappeared.
        Throttled to one real check per poll_interval_s."""
        now = time.monotonic()
        if now - self._last_check < self.poll_interval:
            return False
        self._last_check = now
        # MARK: never let a psutil/OS error kill the main loop
        try:
            found = self._find()
        except Exception as e:
            log.warning("ProcessWatcher._find crashed: %s", e)
            return False
        if found and not self._matched:
            self._matched = found
            log.info("Detected game process '%s' - will exit when it closes.", found)
            return False
        if self._matched and not found:
            log.info("Game process '%s' closed.", self._matched)
            return True
        return False
