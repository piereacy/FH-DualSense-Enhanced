from __future__ import annotations

import importlib
import sys
from typing import Any


RENDER_ENDPOINTS_KEY = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
)
DEVICE_STATE_ACTIVE = 0x1
DEVICE_INSTANCE_PROPERTY = "{b3f8fa53-0004-438e-9003-51a46e139bfc},2"
DEVICE_DESCRIPTION_PROPERTY = "{b3f8fa53-0004-438e-9003-51a46e139bfc},6"
DUALSENSE_PRODUCT_IDS = ("PID_0CE6", "PID_0DF2")


def _endpoint_matches(registry: Any, endpoint: Any) -> bool:
    try:
        state = int(registry.QueryValueEx(endpoint, "DeviceState")[0])
    except (OSError, TypeError, ValueError):
        return False
    if state != DEVICE_STATE_ACTIVE:
        return False

    try:
        with registry.OpenKey(
            endpoint,
            "Properties",
            0,
            getattr(registry, "KEY_READ", 0),
        ) as properties:
            instance = str(
                registry.QueryValueEx(properties, DEVICE_INSTANCE_PROPERTY)[0]
            ).upper()
            try:
                description = str(
                    registry.QueryValueEx(
                        properties,
                        DEVICE_DESCRIPTION_PROPERTY,
                    )[0]
                ).upper()
            except OSError:
                description = ""
    except OSError:
        return False

    hardware_match = (
        "VID_054C" in instance
        and any(product_id in instance for product_id in DUALSENSE_PRODUCT_IDS)
        and "MI_00" in instance
    )
    name_match = not description or "DUALSENSE" in description
    return hardware_match and name_match


def is_dualsense_usb_audio_endpoint_ready(
    *,
    platform: str | None = None,
    registry_module: Any = None,
) -> bool:
    """Return whether Windows exposes an active DualSense USB render endpoint.

    This probe intentionally avoids sounddevice and PortAudio.  On non-Windows
    platforms the Windows-only gate is disabled and therefore returns True.
    Registry failures are treated as not ready so an active Bluetooth session
    is retained instead of committing a half-ready USB handover.
    """
    platform = platform or sys.platform
    if not platform.startswith("win"):
        return True

    registry = registry_module
    if registry is None:
        try:
            registry = importlib.import_module("winreg")
        except ImportError:
            return False

    try:
        with registry.OpenKey(
            registry.HKEY_LOCAL_MACHINE,
            RENDER_ENDPOINTS_KEY,
            0,
            getattr(registry, "KEY_READ", 0),
        ) as render_endpoints:
            index = 0
            while True:
                try:
                    endpoint_name = registry.EnumKey(render_endpoints, index)
                except OSError:
                    break
                index += 1
                try:
                    with registry.OpenKey(
                        render_endpoints,
                        endpoint_name,
                        0,
                        getattr(registry, "KEY_READ", 0),
                    ) as endpoint:
                        if _endpoint_matches(registry, endpoint):
                            return True
                except OSError:
                    continue
    except OSError:
        return False
    return False
