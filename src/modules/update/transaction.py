from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import time
import uuid
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = 1
_TRANSACTION_ID = re.compile(r"^[0-9a-f]{32}$")
_RELEASE_EXE = re.compile(r"^FH-DualSense-Enhanced-R([1-9][0-9]*)\.exe$", re.IGNORECASE)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class TransactionError(ValueError):
    """Raised when an update transaction cannot be trusted."""


class TransactionPhase(StrEnum):
    PREPARED = "prepared"
    WAITING_OLD_EXIT = "waiting_old_exit"
    NEW_INSTALLED = "new_installed"
    WAITING_HEALTH = "waiting_health"
    SHORTCUTS_MIGRATING = "shortcuts_migrating"
    CLEANUP_PENDING = "cleanup_pending"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True, slots=True)
class UpdateTransaction:
    transaction_id: str
    phase: TransactionPhase
    old_path: str
    new_path: str
    staged_path: str
    old_version: int
    new_version: int
    old_sha256: str
    new_sha256: str
    pid: int
    args: tuple[str, ...]
    created_at: float
    token: str
    legacy_r6_bootstrap: bool = False
    legacy_backup_path: str = ""
    migrated_shortcuts: tuple[str, ...] = ()
    failed_shortcuts: tuple[str, ...] = ()
    shortcut_warning_shown: bool = False
    schema: int = SCHEMA_VERSION

    @property
    def directory_name(self) -> str:
        return self.transaction_id

    @property
    def old(self) -> Path:
        return Path(self.old_path)

    @property
    def new(self) -> Path:
        return Path(self.new_path)

    @property
    def staged(self) -> Path:
        return Path(self.staged_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "transaction_id": self.transaction_id,
            "phase": self.phase.value,
            "old_path": self.old_path,
            "new_path": self.new_path,
            "staged_path": self.staged_path,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "old_sha256": self.old_sha256,
            "new_sha256": self.new_sha256,
            "pid": self.pid,
            "args": list(self.args),
            "created_at": self.created_at,
            "token": self.token,
            "legacy_r6_bootstrap": self.legacy_r6_bootstrap,
            "legacy_backup_path": self.legacy_backup_path,
            "migrated_shortcuts": list(self.migrated_shortcuts),
            "failed_shortcuts": list(self.failed_shortcuts),
            "shortcut_warning_shown": self.shortcut_warning_shown,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> UpdateTransaction:
        exact_strings = (
            "transaction_id",
            "phase",
            "old_path",
            "new_path",
            "staged_path",
            "old_sha256",
            "new_sha256",
            "token",
        )
        exact_integers = ("schema", "old_version", "new_version", "pid")
        if any(not isinstance(payload.get(name), str) for name in exact_strings):
            raise TransactionError("update transaction string fields are malformed")
        if any(type(payload.get(name)) is not int for name in exact_integers):
            raise TransactionError("update transaction integer fields are malformed")
        created_value = payload.get("created_at")
        if isinstance(created_value, bool) or not isinstance(created_value, (int, float)):
            raise TransactionError("update transaction timestamp is malformed")
        legacy_backup_value = payload.get("legacy_backup_path", "")
        if not isinstance(legacy_backup_value, str):
            raise TransactionError("legacy update backup path is malformed")
        for name in ("legacy_r6_bootstrap", "shortcut_warning_shown"):
            value = payload.get(name, False)
            if not isinstance(value, bool):
                raise TransactionError(f"{name} must be a boolean")
        try:
            schema = payload["schema"]
            transaction_id = payload["transaction_id"]
            phase = TransactionPhase(payload["phase"])
            old_path = payload["old_path"]
            new_path = payload["new_path"]
            staged_path = payload["staged_path"]
            old_version = payload["old_version"]
            new_version = payload["new_version"]
            old_sha256 = payload["old_sha256"].lower()
            new_sha256 = payload["new_sha256"].lower()
            pid = payload["pid"]
            args = _string_tuple(payload.get("args", ()), "args")
            created_at = float(created_value)
            token = payload["token"]
            legacy = payload.get("legacy_r6_bootstrap", False)
            legacy_backup_path = legacy_backup_value
            migrated = _string_tuple(payload.get("migrated_shortcuts", ()), "migrated_shortcuts")
            failed = _string_tuple(payload.get("failed_shortcuts", ()), "failed_shortcuts")
            shortcut_warning_shown = payload.get("shortcut_warning_shown", False)
        except (KeyError, TypeError, ValueError) as exc:
            raise TransactionError("update transaction is malformed") from exc

        if schema != SCHEMA_VERSION:
            raise TransactionError(f"unsupported update transaction schema: {schema}")
        if not _TRANSACTION_ID.fullmatch(transaction_id):
            raise TransactionError("invalid update transaction id")
        if not token or len(token) < 24 or len(token) > 256:
            raise TransactionError("invalid update transaction token")
        if pid <= 0:
            raise TransactionError("invalid update transaction pid")
        if old_version <= 0 or new_version <= old_version:
            raise TransactionError("invalid update version transition")
        if not _SHA256.fullmatch(old_sha256) or not _SHA256.fullmatch(new_sha256):
            raise TransactionError("invalid update transaction checksum")
        if not math.isfinite(created_at) or created_at <= 0:
            raise TransactionError("invalid update transaction timestamp")

        old_raw = Path(old_path)
        new_raw = Path(new_path)
        staged_raw = Path(staged_path)
        if not old_raw.is_absolute() or not new_raw.is_absolute() or not staged_raw.is_absolute():
            raise TransactionError("update transaction paths must be absolute")
        old = old_raw.resolve()
        new = new_raw.resolve()
        staged = staged_raw.resolve()
        if old == new or staged in (old, new):
            raise TransactionError("update transaction paths overlap")
        if old.parent != new.parent:
            raise TransactionError("old and new executables must share an install directory")
        if release_version(old.name) != old_version or release_version(new.name) != new_version:
            raise TransactionError("update executable name does not match its version")
        if legacy:
            backup = Path(legacy_backup_path)
            if not backup.is_absolute() or backup.resolve() != Path(str(old) + ".old").resolve():
                raise TransactionError("legacy update backup path is invalid")
        elif legacy_backup_path:
            raise TransactionError("normal update must not contain a legacy backup path")

        return cls(
            transaction_id=transaction_id,
            phase=phase,
            old_path=str(old),
            new_path=str(new),
            staged_path=str(staged),
            old_version=old_version,
            new_version=new_version,
            old_sha256=old_sha256,
            new_sha256=new_sha256,
            pid=pid,
            args=args,
            created_at=created_at,
            token=token,
            legacy_r6_bootstrap=legacy,
            legacy_backup_path=legacy_backup_path,
            migrated_shortcuts=migrated,
            failed_shortcuts=failed,
            shortcut_warning_shown=shortcut_warning_shown,
            schema=schema,
        )


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(item, str) for item in value):
        raise TransactionError(f"{field} must contain only strings")
    return tuple(value)


def release_version(name: str) -> int:
    match = _RELEASE_EXE.fullmatch(name)
    if not match:
        raise TransactionError(f"non-canonical release executable name: {name}")
    return int(match.group(1))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def transaction_path(root: Path, transaction_id: str) -> Path:
    if not _TRANSACTION_ID.fullmatch(transaction_id):
        raise TransactionError("invalid update transaction id")
    return Path(root).resolve() / transaction_id / "transaction.json"


def create_transaction(
    *,
    root: Path,
    staged: Path,
    target: Path,
    expected_sha256: str,
    pid: int,
    args: Iterable[str] = (),
    now: float | None = None,
    transaction_id: str | None = None,
    token: str | None = None,
) -> tuple[UpdateTransaction, Path]:
    staged = Path(staged).resolve()
    target = Path(target).resolve()
    if not staged.is_file() or not target.is_file():
        raise FileNotFoundError(staged if not staged.is_file() else target)
    new_version = release_version(staged.name)
    old_version = release_version(target.name)
    if new_version <= old_version:
        raise TransactionError("update version must be newer than the running version")
    expected = str(expected_sha256).lower()
    if not _SHA256.fullmatch(expected) or sha256_file(staged).lower() != expected:
        raise TransactionError("staged update checksum changed")
    txid = transaction_id or uuid.uuid4().hex
    secret = token or secrets.token_urlsafe(32)
    new_target = target.with_name(staged.name)
    transaction = UpdateTransaction(
        transaction_id=txid,
        phase=TransactionPhase.PREPARED,
        old_path=str(target),
        new_path=str(new_target),
        staged_path=str(staged),
        old_version=old_version,
        new_version=new_version,
        old_sha256=sha256_file(target),
        new_sha256=expected,
        pid=int(pid),
        args=tuple(str(item) for item in args),
        created_at=float(time.time() if now is None else now),
        token=secret,
    )
    # Re-parse before persisting so generated data follows the same trust path
    # as a transaction loaded by a later process.
    transaction = UpdateTransaction.from_dict(transaction.to_dict())
    plan_path = transaction_path(root, transaction.transaction_id)
    atomic_write_json(plan_path, transaction.to_dict())
    return transaction, plan_path


def create_legacy_transaction(
    *,
    root: Path,
    staged: Path,
    wrong_named_executable: Path,
    backup: Path,
    new_version: int,
    pid: int,
    args: Iterable[str] = (),
    now: float | None = None,
    transaction_id: str | None = None,
    token: str | None = None,
) -> tuple[UpdateTransaction, Path]:
    """Create the second-stage transaction needed by the already shipped R6 helper."""
    staged = Path(staged).resolve()
    wrong_named_executable = Path(wrong_named_executable).resolve()
    backup = Path(backup).resolve()
    if not staged.is_file() or not wrong_named_executable.is_file() or not backup.is_file():
        missing = next(
            path for path in (staged, wrong_named_executable, backup) if not path.is_file()
        )
        raise FileNotFoundError(missing)
    old_version = release_version(wrong_named_executable.name)
    new_version = int(new_version)
    if new_version <= old_version or release_version(staged.name) != new_version:
        raise TransactionError("legacy update version transition is invalid")
    if backup != Path(str(wrong_named_executable) + ".old").resolve():
        raise TransactionError("legacy update backup path is invalid")
    new_digest = sha256_file(staged)
    if sha256_file(wrong_named_executable) != new_digest:
        raise TransactionError("legacy running executable does not match staged R7 bytes")
    txid = transaction_id or uuid.uuid4().hex
    secret = token or secrets.token_urlsafe(32)
    transaction = UpdateTransaction(
        transaction_id=txid,
        phase=TransactionPhase.PREPARED,
        old_path=str(wrong_named_executable),
        new_path=str(wrong_named_executable.with_name(staged.name)),
        staged_path=str(staged),
        old_version=old_version,
        new_version=new_version,
        old_sha256=sha256_file(backup),
        new_sha256=new_digest,
        pid=int(pid),
        args=tuple(str(item) for item in args),
        created_at=float(time.time() if now is None else now),
        token=secret,
        legacy_r6_bootstrap=True,
        legacy_backup_path=str(backup),
    )
    transaction = UpdateTransaction.from_dict(transaction.to_dict())
    plan_path = transaction_path(root, transaction.transaction_id)
    atomic_write_json(plan_path, transaction.to_dict())
    return transaction, plan_path


def load_transaction(path: Path) -> UpdateTransaction:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TransactionError("could not read update transaction") from exc
    if not isinstance(payload, dict):
        raise TransactionError("update transaction must be a JSON object")
    transaction = UpdateTransaction.from_dict(payload)
    if path.resolve() != transaction_path(path.parent.parent, transaction.transaction_id):
        raise TransactionError("update transaction is stored in the wrong directory")
    return transaction


def save_transaction(path: Path, transaction: UpdateTransaction) -> None:
    trusted = UpdateTransaction.from_dict(transaction.to_dict())
    if Path(path).resolve() != transaction_path(Path(path).parent.parent, trusted.transaction_id):
        raise TransactionError("update transaction is stored in the wrong directory")
    atomic_write_json(Path(path), trusted.to_dict())


def set_phase(path: Path, phase: TransactionPhase, **changes: Any) -> UpdateTransaction:
    current = load_transaction(path)
    updated = replace(current, phase=phase, **changes)
    save_transaction(path, updated)
    return updated


def write_health_ack(
    *,
    root: Path,
    transaction_id: str,
    token: str,
    executable: Path,
    version: int,
    pid: int | None = None,
    initialized_at: float | None = None,
) -> Path:
    plan_path = transaction_path(root, transaction_id)
    transaction = load_transaction(plan_path)
    executable = Path(executable).resolve()
    if not secrets.compare_digest(transaction.token, str(token)):
        raise TransactionError("update health token does not match")
    if executable != transaction.new or int(version) != transaction.new_version:
        raise TransactionError("update health executable does not match")
    if not executable.is_file() or sha256_file(executable).lower() != transaction.new_sha256:
        raise TransactionError("update health executable checksum does not match")
    health_pid = int(os.getpid() if pid is None else pid)
    health_time = float(time.time() if initialized_at is None else initialized_at)
    if health_pid <= 0:
        raise TransactionError("update health pid is invalid")
    if not math.isfinite(health_time) or health_time <= 0.0:
        raise TransactionError("update health timestamp is invalid")
    health = {
        "schema": SCHEMA_VERSION,
        "transaction_id": transaction.transaction_id,
        "token": transaction.token,
        "pid": health_pid,
        "version": transaction.new_version,
        "executable": str(executable),
        "sha256": transaction.new_sha256,
        "initialized_at": health_time,
    }
    health_path = plan_path.with_name("health.json")
    atomic_write_json(health_path, health)
    return health_path
