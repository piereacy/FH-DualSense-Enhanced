"""Exit when the Forza Horizon process disappears. Cross-platform: Windows + Linux/Proton
(Proton runs the Windows binary, so the process name is the same on both)."""
import logging
import math
import os
import time
from dataclasses import dataclass

import psutil

log = logging.getLogger("fhds")


@dataclass(frozen=True, slots=True)
class GameProcess:
    name: str
    exe: str
    pid: int | None


class ProcessScanError(RuntimeError):
    """The operating-system process table could not be scanned reliably."""


def find_game_process(
    name_contains=("forza",),
    *,
    exact_name: str = "",
    strict: bool = False,
) -> GameProcess | None:
    """Return a matching process while tolerating protected/vanishing entries.

    With ``strict=True``, a process-table failure is distinguished from a
    successful scan with no match. Mutating game-file tools use that mode so
    an OS query failure cannot be mistaken for "the game is closed".
    """
    needles = tuple(n.lower() for n in name_contains)
    exact = exact_name.lower()
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
            if exact:
                if name.lower() != exact and exe_base.lower() != exact:
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
