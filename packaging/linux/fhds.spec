# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for FH-DualSense-Enhanced (Linux).

One-file ELF binary. On launch the bootloader extracts everything into a
temp dir (MEIPASS) and auto-deletes it on exit. No Windows VERSIONINFO and
no embedded icon (PyInstaller can't embed an icon into a bare ELF).

Build:
    packaging/linux/build_elf.sh
"""

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

SRC = Path(SPECPATH).resolve().parents[1] / "src"
ROOT = SRC.parent

datas = [
    (str(SRC / "data" / "icon.ico"), "data"),
    (str(SRC / "data" / "icon.png"), "data"),
    (str(SRC / "pyproject.toml"), "."),
    (str(SRC / "lang"), "lang"),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "docs" / "THIRD_PARTY_NOTICES.md"), "docs"),
]
datas += collect_data_files("customtkinter")
datas += collect_data_files("textual")
binaries = collect_dynamic_libs("_sounddevice_data")

hiddenimports = []
hiddenimports += collect_submodules("textual")
hiddenimports += collect_submodules("customtkinter")
hiddenimports += collect_submodules("pystray")
hiddenimports += ["PIL.Image", "PIL.ImageDraw", "sounddevice", "_sounddevice"]

a = Analysis(
    [str(SRC / "main.py")],
    pathex=[str(SRC)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FH-DualSense-Enhanced",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
