"""Keyboard/mouse ownership and deliberate controller-change detection."""
from __future__ import annotations

import ctypes
import logging
import sys
import threading
from ctypes import wintypes
from typing import Callable, Protocol

from ..dualsense.input_state import DPad, DualSenseInputState


log = logging.getLogger("fhds.xinput")

STICK_ACTIVITY_DELTA = 12
TRIGGER_ACTIVITY_DELTA = 8

_WM_DESTROY = 0x0002
_WM_CLOSE = 0x0010
_WM_INPUT = 0x00FF
_RIDEV_REMOVE = 0x00000001
_RIDEV_INPUTSINK = 0x00000100
_HID_USAGE_PAGE_GENERIC = 0x01
_HID_USAGE_GENERIC_MOUSE = 0x02
_HID_USAGE_GENERIC_KEYBOARD = 0x06

_LRESULT = ctypes.c_ssize_t
_WNDPROC_FACTORY = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
_WNDPROC = _WNDPROC_FACTORY(
    _LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class _WNDCLASSW(ctypes.Structure):
    _fields_ = (
        ("style", wintypes.UINT),
        ("lpfnWndProc", _WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    )


class _RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = (
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    )


class _ActivityListener(Protocol):
    @property
    def alive(self) -> bool: ...

    @property
    def running(self) -> bool: ...

    def start(self) -> bool: ...

    def stop(self) -> None: ...


ActivityListenerFactory = Callable[[Callable[[], None]], _ActivityListener]


class _WindowsRawInputListener:
    """Receive keyboard/mouse WM_INPUT messages on a private worker window."""

    def __init__(
        self,
        on_activity: Callable[[], None],
        *,
        start_timeout_s: float = 1.0,
        stop_timeout_s: float = 2.0,
    ):
        self._on_activity = on_activity
        self._lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._ready = threading.Event()
        self._stop_requested: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._hwnd = None
        self._user32 = None
        self._wndproc = None
        self._start_error: Exception | None = None
        self._start_serial = 0
        self._start_timeout_s = max(0.0, float(start_timeout_s))
        self._stop_timeout_s = max(0.0, float(stop_timeout_s))

    @property
    def alive(self) -> bool:
        with self._lock:
            thread = self._thread
            return bool(thread is not None and thread.is_alive())

    @property
    def running(self) -> bool:
        with self._lock:
            thread = self._thread
            stop_requested = self._stop_requested
            return bool(
                thread is not None
                and thread.is_alive()
                and self._hwnd
                and (stop_requested is None or not stop_requested.is_set())
            )

    def start(self) -> bool:
        with self._lifecycle_lock:
            with self._lock:
                thread = self._thread
                if thread is not None and thread.is_alive():
                    return bool(
                        self._hwnd is not None
                        and self._stop_requested is not None
                        and not self._stop_requested.is_set()
                    )
                self._ready.clear()
                self._start_error = None
                self._start_serial += 1
                serial = self._start_serial
                stop_requested = threading.Event()
                self._stop_requested = stop_requested
                thread = threading.Thread(
                    target=self._run,
                    args=(serial, stop_requested),
                    name="fhds-raw-input",
                    daemon=True,
                )
                self._thread = thread
            thread.start()
            if not self._ready.wait(self._start_timeout_s):
                log.warning(
                    "Keyboard/mouse Raw Input listener did not start within %.3g seconds",
                    self._start_timeout_s,
                )
                self.stop()
                return False
            with self._lock:
                error = self._start_error
                started = (
                    self._hwnd is not None
                    and thread.is_alive()
                    and not stop_requested.is_set()
                )
            if error is not None:
                log.warning("Keyboard/mouse Raw Input listener is unavailable: %s", error)
            if not started:
                self.stop()
            return started

    def stop(self) -> None:
        with self._lifecycle_lock:
            with self._lock:
                thread = self._thread
                stop_requested = self._stop_requested
                hwnd = self._hwnd
                user32 = self._user32
            if stop_requested is not None:
                stop_requested.set()
            if hwnd and user32 is not None:
                try:
                    user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
                except Exception:
                    pass
            if thread is not None and thread is not threading.current_thread():
                thread.join(timeout=self._stop_timeout_s)
            if thread is not None and thread.is_alive():
                log.error(
                    "Keyboard/mouse Raw Input listener did not stop within %.3g seconds",
                    self._stop_timeout_s,
                )
                return
            with self._lock:
                if self._thread is thread:
                    self._thread = None
                    self._stop_requested = None
                self._hwnd = None
                self._user32 = None
                self._wndproc = None

    def _run(self, serial: int, stop_requested: threading.Event) -> None:
        user32 = None
        hinstance = None
        class_name = f"FHDSRawInput_{id(self):x}_{serial}"
        class_registered = False
        devices_registered = False
        hwnd = None
        try:
            self._before_startup()
            if stop_requested.is_set():
                return
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            if stop_requested.is_set():
                return
            self._configure_apis(user32, kernel32)
            if stop_requested.is_set():
                return
            hinstance = kernel32.GetModuleHandleW(None)
            if not hinstance:
                raise ctypes.WinError(ctypes.get_last_error())
            if stop_requested.is_set():
                return

            @_WNDPROC
            def window_proc(window, message, wparam, lparam):
                if message == _WM_INPUT:
                    self._on_activity()
                    return user32.DefWindowProcW(window, message, wparam, lparam)
                if message == _WM_CLOSE:
                    user32.DestroyWindow(window)
                    return 0
                if message == _WM_DESTROY:
                    user32.PostQuitMessage(0)
                    return 0
                return user32.DefWindowProcW(window, message, wparam, lparam)

            window_class = _WNDCLASSW(
                hInstance=hinstance,
                lpfnWndProc=window_proc,
                lpszClassName=class_name,
            )
            if not user32.RegisterClassW(ctypes.byref(window_class)):
                raise ctypes.WinError(ctypes.get_last_error())
            class_registered = True
            if stop_requested.is_set():
                return

            hwnd_message = wintypes.HWND(-3)
            hwnd = user32.CreateWindowExW(
                0,
                class_name,
                "",
                0,
                0,
                0,
                0,
                0,
                hwnd_message,
                None,
                hinstance,
                None,
            )
            if not hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            if stop_requested.is_set():
                return

            devices = (_RAWINPUTDEVICE * 2)(
                _RAWINPUTDEVICE(
                    _HID_USAGE_PAGE_GENERIC,
                    _HID_USAGE_GENERIC_MOUSE,
                    _RIDEV_INPUTSINK,
                    hwnd,
                ),
                _RAWINPUTDEVICE(
                    _HID_USAGE_PAGE_GENERIC,
                    _HID_USAGE_GENERIC_KEYBOARD,
                    _RIDEV_INPUTSINK,
                    hwnd,
                ),
            )
            if not user32.RegisterRawInputDevices(
                devices,
                len(devices),
                ctypes.sizeof(_RAWINPUTDEVICE),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            devices_registered = True

            with self._lock:
                if stop_requested.is_set() or serial != self._start_serial:
                    return
                self._hwnd = hwnd
                self._user32 = user32
                self._wndproc = window_proc
            self._ready.set()

            message = wintypes.MSG()
            while True:
                result = int(user32.GetMessageW(ctypes.byref(message), None, 0, 0))
                if result == 0:
                    break
                if result == -1:
                    raise ctypes.WinError(ctypes.get_last_error())
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
        except Exception as exc:
            with self._lock:
                self._start_error = exc
            if self._ready.is_set():
                log.warning("Keyboard/mouse Raw Input listener stopped: %s", exc)
        finally:
            if user32 is not None and devices_registered:
                remove_devices = (_RAWINPUTDEVICE * 2)(
                    _RAWINPUTDEVICE(
                        _HID_USAGE_PAGE_GENERIC,
                        _HID_USAGE_GENERIC_MOUSE,
                        _RIDEV_REMOVE,
                        None,
                    ),
                    _RAWINPUTDEVICE(
                        _HID_USAGE_PAGE_GENERIC,
                        _HID_USAGE_GENERIC_KEYBOARD,
                        _RIDEV_REMOVE,
                        None,
                    ),
                )
                user32.RegisterRawInputDevices(
                    remove_devices,
                    len(remove_devices),
                    ctypes.sizeof(_RAWINPUTDEVICE),
                )
            if user32 is not None and hwnd and user32.IsWindow(hwnd):
                user32.DestroyWindow(hwnd)
            if user32 is not None and class_registered and hinstance:
                user32.UnregisterClassW(class_name, hinstance)
            with self._lock:
                self._hwnd = None
                self._user32 = None
                self._wndproc = None
                if self._thread is threading.current_thread():
                    self._thread = None
                    self._stop_requested = None
            self._ready.set()

    def _before_startup(self) -> None:
        """Test seam for a startup delay before any Win32 resources exist."""

    @staticmethod
    def _configure_apis(user32, kernel32) -> None:
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

        user32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASSW)]
        user32.RegisterClassW.restype = wintypes.ATOM
        user32.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
        user32.UnregisterClassW.restype = wintypes.BOOL
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HANDLE,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.DestroyWindow.restype = wintypes.BOOL
        user32.IsWindow.argtypes = [wintypes.HWND]
        user32.IsWindow.restype = wintypes.BOOL
        user32.PostMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.PostMessageW.restype = wintypes.BOOL
        user32.PostQuitMessage.argtypes = [ctypes.c_int]
        user32.PostQuitMessage.restype = None
        user32.DefWindowProcW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.DefWindowProcW.restype = _LRESULT
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.GetMessageW.restype = wintypes.BOOL
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.TranslateMessage.restype = wintypes.BOOL
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = _LRESULT
        user32.RegisterRawInputDevices.argtypes = [
            ctypes.POINTER(_RAWINPUTDEVICE),
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.RegisterRawInputDevices.restype = wintypes.BOOL


class KeyboardMouseActivityMonitor:
    """Coalesce background Raw Input keyboard/mouse events into pollable edges."""

    def __init__(self, listener_factory: ActivityListenerFactory | None = None):
        if listener_factory is None and sys.platform == "win32":
            listener_factory = _WindowsRawInputListener
        self._listener_factory = listener_factory
        self._listener: _ActivityListener | None = None
        self._lifecycle_lock = threading.Lock()
        self._lock = threading.Lock()
        self._generation = 0
        self._seen_generation = 0

    @property
    def available(self) -> bool:
        return self._listener_factory is not None

    @property
    def running(self) -> bool:
        with self._lock:
            listener = self._listener
        return bool(listener is not None and listener.running)

    def start(self) -> bool:
        with self._lifecycle_lock:
            with self._lock:
                listener = self._listener
                factory = self._listener_factory
            if listener is not None and listener.running:
                return True
            if listener is not None and listener.alive:
                return False
            if factory is None:
                return False
            try:
                listener = factory(self._record_activity)
                with self._lock:
                    self._listener = listener
                started = listener.start()
            except Exception as exc:
                log.warning("Keyboard/mouse hot-switch monitor is unavailable: %s", exc)
                self._stop_listener(listener)
                return False
            if not started:
                self._stop_listener(listener)
                return False
            with self._lock:
                self._seen_generation = self._generation
            return True

    def stop(self) -> None:
        with self._lifecycle_lock:
            with self._lock:
                listener = self._listener
                self._seen_generation = self._generation
            self._stop_listener(listener)

    def _stop_listener(self, listener: _ActivityListener | None) -> None:
        if listener is None:
            return
        if listener.alive:
            try:
                listener.stop()
            except Exception as exc:
                log.warning("Keyboard/mouse hot-switch monitor could not stop: %s", exc)
        if listener.alive:
            return
        with self._lock:
            if self._listener is listener:
                self._listener = None

    def poll(self) -> bool:
        with self._lock:
            if self._listener is None or self._seen_generation == self._generation:
                return False
            self._seen_generation = self._generation
            return True

    def _record_activity(self) -> None:
        with self._lock:
            self._generation += 1


_NEUTRAL_STATE = DualSenseInputState(
    left_x=128,
    left_y=128,
    right_x=128,
    right_y=128,
    left_trigger=0,
    right_trigger=0,
    dpad=DPad.NEUTRAL,
    buttons=frozenset(),
)


def controller_input_changed(
    baseline: DualSenseInputState,
    current: DualSenseInputState,
) -> bool:
    """Return whether a deliberate controller change should reclaim input."""
    if baseline.dpad != current.dpad:
        return True
    if baseline.buttons != current.buttons:
        return True
    if baseline.touchpad_regions != current.touchpad_regions:
        return True
    if baseline.touchpad_touched != current.touchpad_touched:
        return True
    if any(
        abs(getattr(current, field) - getattr(baseline, field))
        >= STICK_ACTIVITY_DELTA
        for field in ("left_x", "left_y", "right_x", "right_y")
    ):
        return True
    return any(
        abs(getattr(current, field) - getattr(baseline, field))
        >= TRIGGER_ACTIVITY_DELTA
        for field in ("left_trigger", "right_trigger")
    )


def controller_input_is_active(current: DualSenseInputState) -> bool:
    """Return whether a first report is deliberately away from neutral."""
    return controller_input_changed(_NEUTRAL_STATE, current)
