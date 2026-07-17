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
    assert workflow.count("--with numpy --with sounddevice") == 1
    assert "packaging\\windows\\build_exe.bat" in workflow
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


def test_haptics_reference_notices_and_user_docs_are_present():
    notice = (ROOT / "docs/THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_zh = (ROOT / "docs/ReadmeZH.md").read_text(encoding="utf-8")

    assert "79fbe2fd7a56e21bd101867dbf14718f2e91ffab" in notice
    assert "2d27ab0b2ea02e735cd3aa758cc5bf3d6e578534" in notice
    assert "ade9ea15b6fb1bf3f4fdc72da8c316234f32e0d0" in notice
    assert "MIT License" in notice
    assert "Bluetooth" in readme and "falls back automatically" in readme
    assert "Bluetooth" in readme_zh and "自动回退" in readme_zh
