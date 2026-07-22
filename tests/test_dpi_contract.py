from pathlib import Path
import xml.etree.ElementTree as ET

from modules.dpi import DpiSnapshot, format_dpi_snapshot


ROOT = Path(__file__).resolve().parents[1]


def test_windows_manifest_declares_per_monitor_v2_and_fallback():
    manifest = ROOT / "packaging" / "windows" / "fhds.manifest"
    root = ET.fromstring(manifest.read_text(encoding="utf-8"))
    values = {element.tag.rsplit("}", 1)[-1]: (element.text or "").strip() for element in root.iter()}

    assert values["dpiAwareness"] == "PerMonitorV2, PerMonitor"
    assert values["dpiAware"] == "true/pm"
    assert values["requestedExecutionLevel"] == ""
    level = next(element for element in root.iter() if element.tag.endswith("requestedExecutionLevel"))
    assert level.attrib == {"level": "asInvoker", "uiAccess": "false"}


def test_pyinstaller_uses_manifest_and_pre_tk_runtime_hook():
    spec = (ROOT / "packaging" / "windows" / "fhds.spec").read_text(encoding="utf-8")
    build = (ROOT / "packaging" / "windows" / "build_exe.bat").read_text(encoding="utf-8")
    hook = (ROOT / "packaging" / "windows" / "dpi_runtime_hook.py").read_text(encoding="utf-8")

    assert "manifest=str(MANIFEST)" in spec
    assert "runtime_hooks=[str(RUNTIME_HOOK)]" in spec
    assert '--manifest "%~dp0fhds.manifest"' in build
    assert "uv run --project src --frozen pyinstaller" in build
    assert 'pyinstaller==6.16.0' in (ROOT / "src" / "pyproject.toml").read_text(encoding="utf-8")
    assert "bootstrap_windows_dpi()" in hook


def test_dpi_diagnostic_text_reports_actual_mode_and_scale():
    snapshot = DpiSnapshot(
        awareness="Per-Monitor v2",
        dpi=144,
        scale_percent=150,
        per_monitor_v2=True,
        bootstrap="already-set",
    )

    assert format_dpi_snapshot(snapshot) == "DPI: Per-Monitor v2 · 150%"
