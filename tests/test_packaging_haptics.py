import ast
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_linux_hidraw_read_keeps_the_shared_hidapi_keyword_contract():
    source = (ROOT / "src/modules/dualsense/_hidraw.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    device = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "device"
    )
    read = next(
        node for node in device.body
        if isinstance(node, ast.FunctionDef) and node.name == "read"
    )

    assert [argument.arg for argument in read.args.args] == [
        "self",
        "size",
        "timeout_ms",
    ]


def test_runtime_and_development_dependencies_are_declared():
    metadata = tomllib.loads((ROOT / "src/pyproject.toml").read_text(encoding="utf-8"))
    dependencies = metadata["project"]["dependencies"]
    development = metadata["dependency-groups"]["dev"]

    assert any(value.startswith("numpy>=") for value in dependencies)
    assert any(value.startswith("sounddevice>=") for value in dependencies)
    assert any(value.startswith("pytest>=") for value in development)
    assert "pyinstaller==6.16.0" in development
    assert "pyrefly==1.1.1" in development


def test_runtime_does_not_load_configuration_from_the_launch_directory():
    main_source = (ROOT / "src/main.py").read_text(encoding="utf-8")
    metadata = tomllib.loads((ROOT / "src/pyproject.toml").read_text(encoding="utf-8"))

    assert "load_dotenv" not in main_source
    assert "dev.env" not in main_source
    assert not (ROOT / "src/dev.env").exists()
    assert not any("dotenv" in value for value in metadata["project"]["dependencies"])


def test_windows_and_release_builds_use_locked_audio_dependencies():
    batch = (ROOT / "packaging/windows/build_exe.bat").read_text(encoding="utf-8")
    linux = (ROOT / "packaging/linux/build_elf.sh").read_text(encoding="utf-8")
    pyproject = (ROOT / "src/pyproject.toml").read_text(encoding="utf-8")
    lock = (ROOT / "src/uv.lock").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "uv run --project src --frozen pyinstaller" in batch
    assert '"numpy>=2.1.0"' in pyproject
    assert '"sounddevice>=0.5.1"' in pyproject
    assert 'name = "numpy"' in lock
    assert 'name = "sounddevice"' in lock
    assert 'uv sync --project "$ROOT/src" --frozen' in linux
    assert 'uv run --project "$ROOT/src" --frozen --no-sync' in linux
    assert 'bash "$GITHUB_WORKSPACE/packaging/linux/build_elf.sh"' in workflow
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
    assert "ViGEmBus" in notice and "BSD 3-Clause License" in notice
    assert "ViGEmClient" in notice and "vgamepad" in notice
    assert "@hotline1337" in notice
    assert "9677E50BF04276A9606956819D7760588EA7B986CFAFEBC70396F35630C53A61" in notice
    assert "Bluetooth" in readme and "falls back automatically" in readme
    assert "Bluetooth" in readme_zh and "自动回退" in readme_zh
