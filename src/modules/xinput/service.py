"""Application-level platform switch for the optional XInput bridge."""
from __future__ import annotations

import threading
from typing import Callable

from .bridge import BridgeSnapshot, BridgeStatus, XInputBridge
from .driver import InstallResult, InstallStatus, install_and_probe
from .vigem_client import is_supported_platform


STEAM_PLATFORM = "steam"
XBOX_APP_PLATFORM = "xbox_app"
FORZA_PLATFORMS = (STEAM_PLATFORM, XBOX_APP_PLATFORM)


def normalize_forza_platform(value: object) -> str:
    normalized = str(value).strip().casefold()
    return normalized if normalized in FORZA_PLATFORMS else STEAM_PLATFORM


class XInputBridgeService:
    """Attach the bridge only in Xbox App mode and only to direct HID backends."""

    def __init__(
        self,
        settings,
        *,
        bridge: XInputBridge | None = None,
        platform_supported: Callable[[], bool] = is_supported_platform,
    ):
        self.settings = settings
        self._bridge = bridge or XInputBridge()
        self._platform_supported = platform_supported
        self._lock = threading.Lock()
        self._backend = None
        self._override: BridgeSnapshot | None = None

    @property
    def platform(self) -> str:
        return normalize_forza_platform(
            getattr(self.settings, "preferred_forza_platform", STEAM_PLATFORM)
        )

    def sync(self, backend) -> None:
        self._detach_consumer()
        self._bridge.stop()
        with self._lock:
            self._backend = backend
            self._override = (
                BridgeSnapshot(status=BridgeStatus.DISABLED)
                if self.platform != XBOX_APP_PLATFORM
                else None
            )
        if self.platform != XBOX_APP_PLATFORM:
            return
        if not self._platform_supported():
            with self._lock:
                self._override = BridgeSnapshot(
                    status=BridgeStatus.DISABLED,
                    last_error="Xbox App input bridge requires Windows x64",
                )
            return
        setter = getattr(backend, "set_input_consumer", None)
        if not callable(setter):
            with self._lock:
                self._override = BridgeSnapshot(
                    status=BridgeStatus.ERROR,
                    last_error="Xbox App input bridge requires direct HID mode; disable DSX",
                )
            return
        self._bridge.start()
        setter(self._bridge.publish_latest)

    def retry(self) -> None:
        with self._lock:
            backend = self._backend
        self.sync(backend)

    def install_driver(
        self,
        installer: Callable[[], InstallResult] = install_and_probe,
    ) -> InstallResult:
        """Run the already-confirmed installer flow; caller owns the UI prompt."""
        with self._lock:
            backend = self._backend
        self._detach_consumer()
        self._bridge.stop()
        with self._lock:
            self._backend = backend
            self._override = BridgeSnapshot(status=BridgeStatus.INSTALLING)
        result = installer()
        if result.status is InstallStatus.SUCCESS:
            self.sync(backend)
            return result
        status = {
            InstallStatus.CANCELLED: BridgeStatus.DRIVER_MISSING,
            InstallStatus.RESTART_REQUIRED: BridgeStatus.RESTART_REQUIRED,
            InstallStatus.FAILED: BridgeStatus.ERROR,
        }[result.status]
        with self._lock:
            self._backend = backend
            self._override = BridgeSnapshot(
                status=status,
                last_error=result.error,
            )
        return result

    def snapshot(self) -> BridgeSnapshot:
        with self._lock:
            override = self._override
        return override or self._bridge.snapshot()

    def stop(self) -> None:
        self._detach_consumer()
        self._bridge.stop()
        with self._lock:
            self._backend = None
            self._override = None

    def _detach_consumer(self) -> None:
        with self._lock:
            backend = self._backend
            self._backend = None
        setter = getattr(backend, "set_input_consumer", None)
        if callable(setter):
            setter(None)
