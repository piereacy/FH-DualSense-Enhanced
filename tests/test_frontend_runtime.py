import asyncio
import logging
import queue
import threading
from types import SimpleNamespace

import pytest

from modules.config import preferences
from modules.config.settings import Settings
from modules.gui import main as gui
from modules.gui.settings_tab import SettingsTab as GUISettingsTab
from modules.haptics.trigger_pulse import TriggerPulse
from modules.tui import main as tui
from modules.tui.settings_tab import SettingsTab as TUISettingsTab

FRONTENDS = ((gui, gui.TriggerGUI), (tui, tui.TriggerTUI))


class _Thread:
    def __init__(self, **kwargs):
        self.started = False
        self.args = kwargs.get("args", ())

    def start(self):
        self.started = True

    def join(self, timeout=None):
        pass

    def is_alive(self):
        return False


def _app(settings):
    return SimpleNamespace(
        settings=settings, _tearing_down=False, _stop=threading.Event(),
        _backend_restart_lock=threading.Lock(), _thread=None,
        _backend_generation=0, _usb_audio=None,
        _listener=None, _listener_cm=None, _ds=None,
        _backend_error="", _udp_error="",
        _haptics_lab=SimpleNamespace(stop=lambda _reason: None),
        _run_loop=lambda _generation: None, _notify_ready=lambda: None,
        _refresh_status=lambda: None,
        overview_tab=SimpleNamespace(refresh=lambda: None),
        query_one=lambda *_args: SimpleNamespace(update=lambda _text: None),
    )


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_deferred_ui_startup_keeps_cli_overrides(module, frontend, monkeypatch):
    settings = Settings(udp_host="127.0.0.2", udp_port=5400)
    app = _app(settings)
    seen = []
    backend = SimpleNamespace(open=lambda: None)
    app._xinput_service = SimpleNamespace(
        prepare_controller_access=lambda _backend: None,
        sync=lambda _backend: None,
    )

    class Listener:
        def __init__(self, host, port, *_args):
            seen.append((host, port))

        def __enter__(self):
            return self

    monkeypatch.setattr(module, "make_backend", lambda *_args: backend)
    monkeypatch.setattr(module.forzahorizon, "UDPListener", Listener)
    monkeypatch.setattr(module.threading, "Thread", _Thread)
    monkeypatch.setattr(
        "modules.config.preferences.load",
        lambda _settings: pytest.fail("startup must keep main's loaded settings"),
    )

    frontend._start_backend(app)

    assert seen == [("127.0.0.2", 5400)]
    assert app._thread.started
    assert app._thread.args == (1,)


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_restart_aborts_before_creating_second_controller_owner(module, frontend, monkeypatch):
    app = _app(Settings())
    old_backend = SimpleNamespace(close=lambda: False)
    app._ds = old_backend
    app._thread = _Thread()
    app._xinput_service = SimpleNamespace(stop=lambda: None)
    monkeypatch.setattr(
        module, "make_backend",
        lambda *_args: pytest.fail("old HID worker still owns the controller"),
    )

    frontend._restart_backend(app)

    assert app._ds is old_backend
    assert app._stop.is_set()
    assert "I/O worker has not stopped" in app._backend_error


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_factory_restart_applies_backend_platform_and_udp_settings(module, frontend, tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "PATH", tmp_path / "preferences.json")
    settings = Settings(udp_port=5400, use_dsx=True, preferred_forza_platform="xbox_app")
    assert preferences.save(settings)
    assert preferences.restore_factory(settings)
    app = _app(settings)
    events = []
    app._ds = SimpleNamespace(close=lambda: events.append("controller-close"))
    app._listener_cm = SimpleNamespace(
        __exit__=lambda *_args: events.append("listener-close"),
    )
    app._listener = app._listener_cm
    app._thread = _Thread()
    app._xinput_service = SimpleNamespace(
        stop=lambda: events.append("bridge-stop"),
        prepare_controller_access=lambda _backend: None,
        sync=lambda _backend: events.append(("bridge-sync", settings.preferred_forza_platform)),
    )
    backend = SimpleNamespace(open=lambda: events.append("controller-open"))

    def make_backend(current, pulse):
        events.append(("backend", current.use_dsx, pulse))
        return backend

    class Listener:
        def __init__(self, host, port, *_args):
            events.append(("listener-open", host, port))

        def __enter__(self):
            return self

    monkeypatch.setattr(module, "make_backend", make_backend)
    monkeypatch.setattr(module.forzahorizon, "UDPListener", Listener)
    monkeypatch.setattr(module.threading, "Thread", _Thread)

    frontend._restart_backend(app, restart_listener=True)

    assert events.index("listener-close") < events.index(("listener-open", settings.udp_host, 5300))
    assert ("backend", False, False) in events
    assert ("bridge-sync", "steam") in events
    assert app._ds is backend
    assert app._thread.started
    assert not app._backend_error


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_disabled_trigger_master_blocks_ui_pulses_even_if_worker_was_queued(
    module, frontend, monkeypatch
):
    settings = Settings(enable_trigger_feedback=False)
    backend = SimpleNamespace(connected=True, set=lambda *_args: pytest.fail("trigger output disabled"))
    pulse = TriggerPulse()
    app = SimpleNamespace(settings=settings, _ds=backend, _trigger_pulse=pulse)
    monkeypatch.setattr(
        module.threading, "Thread", lambda **_kwargs: pytest.fail("must not start a pulse"),
    )

    frontend.haptic(app, True)
    assert pulse.sample(now=0) is None


def test_gui_worker_shutdown_posts_callback_without_touching_tk(monkeypatch):
    app = _app(Settings())
    app._usb_audio = None
    app._ui_queue = queue.SimpleQueue()
    app.root = SimpleNamespace(after=lambda *_args: pytest.fail("worker must not call Tk"))
    closed = []
    app._on_close = lambda: closed.append(threading.get_ident())
    app._on_backend_stopped = lambda generation: gui.TriggerGUI._on_backend_stopped(app, generation)
    app.post_ui = lambda callback: gui.TriggerGUI.post_ui(app, callback)
    monkeypatch.setattr(gui.loop, "run", lambda *_args, **_kwargs: None)
    worker = threading.Thread(target=lambda: gui.TriggerGUI._run_loop(app, 0))
    worker.start()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert closed == []
    gui.TriggerGUI._drain_ui_callbacks(app)
    assert closed == [threading.get_ident()]


@pytest.mark.parametrize("module,frontend", FRONTENDS)
@pytest.mark.parametrize("crashed", [False, True])
def test_queued_old_loop_exit_cannot_close_restarted_session(module, frontend, crashed, monkeypatch):
    app = _app(Settings())
    app._backend_generation = 1
    app._listener = object()
    queued = []
    closed = []
    app._on_close = lambda: closed.append("gui")
    app.request_close = lambda: closed.append("tui")
    app._on_backend_stopped = lambda generation: gui.TriggerGUI._on_backend_stopped(app, generation)
    app.post_ui = queued.append
    app.post_message = queued.append
    app._xinput_service = SimpleNamespace(
        stop=lambda: None, prepare_controller_access=lambda _backend: None,
        sync=lambda _backend: None,
    )

    def run(*_args, **_kwargs):
        if crashed:
            raise RuntimeError("test loop failure")

    monkeypatch.setattr(module.loop, "run", run)
    frontend._run_loop(app, 1)
    assert len(queued) == 1
    assert closed == []

    monkeypatch.setattr(module, "make_backend", lambda *_args: SimpleNamespace(open=lambda: None))
    monkeypatch.setattr(module.threading, "Thread", _Thread)
    frontend._restart_backend(app)
    assert app._backend_generation == 2
    assert app._thread.args == (2,)
    assert not app._stop.is_set()

    if module is gui:
        queued.pop(0)()
    else:
        frontend.on_backend_stopped(app, queued.pop(0))
    assert closed == []

    frontend._run_loop(app, 2)
    if module is gui:
        queued.pop(0)()
    else:
        frontend.on_backend_stopped(app, queued.pop(0))
    assert closed == ["gui" if module is gui else "tui"]


def test_tui_worker_logging_posts_without_waiting_for_ui_thread():
    messages = []
    app = SimpleNamespace(
        _tearing_down=False, _thread_id=threading.get_ident(),
        post_message=lambda message: messages.append(message),
        call_from_thread=lambda *_args: pytest.fail("logging must not wait for UI"),
    )
    handler = tui._LogHandler(app)
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "hello", (), None)
    worker = threading.Thread(target=lambda: handler.emit(record))
    worker.start()
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert len(messages) == 1
    assert messages[0].handler_name == "on_runtime_log"
    assert messages[0].text == "hello"


@pytest.mark.parametrize("frontend", ["gui", "tui"])
@pytest.mark.parametrize("attr,raw", [("udp_port", "inf"), ("udp_port", "1e309"), ("reconnect_interval_s", "nan")])
def test_nonfinite_numeric_entry_keeps_previous_settings(frontend, attr, raw, monkeypatch):
    settings = Settings()
    original = getattr(settings, attr)
    app = SimpleNamespace(_refreshing=False)
    monkeypatch.setattr(preferences, "save", lambda *_args: pytest.fail("invalid input must not save"))
    tab = SimpleNamespace(settings=settings, app=app, _push_live=lambda *_args: pytest.fail("invalid input must not reach backend"))
    if frontend == "gui":
        replacements = []
        entry = SimpleNamespace(
            get=lambda: raw, delete=lambda *_args: None,
            insert=lambda _index, value: replacements.append(value),
        )
        tab._entries = {attr: entry}
        GUISettingsTab._on_entry_change(tab, attr, strict=True)
        assert replacements
    else:
        entry = SimpleNamespace(id=f"set-{attr}", value=raw)
        TUISettingsTab._commit(tab, entry, strict=True)
        assert entry.value != raw
    assert getattr(settings, attr) == original


def test_tui_factory_reset_requests_full_runtime_restart(monkeypatch):
    threads = []

    class Thread:
        def __init__(self, **kwargs):
            threads.append(kwargs)

        def start(self):
            pass

    app = SimpleNamespace(
        mark_default_saved=lambda: None, refresh_setting_widgets=lambda: None,
        _restart_backend=lambda **_kwargs: None,
    )
    tab = SimpleNamespace(settings=Settings(), app=app, _reset_armed=True)
    monkeypatch.setattr(preferences, "reset", lambda _settings: True)
    monkeypatch.setattr("modules.tui.settings_tab.threading.Thread", Thread)

    asyncio.run(TUISettingsTab.on_button_pressed(tab, SimpleNamespace(
        button=SimpleNamespace(id="reset-settings", label=""),
    )))

    assert threads[0]["target"] == app._restart_backend
    assert threads[0]["kwargs"] == {"restart_listener": True}


def test_tui_controller_serial_is_normalized_and_not_used_as_widget_id():
    from modules.tui.system_tab import SystemTab
    app = SimpleNamespace(
        settings=Settings(controller_lock_serial="aa:bb:cc:dd:ee:ff"),
        _devices=[
            {"serial_number": "AA:BB:CC:DD:EE:FF", "bus_type": 2},
            {"serial_number": "aabbccddeeff", "bus_type": 1},
        ],
        _attached_serial=lambda: "aa:bb:cc:dd:ee:ff",
    )
    buttons = SystemTab._build_controller_buttons(app)
    assert len(buttons) == 2
    assert buttons[1].id == "ctrl-device-0"
    assert buttons[1].value
    assert len(app._controller_choices) == 1
