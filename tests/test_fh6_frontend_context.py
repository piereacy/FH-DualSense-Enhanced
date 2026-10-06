import asyncio
from types import MethodType, SimpleNamespace

import pytest

from modules.forzahorizon.fh6_language import (
    FH6Install,
    FH6LanguageState,
    LanguageInspection,
)
from modules.forzahorizon.fh6_language_presentation import LanguageView
from modules.gui import fh6_utilities_tab as gui
from modules.tui import fh6_utilities_tab as tui


def _tab(module, tmp_path):
    install = FH6Install(tmp_path / "A", tmp_path / "A/tables", "Steam", "english")
    notifications = []
    callbacks = []
    tab = SimpleNamespace(
        settings=SimpleNamespace(
            preferred_forza_platform="steam",
            fh6_install_path=str(install.root),
            fh6_xbox_install_path="",
        ),
        app=SimpleNamespace(
            root=None, _tearing_down=False, post_ui=callbacks.append,
            toast=notifications.append,
            notify=lambda message, **_kwargs: notifications.append(message),
        ),
        _fh6_install=install,
        _fh6_inspection=LanguageInspection(FH6LanguageState.NATIVE, install),
        _fh6_platform="steam", _fh6_path_hint=str(install.root),
        _fh6_scan_serial=1, _fh6_active_serial=None,
        _fh6_scan_busy=False, _fh6_operation_busy=False, _fh6_busy=False,
        _fh6_game_running=False, _fh6_pending_action="", _fh6_pending_context=None,
        _fh6_confirm_deadline=0.0, _fh6_silent=False,
        _fh6_view=LanguageView("", "", "enable", "Enable", True),
        _fh6_error="", _fh6_render_cache=None,
        _icon_platform="steam", _icon_path_hint=str(install.root),
        _icon_scan_serial=1, _icon_active_serial=None,
        _icon_busy=False, _icon_operation_busy=False,
        _icon_inspection=SimpleNamespace(root=install.root),
        _visible=False, is_mounted=False,
        _render_fh6_status=lambda: None,
        query_one=lambda *_args: SimpleNamespace(value=""),
    )
    for name in (
        "_language_saved_path", "_icon_saved_path", "_sync_context",
        "_invalidate_fh6", "_invalidate_icons", "_fh6_action_context",
        "_request_fh6_action", "_run_fh6_action", "_finish_fh6_action",
        "_scan_fh6", "_start_fh6_scan", "_apply_fh6_scan", "on_button_pressed",
    ):
        method = getattr(module.FH6UtilitiesTab, name, None)
        if method is not None:
            setattr(tab, name, MethodType(method, tab))
    return tab, notifications, callbacks


def _select_b(tab, tmp_path):
    install = FH6Install(tmp_path / "B", tmp_path / "B/tables", "Steam", "english")
    tab.settings.fh6_install_path = str(install.root)
    tab._sync_context()
    tab._fh6_install = install
    tab._fh6_inspection = LanguageInspection(FH6LanguageState.NATIVE, install)
    return tab._fh6_inspection


def _gui_workers(monkeypatch):
    workers = []
    monkeypatch.setattr(
        gui.threading, "Thread",
        lambda *, target, **_kwargs: SimpleNamespace(start=lambda: workers.append(target)),
    )
    return workers


def test_gui_language_confirmation_cannot_switch_install(tmp_path, monkeypatch):
    tab, _notifications, _callbacks = _tab(gui, tmp_path)
    confirmations = []
    workers = _gui_workers(monkeypatch)
    monkeypatch.setattr(
        gui, "ConfirmationDialog",
        lambda *_args, **kwargs: confirmations.append(kwargs["on_confirm"]),
    )
    tab._request_fh6_action()
    _select_b(tab, tmp_path)

    confirmations.pop()()

    assert workers == []
    assert not tab._fh6_operation_busy


@pytest.mark.parametrize("failed", [False, True])
def test_gui_language_late_result_preserves_new_install(tmp_path, monkeypatch, failed):
    tab, notifications, callbacks = _tab(gui, tmp_path)
    workers = _gui_workers(monkeypatch)
    monkeypatch.setattr(gui, "ConfirmationDialog", lambda *_args, **kwargs: kwargs["on_confirm"]())
    def operation(install, **_kwargs):
        if failed:
            raise OSError("old install unavailable")
        return LanguageInspection(FH6LanguageState.SWAPPED, install)

    monkeypatch.setattr(gui, "enable_chinese_text_english_voice", operation)
    tab._request_fh6_action()
    workers.pop()()
    current = _select_b(tab, tmp_path)

    callbacks.pop()()

    assert tab._fh6_inspection is current
    assert notifications == []
    assert not tab._fh6_operation_busy


def test_tui_language_second_press_requires_same_install(tmp_path):
    tab, _notifications, _callbacks = _tab(tui, tmp_path)
    actions = []

    async def run(*args, **kwargs):
        actions.append((args, kwargs))

    tab._run_fh6_action = run
    event = SimpleNamespace(button=SimpleNamespace(id="fh6-action"))

    async def scenario():
        await tab.on_button_pressed(event)
        _select_b(tab, tmp_path)
        await tab.on_button_pressed(event)
        assert actions == []
        await tab.on_button_pressed(event)
        assert len(actions) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("failed", [False, True])
def test_tui_language_late_result_preserves_new_install(tmp_path, monkeypatch, failed):
    tab, notifications, _callbacks = _tab(tui, tmp_path)
    def operation(install, **_kwargs):
        if failed:
            raise OSError("old install unavailable")
        return LanguageInspection(FH6LanguageState.SWAPPED, install)

    monkeypatch.setattr(tui, "enable_chinese_text_english_voice", operation)

    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()

        async def delayed(function, *args, **kwargs):
            error = None
            try:
                result = function(*args, **kwargs)
            except OSError as exc:
                error = exc
            started.set()
            await release.wait()
            if error is not None:
                raise error
            return result

        monkeypatch.setattr(tui.asyncio, "to_thread", delayed)
        event = SimpleNamespace(button=SimpleNamespace(id="fh6-action"))
        await tab.on_button_pressed(event)
        task = asyncio.create_task(tab.on_button_pressed(event))
        await started.wait()
        current = _select_b(tab, tmp_path)
        release.set()
        await task
        assert tab._fh6_inspection is current
        assert notifications == []
        assert not tab._fh6_busy

    asyncio.run(scenario())


def test_gui_language_worker_rechecks_confirmed_context(tmp_path, monkeypatch):
    tab, notifications, callbacks = _tab(gui, tmp_path)
    workers = _gui_workers(monkeypatch)
    monkeypatch.setattr(gui, "ConfirmationDialog", lambda *_args, **kwargs: kwargs["on_confirm"]())
    monkeypatch.setattr(
        gui, "enable_chinese_text_english_voice",
        lambda *_args, **_kwargs: pytest.fail("obsolete confirmation must not modify files"),
    )
    tab._request_fh6_action()
    current = _select_b(tab, tmp_path)

    workers.pop()()
    callbacks.pop()()

    assert tab._fh6_inspection is current
    assert notifications == []
    assert not tab._fh6_operation_busy


def test_tui_language_worker_rechecks_confirmed_context(tmp_path, monkeypatch):
    tab, notifications, _callbacks = _tab(tui, tmp_path)
    monkeypatch.setattr(
        tui, "enable_chinese_text_english_voice",
        lambda *_args, **_kwargs: pytest.fail("obsolete confirmation must not modify files"),
    )

    async def scenario():
        current = None

        async def delayed(function, *args, **kwargs):
            nonlocal current
            current = _select_b(tab, tmp_path)
            return function(*args, **kwargs)

        monkeypatch.setattr(tui.asyncio, "to_thread", delayed)
        event = SimpleNamespace(button=SimpleNamespace(id="fh6-action"))
        await tab.on_button_pressed(event)
        await tab.on_button_pressed(event)
        assert tab._fh6_inspection is current
        assert notifications == []
        assert not tab._fh6_operation_busy
        assert not tab._fh6_busy

    asyncio.run(scenario())


@pytest.mark.parametrize("manual", [False, True])
@pytest.mark.parametrize("old_failed", [False, True])
def test_tui_language_obsolete_scan_cannot_clear_new_scan(
    tmp_path, monkeypatch, manual, old_failed,
):
    tab, notifications, _callbacks = _tab(tui, tmp_path)
    old_install = tab._fh6_install
    new_install = FH6Install(tmp_path / "B", tmp_path / "B/tables", "Steam", "english")
    monkeypatch.setattr(tui, "inspect_language_state", lambda install: LanguageInspection(FH6LanguageState.NATIVE, install))
    monkeypatch.setattr(tui, "is_fh6_running", lambda _install: False)
    monkeypatch.setattr(tui.preferences, "save", lambda _settings: True)

    async def scenario():
        old_started, new_started = asyncio.Event(), asyncio.Event()
        release_old, release_new = asyncio.Event(), asyncio.Event()
        discoveries = 0

        async def delayed(function, *args, **kwargs):
            nonlocal discoveries
            if function in (tui.discover_fh6_install, tui.validate_game_root):
                discoveries += 1
                if discoveries == 1:
                    old_started.set()
                    await release_old.wait()
                    if old_failed:
                        raise OSError("obsolete scan failed")
                    return old_install
                new_started.set()
                await release_new.wait()
                return new_install
            return function(*args, **kwargs)

        monkeypatch.setattr(tui.asyncio, "to_thread", delayed)
        first = asyncio.create_task(tab._scan_fh6(rediscover=True))
        await old_started.wait()
        if not manual:
            _select_b(tab, tmp_path)
        second = asyncio.create_task(tab._scan_fh6(
            rediscover=True, manual_path=str(new_install.root) if manual else "",
        ))
        await new_started.wait()
        active_serial = tab._fh6_active_serial
        release_old.set()
        await first
        assert tab._fh6_busy
        assert tab._fh6_active_serial == active_serial
        assert tab._fh6_install != old_install or manual
        assert notifications == []
        release_new.set()
        await second
        assert tab._fh6_install == new_install
        assert tab.settings.fh6_install_path == str(new_install.root)
        assert not tab._fh6_busy
        assert tab._fh6_active_serial is None

    asyncio.run(scenario())


def test_gui_language_manual_scan_cannot_replace_later_saved_path(tmp_path, monkeypatch):
    tab, notifications, callbacks = _tab(gui, tmp_path)
    workers = _gui_workers(monkeypatch)
    install = tab._fh6_install
    monkeypatch.setattr(gui, "validate_game_root", lambda *_args, **_kwargs: install)
    monkeypatch.setattr(gui, "inspect_language_state", lambda root: LanguageInspection(FH6LanguageState.NATIVE, root))
    monkeypatch.setattr(gui, "is_fh6_running", lambda _install: False)
    tab._start_fh6_scan(rediscover=False, manual_path=str(install.root))
    workers.pop()()
    tab.settings.fh6_install_path = str(tmp_path / "B")

    callbacks.pop()()

    assert tab.settings.fh6_install_path == str(tmp_path / "B")
    assert tab._fh6_install is None
    assert notifications == []
    assert not tab._fh6_scan_busy


def test_tui_language_invalid_manual_folder_notifies_user(tmp_path, monkeypatch):
    tab, notifications, _callbacks = _tab(tui, tmp_path)
    monkeypatch.setattr(tui, "validate_game_root", lambda *_args, **_kwargs: None)

    asyncio.run(tab._scan_fh6(rediscover=False, manual_path=str(tmp_path / "missing")))

    assert tab._fh6_install is None
    assert notifications
    assert not tab._fh6_busy
