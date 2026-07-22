import pytest

import main as app_main
from modules.config.settings import Settings


@pytest.mark.parametrize("failure", ["open", "sync"])
def test_headless_startup_failure_still_closes_controller_and_xinput(
    monkeypatch,
    failure,
):
    events = []

    class Controller:
        def open(self):
            events.append("open")
            if failure == "open":
                raise RuntimeError("controller failed")

        def close(self):
            events.append("close")

    class XInput:
        def __init__(self, _settings):
            pass

        def sync(self, _controller):
            events.append("sync")
            if failure == "sync":
                raise RuntimeError("xinput failed")

        def stop(self):
            events.append("stop")

    monkeypatch.setattr(app_main, "make_backend", lambda *_args: Controller())
    monkeypatch.setattr(app_main, "XInputBridgeService", XInput)

    with pytest.raises(RuntimeError):
        app_main.run(Settings())

    assert events[-2:] == ["stop", "close"]


def test_headless_health_boundary_follows_controller_xinput_and_udp_initialization(
    monkeypatch,
):
    events = []

    class Controller:
        def open(self):
            events.append("controller")

        def close(self):
            events.append("controller-close")

    class XInput:
        def __init__(self, _settings):
            pass

        def sync(self, _controller):
            events.append("xinput")

        def stop(self):
            events.append("xinput-stop")

    class Listener:
        def __init__(self, *_args):
            pass

        def __enter__(self):
            events.append("udp")
            return self

        def __exit__(self, *_args):
            events.append("udp-close")

    monkeypatch.setattr(app_main, "make_backend", lambda *_args: Controller())
    monkeypatch.setattr(app_main, "XInputBridgeService", XInput)
    monkeypatch.setattr(app_main.forzahorizon, "UDPListener", Listener)
    monkeypatch.setattr(app_main.loop, "run", lambda *_args: events.append("loop"))

    app_main.run(Settings(), on_ready=lambda: events.append("healthy"))

    assert events[:5] == ["controller", "xinput", "udp", "healthy", "loop"]
    assert events[-3:] == ["udp-close", "xinput-stop", "controller-close"]


@pytest.mark.parametrize(
    ("runner_name", "module_name", "class_name"),
    [
        ("run_gui", "modules.gui", "TriggerGUI"),
        ("run_tui", "modules.tui", "TriggerTUI"),
    ],
)
def test_interactive_runner_delegates_health_callback_to_app_lifecycle(
    monkeypatch,
    runner_name,
    module_name,
    class_name,
):
    module = __import__(module_name, fromlist=[class_name])
    events = []

    def callback():
        events.append("healthy")

    class FakeApp:
        def __init__(self, settings, *, on_ready=None):
            events.append(("construct", settings, on_ready))

        def run(self):
            events.append("run")

    monkeypatch.setattr(module, class_name, FakeApp)
    settings = Settings()

    getattr(app_main, runner_name)(settings, on_ready=callback)

    assert events == [("construct", settings, callback), "run"]


def test_interactive_health_callbacks_are_one_shot():
    from modules.gui.main import TriggerGUI
    from modules.tui.main import TriggerTUI

    for app_type in (TriggerGUI, TriggerTUI):
        events = []
        app = app_type.__new__(app_type)
        app._on_ready = lambda: events.append("healthy")

        app_type._notify_ready(app)
        app_type._notify_ready(app)

        assert events == ["healthy"]
