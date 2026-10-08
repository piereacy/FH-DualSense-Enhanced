import threading
from types import SimpleNamespace

import pytest

from modules.config.settings import Settings
from modules.gui import main as gui
from modules.tui import main as tui

FRONTENDS = ((gui, gui.TriggerGUI), (tui, tui.TriggerTUI))
REAL_THREAD = threading.Thread


class Worker:
    def __init__(self, *, alive=False, **kwargs):
        self.alive = alive
        self.started = False
        self.args = kwargs.get("args", ())

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        pass

    def start(self):
        self.started = True
        self.alive = True


def close_app(module, frontend, monkeypatch, *, prompt=True):
    events = []
    dialogs = []
    app = SimpleNamespace(
        settings=Settings(), _backend_generation=4, _tearing_down=False,
        _stop=threading.Event(), _backend_restart_lock=threading.Lock(),
        _thread=Worker(), _ds=object(), _listener=object(), _backend_error="",
        _usb_audio=None, root=None, _close_dialog=None, _close_prompt_open=False,
        _pending_before_exit=None,
        _loop_resume_pending=False, _resume_helpers=[],
        _profile_session=SimpleNamespace(needs_named_save=lambda _s: prompt),
        _show_window=lambda: None, _run_loop=lambda _generation: None,
        report_save_failure=lambda: events.append("save failed"),
        _perform_quit=lambda: events.append("exit"),
        exit=lambda: events.append("exit"),
        toast=lambda *_args: events.append("update failed"),
        notify=lambda *_args, **_kwargs: events.append("update failed"),
    )
    app._resume_stopped_loop = lambda: frontend._resume_stopped_loop(app)
    app._resume_stopped_loop_worker = lambda generation: frontend._resume_stopped_loop_worker(app, generation)
    app._finish_close = lambda action=None: frontend._finish_close(app, action)
    app._on_close = lambda: frontend.request_close(app, "backend")
    app.request_close = lambda: frontend.request_close(app)
    app._finish_close_prompt = lambda result: frontend._finish_close_prompt(app, result)
    app.push_screen = lambda screen, callback: dialogs.append((screen, callback))
    def create_thread(**kwargs):
        if kwargs.get("name") == "FHDS-TelemetryResume":
            helper = REAL_THREAD(**kwargs)
            app._resume_helpers.append(helper)
            return helper
        return Worker(**kwargs)

    monkeypatch.setattr(module.threading, "Thread", create_thread)
    monkeypatch.setattr(module.profiles, "next_profile_name", lambda: "Saved tuning")
    if module is gui:
        monkeypatch.setattr(module, "UnsavedProfileDialog", lambda *_args, **kwargs: dialogs.append(kwargs) or object())
    return app, events, dialogs


def backend_stopped(module, frontend, app):
    if module is gui:
        frontend._on_backend_stopped(app, 4)
    else:
        frontend.on_backend_stopped(app, tui.BackendStopped(4))


def cancel(module, dialogs):
    if module is gui:
        dialogs[0]["on_cancel"]()
    else:
        dialogs[0][1](None)


def wait_for_resume(app):
    for helper in app._resume_helpers:
        helper.join(timeout=1.0)
        assert not helper.is_alive()


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_cancel_game_close_resumes_telemetry_without_reopening_controller(module, frontend, monkeypatch):
    app, events, dialogs = close_app(module, frontend, monkeypatch)
    backend, listener, old_worker = app._ds, app._listener, app._thread
    monkeypatch.setattr(module, "make_backend", lambda *_args: pytest.fail("reuse the current HID owner"))

    backend_stopped(module, frontend, app)
    cancel(module, dialogs)
    wait_for_resume(app)

    assert events == []
    assert app._thread is not old_worker
    assert app._thread.started and app._thread.args == (5,)
    assert app._ds is backend and app._listener is listener
    assert not app._stop.is_set()


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_save_failure_after_game_close_resumes_telemetry(module, frontend, monkeypatch):
    app, events, _dialogs = close_app(module, frontend, monkeypatch, prompt=False)
    monkeypatch.setattr(module.preferences, "save_pending", lambda _s: False)

    backend_stopped(module, frontend, app)
    wait_for_resume(app)

    assert events == ["save failed"]
    assert app._thread.started and app._thread.args == (5,)


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_update_failure_after_game_close_resumes_telemetry(module, frontend, monkeypatch):
    app, events, _dialogs = close_app(module, frontend, monkeypatch, prompt=False)
    monkeypatch.setattr(module.preferences, "save_pending", lambda _s: True)

    def fail_update():
        raise RuntimeError("helper cannot start")

    frontend._finish_close(app, fail_update)
    wait_for_resume(app)

    assert events == ["update failed"]
    assert app._thread.started and app._thread.args == (5,)


@pytest.mark.parametrize("module,frontend", FRONTENDS)
@pytest.mark.parametrize("alive,stopping", [(True, False), (False, True)])
def test_declined_close_does_not_duplicate_a_live_or_stopping_loop(module, frontend, monkeypatch, alive, stopping):
    app, _events, _dialogs = close_app(module, frontend, monkeypatch)
    app._thread.alive = alive
    old_worker = app._thread
    if stopping:
        app._stop.set()

    frontend._resume_stopped_loop(app)
    wait_for_resume(app)

    assert app._thread is old_worker
    assert app._backend_generation == 4


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_crashed_loop_cancel_shows_failure_without_repeated_restart(module, frontend, monkeypatch):
    app, events, dialogs = close_app(module, frontend, monkeypatch)
    queued = []
    app.post_ui = queued.append
    app.post_message = queued.append

    def crash(*_args, **_kwargs):
        raise RuntimeError("broken telemetry renderer")

    monkeypatch.setattr(module.loop, "run", crash)
    frontend._run_loop(app, 4)
    backend_stopped(module, frontend, app)
    cancel(module, dialogs)
    wait_for_resume(app)

    assert events == []
    assert not app._thread.started
    assert "Telemetry loop crashed" in app._backend_error


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_successful_close_does_not_restart_telemetry(module, frontend, monkeypatch):
    app, events, _dialogs = close_app(module, frontend, monkeypatch, prompt=False)
    monkeypatch.setattr(module.preferences, "save_pending", lambda _s: True)

    backend_stopped(module, frontend, app)
    wait_for_resume(app)

    assert events == ["exit"]
    assert not app._thread.started


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_immediate_save_failure_waits_for_worker_to_finish_before_resuming(module, frontend, monkeypatch):
    app, _events, _dialogs = close_app(module, frontend, monkeypatch, prompt=False)
    joined = []
    old_worker = Worker(alive=True)
    app._thread = old_worker

    def finish(timeout=None):
        assert threading.get_ident() != ui_thread
        joined.append(timeout)
        old_worker.alive = False

    old_worker.join = finish
    ui_thread = threading.get_ident()
    monkeypatch.setattr(module.preferences, "save_pending", lambda _s: False)

    backend_stopped(module, frontend, app)
    wait_for_resume(app)

    assert joined == [2.0]
    assert app._thread.started and app._thread.args == (5,)


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_late_old_exit_notification_does_not_close_resumed_loop(module, frontend, monkeypatch):
    app, events, dialogs = close_app(module, frontend, monkeypatch)
    backend_stopped(module, frontend, app)
    cancel(module, dialogs)
    wait_for_resume(app)
    current_worker = app._thread

    backend_stopped(module, frontend, app)

    assert app._thread is current_worker and current_worker.is_alive()
    assert len(dialogs) == 1
    assert events == []


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_resume_failure_remains_visible_and_does_not_retry_indefinitely(module, frontend, monkeypatch):
    app, _events, _dialogs = close_app(module, frontend, monkeypatch)
    old_worker = app._thread
    starts = []

    class FailedWorker(Worker):
        def start(self):
            starts.append(True)
            raise RuntimeError("cannot start another thread")

    def create_thread(**kwargs):
        if kwargs.get("name") == "FHDS-TelemetryResume":
            helper = REAL_THREAD(**kwargs)
            app._resume_helpers.append(helper)
            return helper
        return FailedWorker(**kwargs)

    monkeypatch.setattr(module.threading, "Thread", create_thread)

    frontend._resume_stopped_loop(app)
    wait_for_resume(app)
    frontend._resume_stopped_loop(app)
    wait_for_resume(app)

    assert app._thread is old_worker
    assert starts == [True]
    assert "could not resume" in app._backend_error


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_resume_lifecycle_lock_wait_never_blocks_ui_and_coalesces_requests(module, frontend, monkeypatch):
    app, _events, _dialogs = close_app(module, frontend, monkeypatch)
    old_worker = app._thread
    app._backend_restart_lock.acquire()
    try:
        frontend._resume_stopped_loop(app)
        frontend._resume_stopped_loop(app)
        assert app._thread is old_worker
        assert app._loop_resume_pending
        assert len(app._resume_helpers) == 1
    finally:
        app._backend_restart_lock.release()

    wait_for_resume(app)
    assert app._thread.started and app._thread.args == (5,)


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_unfinished_notifying_worker_is_not_duplicated(module, frontend, monkeypatch):
    app, events, _dialogs = close_app(module, frontend, monkeypatch, prompt=False)
    old_worker = Worker(alive=True)
    app._thread = old_worker
    monkeypatch.setattr(module.preferences, "save_pending", lambda _s: False)

    backend_stopped(module, frontend, app)
    wait_for_resume(app)

    assert events == ["save failed"]
    assert app._thread is old_worker
    assert "did not stop" in app._backend_error
    assert not app._loop_resume_pending


@pytest.mark.parametrize("module,frontend", FRONTENDS)
def test_resume_request_obsolete_after_backend_restart_cannot_replace_new_worker(module, frontend, monkeypatch):
    app, _events, _dialogs = close_app(module, frontend, monkeypatch)
    current_worker = Worker(alive=True)
    app._backend_restart_lock.acquire()
    try:
        frontend._resume_stopped_loop(app)
        app._backend_generation = 5
        app._thread = current_worker
    finally:
        app._backend_restart_lock.release()

    wait_for_resume(app)

    assert app._thread is current_worker
    assert app._backend_generation == 5
    assert not app._backend_error
