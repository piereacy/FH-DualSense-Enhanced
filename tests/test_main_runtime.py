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


def test_gui_udp_conflict_is_healthy_once_the_error_ui_is_usable(monkeypatch):
    from modules.gui import main as gui_main

    events = []

    class Controller:
        def open(self):
            events.append("controller")

    class XInput:
        def sync(self, _controller):
            events.append("xinput")

    class Listener:
        def __init__(self, *_args):
            pass

        def __enter__(self):
            raise OSError("port occupied")

    app = gui_main.TriggerGUI.__new__(gui_main.TriggerGUI)
    app.settings = Settings()
    app._ds = None
    app._xinput_service = XInput()
    app._backend_error = ""
    app._udp_error = ""
    app._listener_cm = None
    app._listener = None
    app._thread = None
    app._on_ready = lambda: events.append("healthy")
    app._refresh_status = lambda: events.append("status")
    app.overview_tab = type("Overview", (), {"refresh": lambda _self: events.append("overview")})()
    app._perform_quit = lambda: pytest.fail("a usable UDP error must not roll back")
    monkeypatch.setattr(gui_main.preferences, "load", lambda _settings: None)
    monkeypatch.setattr(gui_main, "make_backend", lambda *_args: Controller())
    monkeypatch.setattr(gui_main.forzahorizon, "UDPListener", Listener)

    gui_main.TriggerGUI._start_backend(app)

    assert events[:2] == ["controller", "xinput"]
    assert events.count("healthy") == 1
    assert app._udp_error == "port occupied"


def test_tui_udp_conflict_is_healthy_but_controller_failure_is_not(monkeypatch):
    from modules.tui import main as tui_main

    events = []

    class Controller:
        def __init__(self, *, fail=False):
            self.fail = fail

        def open(self):
            events.append("controller")
            if self.fail:
                raise OSError("controller unavailable")

    class XInput:
        def sync(self, _controller):
            events.append("xinput")

    class Listener:
        def __init__(self, *_args):
            pass

        def __enter__(self):
            raise OSError("port occupied")

    class Status:
        def update(self, message):
            events.append(("status", str(message)))

    def make_app(controller):
        app = tui_main.TriggerTUI.__new__(tui_main.TriggerTUI)
        app.settings = Settings()
        app._ds = None
        app._xinput_service = XInput()
        app._backend_error = ""
        app._udp_error = ""
        app._listener_cm = None
        app._listener = None
        app._thread = None
        app._on_ready = lambda: events.append("healthy")
        app.query_one = lambda *_args, **_kwargs: Status()
        app.exit = lambda **_kwargs: pytest.fail("health callback must not fail")
        monkeypatch.setattr(tui_main, "make_backend", lambda *_args: controller)
        return app

    monkeypatch.setattr(tui_main.preferences, "load", lambda _settings: None)
    monkeypatch.setattr(tui_main.forzahorizon, "UDPListener", Listener)
    tui_main.TriggerTUI._start_backend(make_app(Controller()))
    assert events.count("healthy") == 1

    events.clear()
    tui_main.TriggerTUI._start_backend(make_app(Controller(fail=True)))
    assert "healthy" not in events
