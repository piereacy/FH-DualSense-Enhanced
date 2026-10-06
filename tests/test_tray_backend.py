"""Backend selection is testable without a desktop or a frozen build."""

import builtins
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from modules.gui.main import TriggerGUI

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("platform,frozen,wayland,session,override,backend,supported", [
    ("linux", True, "wayland-0", "", "", "xorg", False),
    ("linux", True, "", "wayland", "", "xorg", False),
    ("linux", True, "wayland-0", "", "xorg", "xorg", False),
    ("linux", True, "wayland-0", "", "appindicator", "xorg", False),
    ("linux", True, "", "x11", "", "xorg", True),
    ("linux", True, "", "x11", "appindicator", "xorg", True),
    ("linux", False, "wayland-0", "", "", "appindicator", True),
    ("linux", False, "", "wayland", "", "appindicator", True),
    ("linux", False, "wayland-0", "", "xorg", "xorg", True),
    ("linux", False, "", "x11", "", "", True),
    ("win32", True, "", "", "", "", True),
])
def test_backend_matches_packaged_dependencies(monkeypatch, platform, frozen, wayland, session, override, backend, supported):
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(sys, "frozen", frozen, raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", wayland)
    monkeypatch.setenv("XDG_SESSION_TYPE", session)
    monkeypatch.setenv("PYSTRAY_BACKEND", override)
    namespace = runpy.run_path(str(ROOT / "src/modules/gui/tray.py"))
    assert os.environ["PYSTRAY_BACKEND"] == backend
    assert namespace["TRAY_BACKEND_SUPPORTED"] is supported


def test_frozen_wayland_refuses_tray_without_hiding_the_window(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("PYSTRAY_BACKEND", "xorg")
    namespace = runpy.run_path(str(ROOT / "src/modules/gui/tray.py"))
    imports = []
    original_import = builtins.__import__

    def tracked_import(name, *args, **kwargs):
        imports.append(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", tracked_import)
    root = SimpleNamespace(withdraw=lambda: pytest.fail("no usable tray to restore the window"))
    tray = namespace["TrayController"](root, lambda: None, lambda: None, post_ui=lambda callback: callback())
    app = SimpleNamespace(root=root, _tray=tray,
                          _revoke_haptics_lab_preview=lambda reason: pytest.fail("window stays accessible"))
    TriggerGUI._hide_to_tray(app)
    assert "pystray" not in imports
    assert tray._icon is None
    assert tray._thread is None


def test_linux_spec_excludes_gi_and_explicitly_collects_xorg():
    spec = (ROOT / "packaging/linux/fhds.spec").read_text(encoding="utf-8")
    build = (ROOT / "packaging/linux/build_elf.sh").read_text(encoding="utf-8")
    assert 'hiddenimports += ["pystray._xorg"]' in spec
    assert 'collect_submodules("Xlib")' in spec
    assert 'collect_submodules("pystray")' not in spec
    assert 'excludes=["gi", "cairo", "pystray._appindicator", "pystray._gtk"]' in spec
    assert "--no-install-package pygobject --no-install-package pycairo" in build


def test_tray_quit_keeps_icon_until_ui_confirms(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    namespace = runpy.run_path(str(ROOT / "src/modules/gui/tray.py"))
    icons = []
    queued = []
    requested = []

    class Icon:
        def __init__(self, _name, _image, _title, menu):
            self.menu = menu
            self.stopped = False
            icons.append(self)

        def run(self):
            pass

        def stop(self):
            self.stopped = True

    pystray = SimpleNamespace(
        Icon=Icon, Menu=lambda *items: items,
        MenuItem=lambda label, callback, **_kwargs: (label, callback),
    )
    monkeypatch.setitem(sys.modules, "pystray", pystray)
    tray = namespace["TrayController"](
        SimpleNamespace(), lambda: None, lambda: requested.append(True),
        post_ui=queued.append,
    )
    assert tray.start()
    icon = icons[0]
    icon.menu[1][1]()
    assert not icon.stopped
    assert requested == []
    queued.pop()()
    assert requested == [True]
    assert not icon.stopped
    tray.stop()
    assert icon.stopped
