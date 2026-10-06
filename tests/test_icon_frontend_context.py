"""Old confirmations must never write files in a newly selected installation."""

import asyncio
from types import MethodType, SimpleNamespace

import pytest

from modules.config.settings import Settings
from modules.gui import fh6_utilities_tab as gui
from modules.tui import fh6_utilities_tab as tui


def _tab(frontend, root):
    settings = Settings(preferred_forza_platform="steam", fh6_install_path=str(root))
    tab = SimpleNamespace(
        settings=settings,
        app=SimpleNamespace(root=None, toast=lambda *_args: None),
        _icon_platform="steam",
        _icon_path_hint=str(root),
        _icon_scan_serial=1,
        _icon_inspection=SimpleNamespace(root=root),
        _icon_operation_busy=False,
        _icon_scan_busy=False,
        _icon_busy=False,
    )
    for name in ("_icon_saved_path", "_icon_action_context", "_run_icon_action"):
        setattr(tab, name, MethodType(getattr(frontend, name), tab))
    return tab


@pytest.mark.parametrize("change", ["path", "platform", "scan"])
def test_gui_icon_confirmation_is_bound_to_the_original_installation(tmp_path, monkeypatch, change):
    tab = _tab(gui.FH6UtilitiesTab, tmp_path / "A")
    confirmations = []
    monkeypatch.setattr(gui, "ConfirmationDialog", lambda _root, **kw: confirmations.append(kw["on_confirm"]))
    monkeypatch.setattr(gui.threading, "Thread", lambda **_kw: pytest.fail("stale confirmation launched a file worker"))
    gui.FH6UtilitiesTab._request_icon_action(tab, "install")
    assert len(confirmations) == 1
    if change == "path":
        tab.settings.fh6_install_path = str(tmp_path / "B")
    elif change == "platform":
        tab.settings.preferred_forza_platform = "xbox_app"
    else:
        tab._icon_scan_serial += 1
    confirmations[0]()
    assert not tab._icon_operation_busy


@pytest.mark.parametrize("change", ["path", "platform", "scan"])
def test_tui_icon_action_rejects_an_obsolete_confirmation(tmp_path, monkeypatch, change):
    tab = _tab(tui.FH6UtilitiesTab, tmp_path / "A")
    context = tab._icon_action_context()
    monkeypatch.setattr(tui, "install_controller_icons", lambda *_args: pytest.fail("stale operation modified files"))
    if change == "path":
        tab.settings.fh6_install_path = str(tmp_path / "B")
    elif change == "platform":
        tab.settings.preferred_forza_platform = "xbox_app"
    else:
        tab._icon_scan_serial += 1
    asyncio.run(tab._run_icon_action("install", context))
    assert not tab._icon_operation_busy
