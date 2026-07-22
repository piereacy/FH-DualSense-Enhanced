from __future__ import annotations

import logging
import sys
from dataclasses import dataclass


log = logging.getLogger("fhds.dpi")

PER_MONITOR_AWARE_V2 = -4
PER_MONITOR_AWARE = -3
SYSTEM_AWARE = -2
UNAWARE = -1


@dataclass(frozen=True, slots=True)
class DpiSnapshot:
    awareness: str = "not-applicable"
    dpi: int = 96
    scale_percent: int = 100
    per_monitor_v2: bool = False
    bootstrap: str = "not-applicable"
    error: str = ""


_bootstrap_method = "not-run"
_bootstrap_error = ""


def bootstrap_windows_dpi() -> str:
    """Request PMv2 before any Tk window exists, with old-Windows fallbacks."""
    global _bootstrap_method, _bootstrap_error
    if not sys.platform.startswith("win"):
        _bootstrap_method = "not-applicable"
        _bootstrap_error = ""
        return _bootstrap_method
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        setter = getattr(user32, "SetProcessDpiAwarenessContext", None)
        if setter is not None:
            setter.argtypes = (wintypes.HANDLE,)
            setter.restype = wintypes.BOOL
            if setter(ctypes.c_void_p(PER_MONITOR_AWARE_V2)):
                _bootstrap_method = "SetProcessDpiAwarenessContext(PMv2)"
                _bootstrap_error = ""
                return _bootstrap_method
            error = ctypes.get_last_error()
            # ERROR_ACCESS_DENIED normally means the embedded manifest or an
            # earlier runtime hook already selected the process mode.
            if error == 5:
                _bootstrap_method = "already-set"
                _bootstrap_error = ""
                return _bootstrap_method

        try:
            shcore = ctypes.WinDLL("shcore", use_last_error=True)
            set_awareness = shcore.SetProcessDpiAwareness
            set_awareness.argtypes = (ctypes.c_int,)
            set_awareness.restype = ctypes.c_long
            result = int(set_awareness(2))
            if result in (0, -2147024891):  # S_OK or E_ACCESSDENIED
                _bootstrap_method = "SetProcessDpiAwareness(PMv1)"
                _bootstrap_error = ""
                return _bootstrap_method
        except (AttributeError, OSError):
            pass

        legacy = user32.SetProcessDPIAware
        legacy.argtypes = ()
        legacy.restype = wintypes.BOOL
        if legacy():
            _bootstrap_method = "SetProcessDPIAware"
            _bootstrap_error = ""
            return _bootstrap_method
        raise OSError(ctypes.get_last_error(), "Windows rejected all DPI awareness APIs")
    except Exception as exc:
        _bootstrap_method = "failed"
        _bootstrap_error = str(exc) or type(exc).__name__
        return _bootstrap_method


def query_windows_dpi(hwnd: int | None = None) -> DpiSnapshot:
    if not sys.platform.startswith("win"):
        return DpiSnapshot(bootstrap=_bootstrap_method, error=_bootstrap_error)
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        get_context = user32.GetThreadDpiAwarenessContext
        get_context.argtypes = ()
        get_context.restype = wintypes.HANDLE
        context = get_context()

        equal = user32.AreDpiAwarenessContextsEqual
        equal.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        equal.restype = wintypes.BOOL
        if equal(context, ctypes.c_void_p(PER_MONITOR_AWARE_V2)):
            awareness = "Per-Monitor v2"
            pmv2 = True
        elif equal(context, ctypes.c_void_p(PER_MONITOR_AWARE)):
            awareness = "Per-Monitor"
            pmv2 = False
        elif equal(context, ctypes.c_void_p(SYSTEM_AWARE)):
            awareness = "System aware"
            pmv2 = False
        elif equal(context, ctypes.c_void_p(UNAWARE)):
            awareness = "Unaware"
            pmv2 = False
        else:
            awareness = "Unknown"
            pmv2 = False

        dpi = 96
        if hwnd:
            get_dpi_for_window = getattr(user32, "GetDpiForWindow", None)
            if get_dpi_for_window is not None:
                get_dpi_for_window.argtypes = (wintypes.HWND,)
                get_dpi_for_window.restype = wintypes.UINT
                dpi = int(get_dpi_for_window(wintypes.HWND(hwnd))) or 96
        elif getattr(user32, "GetDpiForSystem", None) is not None:
            user32.GetDpiForSystem.restype = wintypes.UINT
            dpi = int(user32.GetDpiForSystem()) or 96
        return DpiSnapshot(
            awareness=awareness,
            dpi=dpi,
            scale_percent=round(dpi * 100 / 96),
            per_monitor_v2=pmv2,
            bootstrap=_bootstrap_method,
            error=_bootstrap_error,
        )
    except Exception as exc:
        return DpiSnapshot(
            awareness="Unknown",
            bootstrap=_bootstrap_method,
            error=str(exc) or type(exc).__name__,
        )


def format_dpi_snapshot(snapshot: DpiSnapshot) -> str:
    return f"DPI: {snapshot.awareness} · {snapshot.scale_percent}%"
