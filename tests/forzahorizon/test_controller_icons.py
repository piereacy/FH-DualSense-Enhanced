import json
import multiprocessing
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
    original_copy = controller_icons.shutil.copy2

    def corrupt_second_backup_copy(source, target):
        if source.name == "original_1.zip":
            target.write_bytes(b"corrupt-after-copy")
            return
        original_copy(source, target)

    monkeypatch.setattr(controller_icons.shutil, "copy2", corrupt_second_backup_copy)

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
    original_copy = controller_icons.shutil.copy2

    def corrupt_second_install(source, target):
        original_copy(source, target)
        if source == paths.CONTROLLER_ICON_MOD:
            if "HiRes" in target.parts:
                target.write_bytes(b"corrupt-install")

    monkeypatch.setattr(controller_icons.shutil, "copy2", corrupt_second_install)

    with pytest.raises(controller_icons.ControllerIconModError, match="failed verification"):
        controller_icons.install_controller_icons(
            root, data_dir=data, game_running=lambda: False
        )
    assert [
        (root / relative).read_bytes() for relative in controller_icons.TARGETS
    ] == [b"normal", b"hires"]


@pytest.mark.parametrize("operation", ["install_controller_icons", "restore_controller_icons"])
@pytest.mark.parametrize("updated_index", [0, 1])
def test_partial_game_update_preserves_new_original_and_backup(
    tmp_path, operation, updated_index
):
    root = _game(tmp_path)
    data = tmp_path / "data"
    controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)
    backup_dir = controller_icons._backup_dir(root.resolve(), data)
    manifest_before = controller_icons._manifest_path(backup_dir).read_bytes()
    (root / controller_icons.TARGETS[updated_index]).write_bytes(b"new-game-original")
    before = [(root / relative).read_bytes() for relative in controller_icons.TARGETS]

    with pytest.raises(controller_icons.ControllerIconModError, match="Verify the game files"):
        getattr(controller_icons, operation)(root, data_dir=data, game_running=lambda: False)

    assert [(root / relative).read_bytes() for relative in controller_icons.TARGETS] == before
    assert controller_icons._manifest_path(backup_dir).read_bytes() == manifest_before
    assert controller_icons._read_manifest(root.resolve(), backup_dir) is not None


def test_restore_refuses_to_downgrade_a_complete_game_update(tmp_path):
    root = _game(tmp_path)
    data = tmp_path / "data"
    controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)
    for index, relative in enumerate(controller_icons.TARGETS):
        (root / relative).write_bytes(f"updated-{index}".encode())

    with pytest.raises(controller_icons.ControllerIconModError, match="changed game files"):
        controller_icons.restore_controller_icons(root, data_dir=data, game_running=lambda: False)

    controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)
    controller_icons.restore_controller_icons(root, data_dir=data, game_running=lambda: False)
    assert [(root / relative).read_bytes() for relative in controller_icons.TARGETS] == [
        b"updated-0", b"updated-1"
    ]


def test_known_original_and_mod_can_be_repaired_without_replacing_the_backup(tmp_path):
    root = _game(tmp_path)
    data = tmp_path / "data"
    controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)
    backup_dir = controller_icons._backup_dir(root.resolve(), data)
    manifest_before = controller_icons._manifest_path(backup_dir).read_bytes()
    (root / controller_icons.TARGETS[0]).write_bytes(b"normal")

    result = controller_icons.install_controller_icons(
        root, data_dir=data, game_running=lambda: False
    )

    assert result.state is controller_icons.ControllerIconState.INSTALLED
    assert controller_icons._manifest_path(backup_dir).read_bytes() == manifest_before
    controller_icons.restore_controller_icons(root, data_dir=data, game_running=lambda: False)
    assert [(root / relative).read_bytes() for relative in controller_icons.TARGETS] == [
        b"normal", b"hires"
    ]


def test_backup_refuses_files_changed_since_the_initial_hashes(tmp_path, monkeypatch):
    root = _game(tmp_path)
    data = tmp_path / "data"
    original_backup = controller_icons._write_backup

    def change_before_backup(root, backup_dir, expected_hashes):
        for relative in controller_icons.TARGETS:
            (root / relative).write_bytes(paths.CONTROLLER_ICON_MOD.read_bytes())
        return original_backup(root, backup_dir, expected_hashes)

    monkeypatch.setattr(controller_icons, "_write_backup", change_before_backup)

    with pytest.raises(controller_icons.ControllerIconModError, match="changed before backup"):
        controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)

    assert not any(data.rglob("manifest.json"))
    assert not any(data.rglob("original_*.zip"))


def test_manifest_cannot_claim_the_mod_is_an_original(tmp_path):
    root = _game(tmp_path)
    data = tmp_path / "data"
    controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)
    backup_dir = controller_icons._backup_dir(root.resolve(), data)
    manifest_path = controller_icons._manifest_path(backup_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for index in range(len(controller_icons.TARGETS)):
        controller_icons._backup_path(
            backup_dir, index, manifest["backup_generation"]
        ).write_bytes(paths.CONTROLLER_ICON_MOD.read_bytes())
    manifest["original_sha256"] = [controller_icons.MOD_SHA256] * 2
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert controller_icons.inspect_controller_icons(root, data_dir=data).has_backup is False
    with pytest.raises(controller_icons.ControllerIconModError, match="No verified original"):
        controller_icons.restore_controller_icons(root, data_dir=data, game_running=lambda: False)


@pytest.mark.parametrize("operation", ["install_controller_icons", "restore_controller_icons"])
def test_target_changed_while_staging_is_preserved(tmp_path, monkeypatch, operation):
    root = _game(tmp_path)
    data = tmp_path / "data"
    controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)
    if operation == "install_controller_icons":
        controller_icons.restore_controller_icons(root, data_dir=data, game_running=lambda: False)
    before_first = (root / controller_icons.TARGETS[0]).read_bytes()
    second = root / controller_icons.TARGETS[1]
    original_copy = controller_icons.shutil.copy2

    def update_second_while_staging(source, target):
        original_copy(source, target)
        if target.parent == second.parent:
            second.write_bytes(b"concurrent-game-update")

    monkeypatch.setattr(controller_icons.shutil, "copy2", update_second_while_staging)

    with pytest.raises(controller_icons.ControllerIconModError, match="changed during"):
        getattr(controller_icons, operation)(root, data_dir=data, game_running=lambda: False)

    assert (root / controller_icons.TARGETS[0]).read_bytes() == before_first
    assert second.read_bytes() == b"concurrent-game-update"


def test_rollback_preserves_an_update_to_an_already_replaced_target(tmp_path, monkeypatch):
    root = _game(tmp_path)
    data = tmp_path / "data"
    first, second = [root / relative for relative in controller_icons.TARGETS]
    original_copy = controller_icons.shutil.copy2

    def update_first_while_staging_second(source, target):
        original_copy(source, target)
        if source == paths.CONTROLLER_ICON_MOD and target.parent == second.parent:
            first.write_bytes(b"new-game-original")

    monkeypatch.setattr(controller_icons.shutil, "copy2", update_first_while_staging_second)

    with pytest.raises(controller_icons.ControllerIconModError, match="failed verification"):
        controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)

    assert first.read_bytes() == b"new-game-original"
    assert second.read_bytes() == b"hires"


def _install_with_backup_paused(root, data, ready, release):
    original_backup = controller_icons._write_backup

    def paused_backup(*args):
        ready.set()
        if not release.wait(15):
            raise RuntimeError("test did not release the icon installer")
        return original_backup(*args)

    controller_icons._write_backup = paused_backup
    controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)


@pytest.mark.parametrize("terminate_owner", [False, True])
def test_icon_transaction_excludes_other_processes_and_releases_on_exit(
    tmp_path, terminate_owner
):
    root = _game(tmp_path)
    data = tmp_path / "owner-data"
    other_data = tmp_path / "other-data"
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    owner = context.Process(target=_install_with_backup_paused, args=(root, data, ready, release))
    owner.start()
    try:
        assert ready.wait(15), "child installer never reached the locked transaction"
        for operation in (controller_icons.install_controller_icons, controller_icons.restore_controller_icons):
            with pytest.raises(controller_icons.ControllerIconModError, match="in progress"):
                operation(root / ".", data_dir=other_data, game_running=lambda: False)
        assert not other_data.exists()
        unrelated_root = _game(tmp_path / "other-installation")
        controller_icons.install_controller_icons(
            unrelated_root, data_dir=other_data, game_running=lambda: False
        )
        if terminate_owner:
            owner.terminate()
        else:
            release.set()
        owner.join(15)
        assert not owner.is_alive()
        if not terminate_owner:
            assert owner.exitcode == 0
    finally:
        # A terminated process may leave Event's condition semaphore locked.
        # Never touch that IPC object again after terminating its owner.
        if owner.is_alive():
            owner.terminate()
        owner.join(15)

    controller_icons.install_controller_icons(root, data_dir=data, game_running=lambda: False)
    controller_icons.restore_controller_icons(root, data_dir=data, game_running=lambda: False)
    assert [(root / relative).read_bytes() for relative in controller_icons.TARGETS] == [
        b"normal", b"hires"
    ]
