import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_and_development_dependencies_are_declared():
    metadata = tomllib.loads((ROOT / "src/pyproject.toml").read_text(encoding="utf-8"))
    dependencies = metadata["project"]["dependencies"]

    assert any(value.startswith("numpy>=") for value in dependencies)
    assert any(value.startswith("sounddevice>=") for value in dependencies)
    assert any(value.startswith("pytest>=") for value in metadata["dependency-groups"]["dev"])


def test_windows_and_release_builds_install_audio_dependencies():
    batch = (ROOT / "packaging/windows/build_exe.bat").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "--with numpy --with sounddevice" in batch
    assert workflow.count("--with numpy --with sounddevice") == 2
    assert "THIRD_PARTY_NOTICES.md" in batch
    assert "cp win_start.bat linux_start.sh LICENSE docs/THIRD_PARTY_NOTICES.md release/" in workflow


def test_pyinstaller_specs_collect_sounddevice_runtime():
    for path in (
        ROOT / "packaging/windows/fhds.spec",
        ROOT / "packaging/linux/fhds.spec",
    ):
        text = path.read_text(encoding="utf-8")
        compile(text, str(path), "exec")
        assert 'collect_dynamic_libs("_sounddevice_data")' in text
        assert '"sounddevice"' in text
        assert "THIRD_PARTY_NOTICES.md" in text


def test_horizonhaptics_notice_and_user_docs_are_present():
    notice = (ROOT / "docs/THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    readme = (ROOT / "README_EN.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "79fbe2fd7a56e21bd101867dbf14718f2e91ffab" in notice
    assert "MIT License" in notice
    assert "Bluetooth" in readme and "compatible rumble" in readme
    assert "蓝牙" in readme_zh and "兼容振动" in readme_zh
