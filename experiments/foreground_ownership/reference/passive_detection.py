"""Handle-free DualSense presence detection.

The Windows runtime must be able to report that a controller exists while a
different game owns it.  hidapi enumeration is deliberately avoided there:
some Windows hidapi builds open each collection briefly to resolve metadata.
The Configuration Manager device tree can answer the narrower "is it present"
question without creating a HID file handle.
"""

from __future__ import annotations

import ctypes
import re
import sys
from ctypes import wintypes
from typing import Callable, cast


_CR_SUCCESS = 0x00000000
_CR_BUFFER_SMALL = 0x0000001A
_CM_GETIDLIST_FILTER_PRESENT = 0x00000100
_MAX_DEVICE_TREE_RETRIES = 3
_BLUETOOTH_DEVICE_NAME_SIZE = 248

_USB_VENDOR = re.compile(r"(?:^|[\\&#_])VID_054C(?:[\\&#_]|$)", re.IGNORECASE)
_BT_VENDOR = re.compile(r"(?:^|[\\&#_])VID&0002054C(?:[\\&#_]|$)", re.IGNORECASE)
_PRODUCT = re.compile(
    r"(?:^|[\\&#_])PID(?:_|&)(?:0CE6|0DF2)(?:[\\&#_]|$)",
    re.IGNORECASE,
)


class PassiveDetectionError(RuntimeError):
    """Windows PnP presence could not be read reliably."""


class _BluetoothAddress(ctypes.Union):
    _fields_ = (
        ("value", ctypes.c_ulonglong),
        ("bytes", ctypes.c_ubyte * 6),
    )


class _SystemTime(ctypes.Structure):
    _fields_ = tuple(
        (name, wintypes.WORD)
        for name in (
            "year",
            "month",
            "day_of_week",
            "day",
            "hour",
            "minute",
            "second",
            "milliseconds",
        )
    )


class _BluetoothDeviceInfo(ctypes.Structure):
    _fields_ = (
        ("size", wintypes.DWORD),
        ("address", _BluetoothAddress),
        ("class_of_device", wintypes.ULONG),
        ("connected", wintypes.BOOL),
        ("remembered", wintypes.BOOL),
        ("authenticated", wintypes.BOOL),
        ("last_seen", _SystemTime),
        ("last_used", _SystemTime),
        ("name", wintypes.WCHAR * _BLUETOOTH_DEVICE_NAME_SIZE),
    )


class _BluetoothDeviceSearchParams(ctypes.Structure):
    _fields_ = (
        ("size", wintypes.DWORD),
        ("return_authenticated", wintypes.BOOL),
        ("return_remembered", wintypes.BOOL),
        ("return_unknown", wintypes.BOOL),
        ("return_connected", wintypes.BOOL),
        ("issue_inquiry", wintypes.BOOL),
        ("timeout_multiplier", ctypes.c_ubyte),
        ("radio", wintypes.HANDLE),
    )


def is_dualsense_device_instance_id(value: object) -> bool:
    """Recognize USB and Bluetooth DualSense/Edge PnP instance IDs."""
    text = str(value or "").strip()
    return bool((_USB_VENDOR.search(text) or _BT_VENDOR.search(text)) and _PRODUCT.search(text))


def _split_multi_sz(value: str) -> tuple[str, ...]:
    return tuple(item for item in value.split("\0") if item)


def _windows_present_device_ids(
    *,
    library_loader: Callable[..., object] | None = None,
) -> tuple[str, ...]:
    """Return present Windows PnP instance IDs without opening HID handles."""
    if sys.platform != "win32":
        return ()
    loader = library_loader or ctypes.WinDLL
    cfgmgr32 = loader("cfgmgr32", use_last_error=True)
    get_size = cfgmgr32.CM_Get_Device_ID_List_SizeW
    get_size.argtypes = (
        ctypes.POINTER(wintypes.ULONG),
        wintypes.LPCWSTR,
        wintypes.ULONG,
    )
    get_size.restype = wintypes.ULONG
    get_list = cfgmgr32.CM_Get_Device_ID_ListW
    get_list.argtypes = (
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.ULONG,
        wintypes.ULONG,
    )
    get_list.restype = wintypes.ULONG

    for _attempt in range(_MAX_DEVICE_TREE_RETRIES):
        required = wintypes.ULONG()
        result = int(
            get_size(
                ctypes.byref(required),
                None,
                _CM_GETIDLIST_FILTER_PRESENT,
            )
        )
        if result != _CR_SUCCESS:
            raise PassiveDetectionError(
                f"CM_Get_Device_ID_List_SizeW failed with CONFIGRET 0x{result:08x}"
            )
        # A MULTI_SZ always needs its final terminator. Keep one extra WCHAR so
        # a concurrently changing device tree cannot expose an unterminated
        # Python buffer even when Configuration Manager reports BUFFER_SMALL.
        capacity = max(2, int(required.value) + 1)
        buffer = ctypes.create_unicode_buffer(capacity)
        result = int(
            get_list(
                None,
                buffer,
                capacity,
                _CM_GETIDLIST_FILTER_PRESENT,
            )
        )
        if result == _CR_SUCCESS:
            return _split_multi_sz(buffer[:capacity])
        if result != _CR_BUFFER_SMALL:
            raise PassiveDetectionError(
                f"CM_Get_Device_ID_ListW failed with CONFIGRET 0x{result:08x}"
            )
    raise PassiveDetectionError("Windows device tree kept changing during presence detection")


def windows_present_dualsense_ids(
    *,
    library_loader: Callable[..., object] | None = None,
) -> tuple[str, ...]:
    """Return present DualSense PnP IDs; callers should expose only a count."""
    return tuple(
        device_id
        for device_id in _windows_present_device_ids(library_loader=library_loader)
        if is_dualsense_device_instance_id(device_id)
    )


def _bluetooth_mac_from_instance_id(device_id: str) -> str:
    upper = str(device_id or "").upper()
    matches = re.findall(r"(?:^|[_&\\])([0-9A-F]{12})(?=[_&\\]|$)", upper)
    return matches[-1] if matches else ""


def _windows_connected_bluetooth_macs(
    *,
    library_loader: Callable[..., object] | None = None,
) -> frozenset[str]:
    """Return classic Bluetooth addresses that Windows reports connected.

    Paired BTHENUM nodes remain ``present`` after a controller powers off, so
    Configuration Manager alone cannot distinguish a live Bluetooth pad from
    a remembered one. The Bluetooth API exposes that narrower connection bit
    without opening the controller's HID interface.
    """
    if sys.platform != "win32":
        return frozenset()
    loader = library_loader or ctypes.WinDLL
    bluetooth = loader("bthprops.cpl", use_last_error=True)
    find_first = bluetooth.BluetoothFindFirstDevice
    find_first.argtypes = (
        ctypes.POINTER(_BluetoothDeviceSearchParams),
        ctypes.POINTER(_BluetoothDeviceInfo),
    )
    find_first.restype = wintypes.HANDLE
    find_next = bluetooth.BluetoothFindNextDevice
    find_next.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_BluetoothDeviceInfo),
    )
    find_next.restype = wintypes.BOOL
    find_close = bluetooth.BluetoothFindDeviceClose
    find_close.argtypes = (wintypes.HANDLE,)
    find_close.restype = wintypes.BOOL

    search = _BluetoothDeviceSearchParams()
    search.size = ctypes.sizeof(search)
    search.return_connected = True
    info = _BluetoothDeviceInfo()
    info.size = ctypes.sizeof(info)
    handle = find_first(ctypes.byref(search), ctypes.byref(info))
    if not handle:
        return frozenset()
    connected: set[str] = set()
    try:
        while True:
            if info.connected:
                connected.add(f"{int(info.address.value):012X}")
            info = _BluetoothDeviceInfo()
            info.size = ctypes.sizeof(info)
            if not find_next(handle, ctypes.byref(info)):
                break
    finally:
        find_close(handle)
    return frozenset(connected)


def windows_present_dualsense_count() -> int:
    """Return a conservative physical-controller count from matching PnP nodes.

    One DualSense can expose multiple HID collections. Bluetooth instance IDs
    contain the paired MAC, while USB often exposes MI_03 plus collection
    children. The count is presentation-only; it never influences ownership.
    """
    device_ids = windows_present_dualsense_ids()
    if not device_ids:
        return 0
    connected_bluetooth = _windows_connected_bluetooth_macs()
    bluetooth_macs: set[str] = set()
    usb_roots: set[str] = set()
    for device_id in device_ids:
        upper = device_id.upper()
        if "VID&0002054C" in upper:
            mac = _bluetooth_mac_from_instance_id(device_id)
            if mac and mac in connected_bluetooth:
                bluetooth_macs.add(mac)
            continue
        root = re.sub(r"&COL[0-9A-F]{2}(?=\\|$)", "", upper)
        usb_roots.add(root)
    # A controller that is paired over Bluetooth and currently cabled can
    # expose both transports. Without opening feature report 0x09 there is no
    # reliable cross-transport identity, so report a conservative lower bound
    # instead of presenting one physical pad twice.
    if bluetooth_macs and usb_roots:
        return max(len(bluetooth_macs), len(usb_roots))
    return len(bluetooth_macs or usb_roots)


def passive_dualsense_count(
    non_windows_enumerator: Callable[[], list[dict]] | None = None,
) -> int:
    """Count visible controller records without touching a Windows HID handle."""
    if sys.platform == "win32":
        return windows_present_dualsense_count()
    enumerator = non_windows_enumerator
    if enumerator is None:
        return 0
    enumerator = cast(Callable[[], list[dict]], enumerator)
    return len(enumerator())


def passive_dualsense_records(
    non_windows_enumerator: Callable[[], list[dict]] | None = None,
) -> list[dict]:
    """Return handle-free records suitable for UI discovery.

    Windows intentionally returns one aggregate informational row. A physical
    controller may expose several matching PnP nodes, and none of those records
    may be passed to hidapi or used for an identify pulse. The runtime I/O owner
    resolves path, transport and serial only after the Forza foreground gate
    opens.
    """
    if sys.platform == "win32":
        count = windows_present_dualsense_count()
        return [{"passive": True, "pnp_record_count": count}] if count else []
    enumerator = non_windows_enumerator
    if enumerator is None:
        return []
    enumerator = cast(Callable[[], list[dict]], enumerator)
    return [dict(record) for record in enumerator()]
