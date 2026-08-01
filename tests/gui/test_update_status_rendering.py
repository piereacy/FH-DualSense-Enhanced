from __future__ import annotations

from pathlib import Path

from modules.update import UpdatePhase
from modules.update.model import UpdateRelease, UpdateSnapshot
from modules.update.presentation import update_status_presentation


def _release() -> UpdateRelease:
    return UpdateRelease(
        version=8,
        tag="R8",
        body="",
        html_url="https://example.invalid/R8",
        asset_name="FH-DualSense-Enhanced-R8.exe",
        asset_url="https://example.invalid/R8.exe",
        asset_size=100,
        checksum_url="https://example.invalid/R8.exe.sha256",
    )


def test_update_status_presentation_changes_only_for_visible_state():
    def translate(value: str) -> str:
        return value

    first = update_status_presentation(UpdateSnapshot(), translate)
    same_visible_state = update_status_presentation(
        UpdateSnapshot(last_checked_at=123.0),
        translate,
    )

    assert first == same_visible_state
    assert first.action is None
    assert first.release_visible is False
    assert first.manual_download_url == ""


def test_update_status_presentation_exposes_action_progress_and_release():
    release = _release()
    downloading = update_status_presentation(
        UpdateSnapshot(
            phase=UpdatePhase.DOWNLOADING,
            release=release,
            downloaded=25,
            total=100,
        ),
        lambda value: value,
    )
    available = update_status_presentation(
        UpdateSnapshot(phase=UpdatePhase.AVAILABLE, release=release),
        lambda value: value,
    )
    ready = update_status_presentation(
        UpdateSnapshot(phase=UpdatePhase.READY, release=release),
        lambda value: value,
    )

    assert downloading.progress == 0.25
    assert downloading.release_visible is True
    assert downloading.manual_download_url == release.asset_url
    assert downloading.action is None
    assert available.action == "download"
    assert available.manual_download_url == release.asset_url
    assert ready.action == "install"
    assert ready.manual_download_url == release.asset_url


def test_manual_download_link_is_hidden_when_no_newer_release_is_active():
    release = _release()

    up_to_date = update_status_presentation(
        UpdateSnapshot(phase=UpdatePhase.UP_TO_DATE, release=release),
        lambda value: value,
    )

    assert up_to_date.release_visible is True
    assert up_to_date.manual_download_url == ""


def test_both_interfaces_render_the_direct_asset_as_a_manual_download_link():
    root = Path(__file__).resolve().parents[2]
    gui = (root / "src/modules/gui/system_tab.py").read_text(encoding="utf-8")
    tui = (root / "src/modules/tui/system_tab.py").read_text(encoding="utf-8")

    for source in (gui, tui):
        assert "Or download manually: {url}" in source
        assert "release.asset_url" in source
