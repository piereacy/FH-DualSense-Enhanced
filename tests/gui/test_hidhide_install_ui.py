from pathlib import Path
from queue import SimpleQueue
from types import SimpleNamespace

import pytest

from modules.dualsense.hidhide_installer import (
    HidHideDetection,
    HidHideInstallProgress,
    HidHideInstallStage,
)
from modules.gui import overview_tab
from modules.gui.overview_tab import OverviewTab
from modules.xinput.driver import InstallResult, InstallStatus


def test_install_result_is_delivered_by_gui_poll_even_after_worker_exits():
    events = SimpleQueue()
    result = InstallResult(InstallStatus.SUCCESS)
    events.put(result)
    seen = []
    state = SimpleNamespace(
        _hidhide_events=events,
        _hidhide_installing=True,
        _hidhide_install_thread=SimpleNamespace(is_alive=lambda: False),
        _hidhide_installed=None,
        _on_hidhide_install_done=lambda value: (seen.append(value), setattr(state, "_hidhide_installing", False)),
        _on_hidhide_install_error=lambda message: seen.append(message),
    )

    OverviewTab._poll_hidhide_events(state)

    assert seen == [result]
    assert not state._hidhide_installing


def test_dead_installer_worker_cannot_leave_install_status_stuck():
    errors = []
    state = SimpleNamespace(
        _hidhide_events=SimpleQueue(),
        _hidhide_installing=True,
        _hidhide_install_thread=SimpleNamespace(is_alive=lambda: False),
        _hidhide_installed=None,
        _on_hidhide_install_done=lambda _result: None,
        _on_hidhide_install_error=lambda message: errors.append(message),
    )

    OverviewTab._poll_hidhide_events(state)

    assert errors


class _Widget:
    def __init__(self):
        self.options = {}
        self.visible = False
        self.running = False
        self.value = None

    def configure(self, **options):
        self.options.update(options)

    def grid(self):
        self.visible = True

    def grid_remove(self):
        self.visible = False

    def start(self):
        self.running = True

    def stop(self):
        self.running = False

    def set(self, value):
        self.value = value


@pytest.mark.parametrize("client_available", [False, True])
def test_installed_driver_shows_official_client_only_when_found(monkeypatch, client_available):
    monkeypatch.setattr(
        overview_tab,
        "find_hidhide_client",
        lambda: Path("HidHideClient.exe") if client_available else None,
    )
    monkeypatch.setattr(
        overview_tab,
        "hidhide_presentation",
        lambda *_args, **_kwargs: SimpleNamespace(title="ready", detail="waiting"),
    )
    state = SimpleNamespace(
        _hidhide_installed=True,
        _hidhide_driver_ready=True,
        _hidhide_installing=False,
        _hidhide_install_message=None,
        _hidhide_install_button=_Widget(),
        _hidhide_open_button=_Widget(),
        _hidhide_install_notice=_Widget(),
        _hidhide_status=_Widget(),
        _hidhide_detail=_Widget(),
        _hidhide_presentation=None,
        settings=SimpleNamespace(),
        app=SimpleNamespace(
            _xinput_service=SimpleNamespace(
                snapshot=lambda: None,
                hidhide_snapshot=lambda: None,
            ),
            _ds=None,
        ),
    )
    OverviewTab._refresh_hidhide_status(state)
    assert state._hidhide_install_button.options["text"] == overview_tab.t(
        "Check HidHide and enable isolation"
    )
    assert state._hidhide_open_button.options["state"] == (
        "normal" if client_available else "disabled"
    )
    assert state._hidhide_install_notice.options["text"] == overview_tab.t("HidHide installed")


def test_probe_event_uses_installation_marker_not_client_path():
    events = SimpleQueue()
    events.put(HidHideDetection(installed=True, driver_ready=False))
    state = SimpleNamespace(
        _hidhide_events=events,
        _hidhide_installing=False,
        _hidhide_install_thread=None,
        _hidhide_installed=None,
        _hidhide_driver_ready=None,
    )
    OverviewTab._poll_hidhide_events(state)
    assert state._hidhide_installed is True
    assert state._hidhide_driver_ready is False


def test_progress_bar_uses_download_bytes_and_waits_indeterminately():
    state = SimpleNamespace(
        _hidhide_installing=True,
        _hidhide_progress_mode=None,
        _hidhide_progress=_Widget(),
        _hidhide_install_notice=_Widget(),
        _hidhide_install_message=None,
    )
    OverviewTab._show_hidhide_progress(
        state, HidHideInstallProgress(HidHideInstallStage.DOWNLOADING, 0.5)
    )
    assert state._hidhide_progress.value == 0.5
    assert "50%" in state._hidhide_install_notice.options["text"]
    OverviewTab._show_hidhide_progress(
        state, HidHideInstallProgress(HidHideInstallStage.INSTALLING)
    )
    assert state._hidhide_progress.running
    assert state._hidhide_progress.options["mode"] == "indeterminate"
    OverviewTab._finish_hidhide_progress(state)
    assert not state._hidhide_progress.visible
    assert not state._hidhide_progress.running
