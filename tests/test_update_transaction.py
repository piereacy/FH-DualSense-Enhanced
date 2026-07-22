import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from modules.update.transaction import (
    TransactionError,
    TransactionPhase,
    UpdateTransaction,
    create_legacy_transaction,
    create_transaction,
    load_transaction,
    release_version,
    save_transaction,
    set_phase,
    write_health_ack,
)


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _create(tmp_path):
    install = tmp_path / "install"
    update_root = install / "data" / "updates" / "transactions"
    install.mkdir()
    old = install / "FH-DualSense-Enhanced-R6.exe"
    staged = install / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, path = create_transaction(
        root=update_root,
        staged=staged,
        target=old,
        expected_sha256=_digest(b"MZ-new"),
        pid=123,
        args=("--gui",),
        now=100.0,
        transaction_id="a" * 32,
        token="test-token-with-at-least-24-bytes",
    )
    return transaction, path, old, staged, update_root


def test_transaction_uses_canonical_side_by_side_paths_and_round_trips(tmp_path):
    transaction, path, old, staged, _root = _create(tmp_path)

    assert transaction.phase is TransactionPhase.PREPARED
    assert transaction.old == old.resolve()
    assert transaction.new == old.with_name("FH-DualSense-Enhanced-R7.exe").resolve()
    assert transaction.staged == staged.resolve()
    assert transaction.old_sha256 == _digest(b"MZ-old")
    assert transaction.new_sha256 == _digest(b"MZ-new")
    assert load_transaction(path) == transaction
    assert not path.with_suffix(".tmp").exists()


def test_transaction_phase_is_atomically_persisted(tmp_path):
    _transaction, path, _old, _staged, _root = _create(tmp_path)

    updated = set_phase(path, TransactionPhase.WAITING_HEALTH)

    assert updated.phase is TransactionPhase.WAITING_HEALTH
    assert load_transaction(path).phase is TransactionPhase.WAITING_HEALTH


@pytest.mark.parametrize(
    ("name", "version"),
    [
        ("FH-DualSense-Enhanced-R7.exe", 7),
        ("fh-dualsense-enhanced-r12.EXE", 12),
    ],
)
def test_release_version_accepts_only_the_canonical_name(name, version):
    assert release_version(name) == version


@pytest.mark.parametrize(
    "name",
    ["R7.exe", "FH-DualSense-Enhanced-R0.exe", "FH-DualSense-Enhanced-R7-old.exe"],
)
def test_release_version_rejects_ambiguous_names(name):
    with pytest.raises(TransactionError, match="non-canonical"):
        release_version(name)


def test_transaction_rejects_tampering_and_wrong_storage_directory(tmp_path):
    transaction, path, _old, _staged, _root = _create(tmp_path)
    payload = transaction.to_dict()
    payload["new_path"] = str(transaction.old)
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(TransactionError, match="overlap"):
        load_transaction(path)

    other = path.parent.parent / ("b" * 32) / "transaction.json"
    other.parent.mkdir()
    other.write_text(json.dumps(transaction.to_dict()), encoding="utf-8")
    with pytest.raises(TransactionError, match="wrong directory"):
        load_transaction(other)


def test_save_revalidates_replaced_transaction(tmp_path):
    transaction, path, _old, _staged, _root = _create(tmp_path)
    invalid = replace(transaction, new_sha256="not-a-hash")

    with pytest.raises(TransactionError, match="checksum"):
        save_transaction(path, invalid)


def test_health_ack_binds_token_pid_version_path_and_hash(tmp_path):
    transaction, path, _old, staged, root = _create(tmp_path)
    staged.replace(transaction.new)

    health_path = write_health_ack(
        root=root,
        transaction_id=transaction.transaction_id,
        token=transaction.token,
        executable=transaction.new,
        version=7,
        pid=456,
        initialized_at=200.0,
    )

    payload = json.loads(health_path.read_text(encoding="utf-8"))
    assert payload == {
        "schema": 1,
        "transaction_id": transaction.transaction_id,
        "token": transaction.token,
        "pid": 456,
        "version": 7,
        "executable": str(transaction.new),
        "sha256": transaction.new_sha256,
        "initialized_at": 200.0,
    }
    assert path.is_file()


def test_health_ack_rejects_wrong_token_and_modified_executable(tmp_path):
    transaction, _path, _old, staged, root = _create(tmp_path)
    staged.replace(transaction.new)

    with pytest.raises(TransactionError, match="token"):
        write_health_ack(
            root=root,
            transaction_id=transaction.transaction_id,
            token="wrong-token-with-at-least-24-bytes",
            executable=transaction.new,
            version=7,
        )

    transaction.new.write_bytes(b"MZ-tampered")
    with pytest.raises(TransactionError, match="checksum"):
        write_health_ack(
            root=root,
            transaction_id=transaction.transaction_id,
            token=transaction.token,
            executable=transaction.new,
            version=7,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("pid", 0, "pid"),
        ("initialized_at", float("nan"), "timestamp"),
        ("initialized_at", float("inf"), "timestamp"),
    ],
)
def test_health_ack_rejects_invalid_runtime_identity(tmp_path, field, value, message):
    transaction, _path, _old, staged, root = _create(tmp_path)
    staged.replace(transaction.new)
    kwargs = {"pid": 456, "initialized_at": 200.0}
    kwargs[field] = value

    with pytest.raises(TransactionError, match=message):
        write_health_ack(
            root=root,
            transaction_id=transaction.transaction_id,
            token=transaction.token,
            executable=transaction.new,
            version=7,
            **kwargs,
        )


def test_create_transaction_rejects_non_newer_or_changed_staged_file(tmp_path):
    install = tmp_path / "install"
    install.mkdir()
    target = install / "FH-DualSense-Enhanced-R7.exe"
    staged = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    target.write_bytes(b"old")
    staged.write_bytes(b"new")

    with pytest.raises(TransactionError, match="newer"):
        create_transaction(
            root=tmp_path / "transactions",
            staged=staged,
            target=target,
            expected_sha256=_digest(b"new"),
            pid=1,
        )

    staged = tmp_path / "FH-DualSense-Enhanced-R8.exe"
    staged.write_bytes(b"changed")
    with pytest.raises(TransactionError, match="checksum"):
        create_transaction(
            root=tmp_path / "transactions",
            staged=staged,
            target=target,
            expected_sha256="0" * 64,
            pid=1,
        )


def test_transaction_parser_rejects_unknown_schema(tmp_path):
    transaction, path, _old, _staged, _root = _create(tmp_path)
    payload = transaction.to_dict()
    payload["schema"] = 99
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(TransactionError, match="unsupported"):
        load_transaction(path)


def test_transaction_from_dict_rejects_non_string_args(tmp_path):
    transaction, _path, _old, _staged, _root = _create(tmp_path)
    payload = transaction.to_dict()
    payload["args"] = ["--gui", 1]

    with pytest.raises(TransactionError, match="malformed"):
        UpdateTransaction.from_dict(payload)


@pytest.mark.parametrize("created_at", [float("nan"), float("inf"), float("-inf"), 0.0])
def test_transaction_from_dict_rejects_invalid_timestamp(tmp_path, created_at):
    transaction, _path, _old, _staged, _root = _create(tmp_path)
    payload = transaction.to_dict()
    payload["created_at"] = created_at

    with pytest.raises(TransactionError, match="timestamp"):
        UpdateTransaction.from_dict(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", "1"),
        ("pid", "123"),
        ("old_version", True),
        ("token", 123),
        ("old_path", 123),
    ],
)
def test_transaction_from_dict_rejects_coerced_scalar_fields(tmp_path, field, value):
    transaction, _path, _old, _staged, _root = _create(tmp_path)
    payload = transaction.to_dict()
    payload[field] = value

    with pytest.raises(TransactionError, match="malformed"):
        UpdateTransaction.from_dict(payload)


@pytest.mark.parametrize("field", ["legacy_r6_bootstrap", "shortcut_warning_shown"])
def test_transaction_from_dict_rejects_truthy_non_boolean_flags(tmp_path, field):
    transaction, _path, _old, _staged, _root = _create(tmp_path)
    payload = transaction.to_dict()
    payload[field] = "false"

    with pytest.raises(TransactionError, match="boolean"):
        UpdateTransaction.from_dict(payload)


def test_legacy_transaction_binds_wrong_name_backup_and_canonical_new_path(tmp_path):
    install = tmp_path / "install"
    update_root = install / "data" / "updates"
    install.mkdir()
    running = install / "FH-DualSense-Enhanced-R6.exe"
    backup = Path(str(running) + ".old")
    staged = update_root / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    running.write_bytes(b"MZ-r7")
    staged.write_bytes(b"MZ-r7")
    backup.write_bytes(b"MZ-r6")

    transaction, plan = create_legacy_transaction(
        root=update_root / "transactions",
        staged=staged,
        wrong_named_executable=running,
        backup=backup,
        new_version=7,
        pid=123,
        now=100.0,
        transaction_id="c" * 32,
        token="legacy-test-token-with-24-bytes",
    )

    assert transaction.legacy_r6_bootstrap is True
    assert transaction.legacy_backup_path == str(backup.resolve())
    assert transaction.old == running.resolve()
    assert transaction.new == install / "FH-DualSense-Enhanced-R7.exe"
    assert transaction.old_sha256 == _digest(b"MZ-r6")
    assert transaction.new_sha256 == _digest(b"MZ-r7")
    assert load_transaction(plan) == transaction


def test_legacy_transaction_rejects_manual_rename_without_matching_backup(tmp_path):
    install = tmp_path / "install"
    update_root = install / "data" / "updates"
    install.mkdir()
    running = install / "FH-DualSense-Enhanced-R6.exe"
    wrong_backup = install / "unrelated.old"
    staged = update_root / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    running.write_bytes(b"MZ-r7")
    staged.write_bytes(b"MZ-r7")
    wrong_backup.write_bytes(b"MZ-r6")

    with pytest.raises(TransactionError, match="backup path"):
        create_legacy_transaction(
            root=update_root / "transactions",
            staged=staged,
            wrong_named_executable=running,
            backup=wrong_backup,
            new_version=7,
            pid=123,
        )
