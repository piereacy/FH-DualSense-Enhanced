import asyncio
from types import SimpleNamespace

from textual.app import App
from textual.widgets import Input, Static

from modules.tui.dialogs import UnsavedProfileScreen
from modules.tui.main import TriggerTUI
from modules.tui.profiles_tab import ProfilesTab


def test_tui_unsaved_profile_dialog_validates_and_saves_before_exit():
    saved = []
    results = []

    class Harness(App):
        def on_mount(self) -> None:
            self.push_screen(
                UnsavedProfileScreen(
                    suggested_name="profile1",
                    on_save=lambda name: saved.append(name) is None,
                ),
                results.append,
            )

    async def check():
        app = Harness()
        async with app.run_test() as pilot:
            await pilot.pause()
            field = app.screen.query_one("#profile-exit-name", Input)
            field.value = "   "
            await pilot.click("#profile-exit-save")
            await pilot.pause()
            assert str(app.screen.query_one("#profile-exit-error", Static).render())
            assert saved == []

            field = app.screen.query_one("#profile-exit-name", Input)
            field.value = "profile1"
            app.screen._save()
            await pilot.pause()

    asyncio.run(check())

    assert saved == ["profile1"]
    assert results == ["exit"]


def test_tui_unsaved_profile_dialog_direct_exit_and_cancel_are_distinct():
    async def choose(selector):
        results = []

        class Harness(App):
            def on_mount(self) -> None:
                self.push_screen(
                    UnsavedProfileScreen(
                        suggested_name="profile1",
                        on_save=lambda _name: True,
                    ),
                    results.append,
                )

        app = Harness()
        async with app.run_test() as pilot:
            await pilot.click(selector)
            await pilot.pause()
        return results

    assert asyncio.run(choose("#profile-exit-discard")) == ["exit"]
    assert asyncio.run(choose("#profile-exit-cancel")) == [None]


def test_tui_close_prompt_runs_deferred_exit_action_only_after_confirmation(monkeypatch):
    accepted = []
    finished = []
    pushed = []
    settings = object()
    session = SimpleNamespace(
        needs_named_save=lambda current: current is settings,
        accept_current_default=lambda current: accepted.append(current),
    )
    app = SimpleNamespace(
        _tearing_down=False,
        _close_prompt_open=False,
        _pending_before_exit=None,
        _profile_session=session,
        settings=settings,
        refresh_profile=lambda: None,
    )
    app._finish_close = lambda action=None: finished.append(action)
    app._finish_close_prompt = lambda result: TriggerTUI._finish_close_prompt(app, result)
    app.push_screen = lambda screen, callback: pushed.append((screen, callback))
    monkeypatch.setattr("modules.tui.main.profiles.next_profile_name", lambda: "profile1")
    monkeypatch.setattr("modules.tui.main.profiles.save_profile", lambda name, current: name)
    before_exit = object()

    TriggerTUI.request_close(app, before_exit)

    assert app._close_prompt_open is True
    assert finished == []
    screen, callback = pushed[0]
    assert screen._suggested_name == "profile1"
    assert screen._on_save("Touring") is True
    assert accepted == [settings]

    callback("exit")

    assert finished == [before_exit]
    assert app._close_prompt_open is False


def test_tui_profile_heading_escapes_user_supplied_rich_markup(monkeypatch):
    monkeypatch.setattr(
        "modules.tui.profiles_tab.profiles.load_profiles",
        lambda: {"active": "[red]Track[/]", "profiles": {}},
    )
    tab = ProfilesTab(object())

    heading = tab._active_text()

    assert "\\[red]Track\\[/]" in heading
