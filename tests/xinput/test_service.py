from modules.config.settings import Settings
from modules.xinput.bridge import BridgeSnapshot, BridgeStatus
from modules.xinput.driver import InstallResult, InstallStatus
from modules.xinput.mapping import DEFAULT_BUTTON_MAPPING
from modules.xinput.service import (
    STEAM_PLATFORM,
    XBOX_APP_PLATFORM,
    XInputBridgeService,
    custom_xinput_mapping_available,
    normalize_forza_platform,
)


def test_custom_mapping_is_available_only_for_the_xbox_app_platform():
    assert custom_xinput_mapping_available(XBOX_APP_PLATFORM) is True
    assert custom_xinput_mapping_available(" XBOX_APP ") is True
    assert custom_xinput_mapping_available(STEAM_PLATFORM) is False
    assert custom_xinput_mapping_available("future-platform") is False


class _Bridge:
    def __init__(self):
        self.calls = []
        self.mappings = []
        self._snapshot = BridgeSnapshot(status=BridgeStatus.WAITING_CONTROLLER)

    def set_button_mapping(self, mapping):
        self.mappings.append(mapping)

    def start(self):
        self.calls.append("start")

    def stop(self):
        self.calls.append("stop")

    def publish_latest(self, _state, _received_at):
        pass

    def snapshot(self):
        return self._snapshot


class _Backend:
    def __init__(self):
        self.consumers = []

    def set_input_consumer(self, consumer):
        self.consumers.append(consumer)


def test_unknown_platform_normalizes_to_safe_steam_default():
    assert normalize_forza_platform("XBOX_APP") == XBOX_APP_PLATFORM
    assert normalize_forza_platform("future-store") == STEAM_PLATFORM


def test_steam_mode_never_starts_bridge_or_attaches_input_consumer():
    settings = Settings()
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        platform_supported=lambda: True,
    )

    service.sync(backend)

    assert bridge.calls == ["stop"]
    assert backend.consumers == []
    assert service.snapshot().status is BridgeStatus.DISABLED


def test_xbox_app_mode_starts_bridge_and_attaches_latest_publisher():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        platform_supported=lambda: True,
    )

    service.sync(backend)

    assert bridge.calls == ["stop", "start"]
    assert backend.consumers == [bridge.publish_latest]
    assert bridge.mappings[-1] == DEFAULT_BUTTON_MAPPING


def test_custom_mapping_refresh_does_not_restart_the_bridge():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(
        settings,
        bridge=bridge,
        platform_supported=lambda: True,
    )
    service.sync(backend)
    calls_before = list(bridge.calls)

    settings.enable_custom_xinput_mapping = True
    settings.xinput_mapping_cross = "y"
    mapping = service.refresh_button_mapping()

    assert bridge.calls == calls_before
    assert mapping.target_for("cross") == "y"
    assert bridge.mappings[-1] == mapping


def test_switching_back_to_steam_detaches_before_bridge_stops():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(settings, bridge=bridge, platform_supported=lambda: True)
    service.sync(backend)
    settings.preferred_forza_platform = STEAM_PLATFORM

    service.sync(backend)

    assert backend.consumers[-1] is None
    assert bridge.calls[-1] == "stop"


def test_dsx_backend_is_reported_as_incompatible_without_starting_bridge():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    service = XInputBridgeService(settings, bridge=bridge, platform_supported=lambda: True)

    service.sync(object())

    snapshot = service.snapshot()
    assert snapshot.status is BridgeStatus.ERROR
    assert "disable DSX" in snapshot.last_error
    assert "start" not in bridge.calls


def test_non_windows_x64_platform_stays_disabled():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    service = XInputBridgeService(settings, bridge=bridge, platform_supported=lambda: False)

    service.sync(_Backend())

    assert service.snapshot().status is BridgeStatus.DISABLED
    assert "Windows x64" in service.snapshot().last_error
    assert "start" not in bridge.calls


def test_stop_detaches_consumer_and_is_idempotent():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(settings, bridge=bridge, platform_supported=lambda: True)
    service.sync(backend)

    service.stop()
    service.stop()

    assert backend.consumers[-1] is None


def test_confirmed_driver_install_exposes_installing_then_restarts_bridge():
    settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
    bridge = _Bridge()
    backend = _Backend()
    service = XInputBridgeService(settings, bridge=bridge, platform_supported=lambda: True)
    service.sync(backend)
    observed = []

    result = service.install_driver(
        lambda: observed.append(service.snapshot().status)
        or InstallResult(InstallStatus.SUCCESS, exit_code=0)
    )

    assert observed == [BridgeStatus.INSTALLING]
    assert result.status is InstallStatus.SUCCESS
    assert bridge.calls[-1] == "start"
    assert backend.consumers[-1] == bridge.publish_latest


def test_cancelled_and_restart_required_installs_keep_explicit_status():
    for install_status, bridge_status in (
        (InstallStatus.CANCELLED, BridgeStatus.DRIVER_MISSING),
        (InstallStatus.RESTART_REQUIRED, BridgeStatus.RESTART_REQUIRED),
        (InstallStatus.FAILED, BridgeStatus.ERROR),
    ):
        settings = Settings(preferred_forza_platform=XBOX_APP_PLATFORM)
        service = XInputBridgeService(
            settings,
            bridge=_Bridge(),
            platform_supported=lambda: True,
        )
        service.sync(_Backend())

        service.install_driver(
            lambda status=install_status: InstallResult(status, error="synthetic result")
        )

        assert service.snapshot().status is bridge_status
        assert service.snapshot().last_error == "synthetic result"
