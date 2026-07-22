import modules as modules_package

from modules import make_backend
from modules.config.settings import Settings


def test_native_backend_uses_live_body_haptics_audio_gate(monkeypatch):
    captured = {}
    endpoint_checks = []

    class Controller:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        modules_package,
        "is_dualsense_usb_audio_endpoint_ready",
        lambda: endpoint_checks.append(True) or False,
    )
    monkeypatch.setattr(modules_package.dualsense, "DualSense", Controller)
    settings = Settings(enable_body_haptics=True)

    make_backend(settings, False)
    readiness = captured["usb_handover_ready"]

    assert readiness() is False
    assert endpoint_checks == [True]
    settings.enable_body_haptics = False
    assert readiness() is True
    assert endpoint_checks == [True]
