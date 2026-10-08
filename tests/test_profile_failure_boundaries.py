from types import SimpleNamespace

import pytest

from modules.config import preferences, profiles
from modules.config.profile_session import ProfileSession
from modules.config.settings import Settings
from modules.gui.main import TriggerGUI
from modules.gui.profiles_tab import ProfilesTab as GUIProfilesTab
from modules.tui.main import TriggerTUI
from modules.tui.profiles_tab import ProfilesTab as TUIProfilesTab


@pytest.fixture
def instances(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences, "PATH", tmp_path / "preferences.json")
    monkeypatch.setattr(preferences, "_DATA", tmp_path)
    first = Settings()
    preferences.load(first)
    assert profiles.save_profile("Track", first) == "Track"
    second = Settings()
    preferences.load(second)
    return first, second


def _conflict(instances, field):
    first, second = instances
    for settings, value in ((second, 8), (first, 9)):
        setattr(settings, field, value)
        saved = preferences.save(settings)
        assert saved is (settings is second)
    return first


@pytest.mark.parametrize("field", ["brake_max_force", "udp_timeout"])
def test_profile_load_preserves_changes_after_autosave_conflict(instances, field):
    settings = _conflict(instances, field)
    original = preferences.PATH.read_bytes()

    assert profiles.apply_profile("Default", settings) is False

    assert getattr(settings, field) == 9
    assert profiles.active_name(settings) == "Track"
    assert preferences.PATH.read_bytes() == original


def test_profile_load_preserves_changes_when_pending_save_cannot_write(instances, monkeypatch):
    settings, _ = instances
    settings.brake_max_force = 9
    original = preferences.PATH.read_bytes()
    monkeypatch.setattr(preferences, "_write", lambda _raw: False)

    assert profiles.apply_profile("Default", settings) is False

    assert settings.brake_max_force == 9
    assert profiles.active_name(settings) == "Track"
    assert preferences.PATH.read_bytes() == original


def test_profile_load_saves_pending_changes_before_rebinding(instances):
    settings, _ = instances
    settings.brake_max_force = 9
    settings.udp_timeout = 8

    assert profiles.apply_profile("Default", settings)

    raw = preferences._read_raw()
    assert raw["profiles"]["Track"]["brake_max_force"] == 9
    assert raw["globals"]["udp_timeout"] == 8
    assert settings.brake_max_force == Settings().brake_max_force
    assert profiles.active_name(settings) == "Default"


def test_active_profile_delete_does_not_erase_unsaved_conflicting_changes(instances):
    settings = _conflict(instances, "brake_max_force")
    original = preferences.PATH.read_bytes()

    assert profiles.delete_profile("Track", settings) is False

    assert settings.brake_max_force == 9
    assert preferences.PATH.read_bytes() == original


def _frontend(frontend, settings):
    events = []
    app = SimpleNamespace(
        settings=settings,
        toast=lambda message: events.append(("error", message)),
        notify=lambda message, **_kwargs: events.append(("error", message)),
        _perform_quit=lambda: events.append("exit"),
        exit=lambda: events.append("exit"),
    )
    app.report_save_failure = lambda: frontend.report_save_failure(app)
    app._resume_stopped_loop = lambda: None
    return app, events


@pytest.mark.parametrize("frontend", [TriggerGUI, TriggerTUI])
@pytest.mark.parametrize("field", ["brake_max_force", "udp_timeout"])
def test_exit_keeps_window_open_and_never_schedules_update_after_save_conflict(
    instances, frontend, field
):
    settings = _conflict(instances, field)
    app, events = _frontend(frontend, settings)

    frontend._finish_close(app, lambda: events.append("update"))

    assert len(events) == 1 and events[0][0] == "error"
    assert getattr(settings, field) == 9


@pytest.mark.parametrize("frontend", [TriggerGUI, TriggerTUI])
def test_exit_retries_transient_save_failure_before_scheduling_update(
    instances, frontend, monkeypatch
):
    settings, _ = instances
    settings.brake_max_force = 9
    with monkeypatch.context() as patch:
        patch.setattr(preferences, "_write", lambda _raw: False)
        assert preferences.save(settings) is False
    app, events = _frontend(frontend, settings)

    frontend._finish_close(app, lambda: events.append("update"))

    assert events == ["update", "exit"]
    assert profiles.load_profiles()["profiles"]["Track"]["brake_max_force"] == 9


@pytest.mark.parametrize("frontend", [TriggerGUI, TriggerTUI])
def test_save_as_preserves_tuning_but_does_not_hide_unsaved_global_conflict(
    instances, frontend
):
    settings = _conflict(instances, "udp_timeout")
    settings.brake_max_force = 9
    assert profiles.save_profile("Kept tuning", settings) == "Kept tuning"
    app, events = _frontend(frontend, settings)

    frontend._finish_close(app)

    assert len(events) == 1 and events[0][0] == "error"
    assert "Application settings" in events[0][1]
    assert profiles.load_profiles()["profiles"]["Kept tuning"]["brake_max_force"] == 9
    assert preferences._read_raw()["globals"]["udp_timeout"] == 8
    assert settings.udp_timeout == 9


@pytest.mark.parametrize("frontend", [TriggerGUI, TriggerTUI])
def test_save_as_recovers_profile_conflict_and_allows_exit(instances, frontend):
    settings = _conflict(instances, "brake_max_force")
    assert profiles.save_profile("Kept tuning", settings) == "Kept tuning"
    app, events = _frontend(frontend, settings)

    frontend._finish_close(app)

    assert events == ["exit"]
    assert profiles.load_profiles()["profiles"]["Track"]["brake_max_force"] == 8
    assert profiles.load_profiles()["profiles"]["Kept tuning"]["brake_max_force"] == 9


@pytest.mark.parametrize("frontend,tab_type", [(TriggerGUI, GUIProfilesTab), (TriggerTUI, TUIProfilesTab)])
def test_profile_tab_load_failure_is_visible(instances, frontend, tab_type):
    settings = _conflict(instances, "brake_max_force")
    app, events = _frontend(frontend, settings)
    app.refresh_setting_widgets = lambda: events.append("refresh")
    tab = SimpleNamespace(
        settings=settings, app=app, _selected_name=lambda: "Default",
        _refresh_list=lambda: events.append("refresh"),
        refresh_list=lambda: events.append("refresh"),
    )

    if frontend is TriggerGUI:
        tab_type._on_load(tab)
    else:
        tab_type.on_button_pressed(tab, SimpleNamespace(button=SimpleNamespace(id="profile-load")))

    assert len(events) == 1 and events[0][0] == "error"


@pytest.mark.parametrize("frontend,tab_type", [(TriggerGUI, GUIProfilesTab), (TriggerTUI, TUIProfilesTab)])
def test_profile_tab_save_failure_keeps_name_and_shows_error(
    instances, frontend, tab_type, monkeypatch
):
    settings, _ = instances
    app, events = _frontend(frontend, settings)
    app.mark_default_saved = lambda: events.append("accepted")
    field = SimpleNamespace(value="Keep this name", delete=lambda *_args: events.append("clear"))
    tab = SimpleNamespace(
        settings=settings, app=app, entry_name=field,
        _name_input=lambda: "Keep this name" if frontend is TriggerGUI else field,
        _refresh_list=lambda: events.append("refresh"),
        refresh_list=lambda: events.append("refresh"),
    )
    monkeypatch.setattr(preferences, "_write", lambda _raw: False)

    if frontend is TriggerGUI:
        tab_type._on_save(tab)
    else:
        tab_type._save_from_input(tab)

    assert len(events) == 1 and events[0][0] == "error"
    assert field.value == "Keep this name"


def test_copy_of_named_profile_does_not_mark_untouched_default_as_changed(instances):
    settings, _ = instances
    settings.brake_max_force = 9
    assert preferences.save(settings)
    session = ProfileSession(settings)
    assert profiles.save_profile("Track copy", settings) == "Track copy"
    session.accept_current_default(settings)

    assert profiles.apply_profile("Default", settings)

    assert not session.needs_named_save(settings)
