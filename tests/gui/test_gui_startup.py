"""Windows GUI construction smoke test for the packaged startup path."""

import sys

import pytest

from modules.config.settings import Settings
from modules.dualsense.hidhide_installer import HidHideInstallProgress, HidHideInstallStage


@pytest.mark.skipif(sys.platform != "win32", reason="requires the Windows GUI")
def test_gui_constructs_every_tab_after_hidhide_move(monkeypatch):
    import customtkinter as ctk

    from modules.gui import main as gui

    roots = []
    original_ctk = ctk.CTk

    class HiddenCTk(original_ctk):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.withdraw()
            roots.append(self)

    monkeypatch.setattr(ctk, "CTk", HiddenCTk)
    monkeypatch.setattr(gui, "cleanup_previous_update", lambda: None)

    try:
        app = gui.TriggerGUI(Settings())
        app.root.update_idletasks()
        assert len(app._tab_frames) == len(gui.NAV_ITEMS)
        assert app.system_tab._display_card is not None
        app.overview_tab._hidhide_installing = True
        app.overview_tab._show_hidhide_progress(
            HidHideInstallProgress(HidHideInstallStage.DOWNLOADING, 0.5)
        )
        app.root.update_idletasks()
        assert app.overview_tab._hidhide_progress.winfo_manager() == "grid"
        app.overview_tab._finish_hidhide_progress()
    finally:
        for root in roots:
            root.destroy()
