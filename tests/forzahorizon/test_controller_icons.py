from pathlib import Path

import pytest

from modules.config import paths
from modules.forzahorizon import controller_icons


def _game(tmp_path: Path, normal: bytes = b"normal", hires: bytes = b"hires") -> Path:
    root = tmp_path / "ForzaHorizon6"
    (root / "ForzaHorizon6.exe").parent.mkdir(parents=True)
    (root / "ForzaHorizon6.exe").write_bytes(b"MZ")
    for relative, payload in zip(
        controller_icons.TARGETS,
        (normal, hires),
        strict=True,
    ):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    return root


def test_bundled_mod_is_one_verified_archive_for_both_targets():
    assert paths.CONTROLLER_ICON_MOD.stat().st_size == 70_188
    assert controller_icons._sha256(paths.CONTROLLER_ICON_MOD) == controller_icons.MOD_SHA256
    assert len(controller_icons.TARGETS) == 2


def test_icon_root_accepts_an_xbox_game_wrapper_with_content_child(tmp_path):
    wrapper = tmp_path / "Xbox FH6"
    content = wrapper / "Content"
    content.mkdir(parents=True)
    (content / "ForzaHorizon6.exe").write_bytes(b"MZ")
    for relative in controller_icons.TARGETS:
        target = content / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"original")

    assert controller_icons.validate_controller_icon_root(wrapper) == content.resolve()


def test_windows_spec_bundles_one_mod_archive_and_linux_does_not():
    root = Path(__file__).resolve().parents[2]
    windows = (root / "packaging/windows/fhds.spec").read_text(encoding="utf-8")
    linux = (root / "packaging/linux/fhds.spec").read_text(encoding="utf-8")

    assert windows.count("ControllerIcons.zip") == 1
    assert "ControllerIcons.zip" not in linux


def test_install_backs_up_both_originals_and_restore_is_reversible(tmp_path):
    root = _game(tmp_path)
    data = tmp_path / "data"

    installed = controller_icons.install_controller_icons(
        root,
        data_dir=data,
        game_running=lambda: False,
    )

    assert installed.state is controller_icons.ControllerIconState.INSTALLED
    assert installed.has_backup is True
    assert [
        (root / relative).read_bytes() for relative in controller_icons.TARGETS
    ] == [paths.CONTROLLER_ICON_MOD.read_bytes()] * 2

    restored = controller_icons.restore_controller_icons(
        root,
        data_dir=data,
        game_running=lambda: False,
    )

    assert restored.state is controller_icons.ControllerIconState.READY
    assert restored.has_backup is True
    assert [
        (root / relative).read_bytes() for relative in controller_icons.TARGETS
    ] == [b"normal", b"hires"]


def test_game_update_refreshes_backup_before_reinstall(tmp_path):
    root = _game(tmp_path)
    data = tmp_path / "data"
    controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)
    controller_icons.restore_controller_icons(root, data_dir=data, game_running=lambda: False)
    for index, relative in enumerate(controller_icons.TARGETS):
        (root / relative).write_bytes(f"updated-{index}".encode())

    controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)
    controller_icons.restore_controller_icons(root, data_dir=data, game_running=lambda: False)

    assert [
        (root / relative).read_bytes() for relative in controller_icons.TARGETS
    ] == [b"updated-0", b"updated-1"]


def test_failed_backup_refresh_keeps_the_previous_verified_generation(
    tmp_path,
    monkeypatch,
):
    root = _game(tmp_path)
    data = tmp_path / "data"
    controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)
    controller_icons.restore_controller_icons(root, data_dir=data, game_running=lambda: False)
    backup_dir = controller_icons._backup_dir(root.resolve(), data)
    manifest_before = controller_icons._manifest_path(backup_dir).read_bytes()
    for index, relative in enumerate(controller_icons.TARGETS):
        (root / relative).write_bytes(f"updated-{index}".encode())

    original_copy = controller_icons._atomic_copy

    def corrupt_new_generation(source, target):
        original_copy(source, target)
        if "generations" in target.parts and target.name == "original_1.zip":
            target.write_bytes(b"corrupt-refresh")

    monkeypatch.setattr(controller_icons, "_atomic_copy", corrupt_new_generation)

    with pytest.raises(controller_icons.ControllerIconModError, match="backup 2"):
        controller_icons.install_controller_icons(
            root,
            data_dir=data,
            game_running=lambda: False,
        )

    assert controller_icons._manifest_path(backup_dir).read_bytes() == manifest_before
    assert controller_icons._read_manifest(root.resolve(), backup_dir) is not None
    assert len(list((backup_dir / "generations").iterdir())) == 1


def test_partial_manual_install_without_backup_is_not_treated_as_original(tmp_path):
    root = _game(tmp_path)
    (root / controller_icons.TARGETS[0]).write_bytes(paths.CONTROLLER_ICON_MOD.read_bytes())

    inspection = controller_icons.inspect_controller_icons(root, data_dir=tmp_path / "data")
    assert inspection.state is controller_icons.ControllerIconState.PARTIAL
    assert inspection.has_backup is False
    with pytest.raises(controller_icons.ControllerIconModError, match="no complete original backup"):
        controller_icons.install_controller_icons(
            root,
            data_dir=tmp_path / "data",
            game_running=lambda: False,
        )


def test_install_and_restore_refuse_to_modify_files_while_game_runs(tmp_path):
    root = _game(tmp_path)
    with pytest.raises(controller_icons.ControllerIconModError, match="Close FH6"):
        controller_icons.install_controller_icons(
            root,
            data_dir=tmp_path / "data",
            game_running=lambda: True,
        )


def test_validation_requires_fh6_executable_and_both_target_archives(tmp_path):
    root = _game(tmp_path)
    assert controller_icons.validate_controller_icon_root(root) == root.resolve()
    (root / controller_icons.TARGETS[1]).unlink()
    assert controller_icons.validate_controller_icon_root(root) is None


def test_restore_verification_failure_rolls_both_targets_back(tmp_path, monkeypatch):
    root = _game(tmp_path)
    data = tmp_path / "data"
    controller_icons.install_controller_icons(
        root, data_dir=data, game_running=lambda: False
    )
    before = [(root / relative).read_bytes() for relative in controller_icons.TARGETS]
    original_copy = controller_icons._atomic_copy

    def corrupt_second_backup_copy(source, target):
        if source.name == "original_1.zip":
            target.write_bytes(b"corrupt-after-copy")
            return
        original_copy(source, target)

    monkeypatch.setattr(controller_icons, "_atomic_copy", corrupt_second_backup_copy)

    with pytest.raises(controller_icons.ControllerIconModError, match="failed verification"):
        controller_icons.restore_controller_icons(
            root, data_dir=data, game_running=lambda: False
        )
    assert [
        (root / relative).read_bytes() for relative in controller_icons.TARGETS
    ] == before


def test_backup_copy_must_match_the_live_original(tmp_path, monkeypatch):
    root = _game(tmp_path)
    data = tmp_path / "data"
    original_copy = controller_icons._atomic_copy

    def corrupt_first_backup(source, target):
        original_copy(source, target)
        if target.name == "original_0.zip":
            target.write_bytes(b"corrupt-backup")

    monkeypatch.setattr(controller_icons, "_atomic_copy", corrupt_first_backup)

    with pytest.raises(controller_icons.ControllerIconModError, match="backup 1"):
        controller_icons.install_controller_icons(
            root, data_dir=data, game_running=lambda: False
        )
    assert not any(data.rglob("manifest.json"))


def test_install_verification_failure_restores_both_originals(tmp_path, monkeypatch):
    root = _game(tmp_path)
    data = tmp_path / "data"
    original_copy = controller_icons._atomic_copy

    def corrupt_second_install(source, target):
        original_copy(source, target)
        if source == paths.CONTROLLER_ICON_MOD and target.name == "ControllerIcons.zip":
            if "HiRes" in target.parts:
                target.write_bytes(b"corrupt-install")

    monkeypatch.setattr(controller_icons, "_atomic_copy", corrupt_second_install)

    with pytest.raises(controller_icons.ControllerIconModError, match="failed verification"):
        controller_icons.install_controller_icons(
            root, data_dir=data, game_running=lambda: False
        )
    assert [
        (root / relative).read_bytes() for relative in controller_icons.TARGETS
    ] == [b"normal", b"hires"]
