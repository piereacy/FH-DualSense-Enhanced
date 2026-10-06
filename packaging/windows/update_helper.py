"""Transactional Windows self-update helper, packaged separately from the app."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import psutil


SCHEMA_VERSION = 1
PHASES = {
    "prepared",
    "waiting_old_exit",
    "new_installed",
    "waiting_health",
    "shortcuts_migrating",
    "cleanup_pending",
    "committed",
    "rolled_back",
}
_CANONICAL_EXE_RE = re.compile(
    r"^FH-DualSense-Enhanced-R(?P<version>[1-9][0-9]*)\.exe$",
    re.IGNORECASE,
)
_STALE_RELEASE_FILE_RE = re.compile(
    r"^FH-DualSense-Enhanced-R(?P<version>[1-9][0-9]*)\.exe(?:\.old|\.sha256)$",
    re.IGNORECASE,
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_POPEN_CLASS = subprocess.Popen


class _UnconfirmedLaunchError(RuntimeError):
    """Launching failed without confirming that all candidate processes stopped."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_matches(path: Path, expected_sha256: str) -> bool:
    try:
        return path.is_file() and sha256(path).lower() == expected_sha256
    except OSError:
        return False


@contextmanager
def _transaction_lock(plan_path: Path):
    """Hold one crash-safe, cross-process lock for a transaction journal."""
    resolved = Path(plan_path).resolve()
    lock_key = hashlib.sha256(
        os.path.normcase(str(resolved)).encode("utf-8")
    ).hexdigest()
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_mutex = kernel32.CreateMutexW
        create_mutex.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        create_mutex.restype = wintypes.HANDLE
        wait_for_single_object = kernel32.WaitForSingleObject
        wait_for_single_object.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        wait_for_single_object.restype = wintypes.DWORD
        release_mutex = kernel32.ReleaseMutex
        release_mutex.argtypes = (wintypes.HANDLE,)
        release_mutex.restype = wintypes.BOOL
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (wintypes.HANDLE,)
        close_handle.restype = wintypes.BOOL

        handle = create_mutex(None, False, f"Local\\FHDS-Update-{lock_key}")
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        acquired = False
        try:
            result = wait_for_single_object(handle, 0)
            if result == 0x00000102:  # WAIT_TIMEOUT
                yield False
                return
            if result not in (0x00000000, 0x00000080):  # WAIT_OBJECT_0 / WAIT_ABANDONED
                raise OSError(f"WaitForSingleObject failed with result 0x{result:08x}")
            acquired = True
            yield True
        finally:
            if acquired:
                release_mutex(handle)
            close_handle(handle)
        return

    import fcntl

    lock_path = resolved.with_name("transaction.lock")
    with lock_path.open("a+b") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _load_plan(plan_path: Path) -> dict[str, Any]:
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("could not read update transaction") from exc
    if not isinstance(plan, dict):
        raise ValueError("update transaction must be a JSON object")
    if type(plan.get("schema")) is not int or plan["schema"] != SCHEMA_VERSION:
        raise ValueError("unsupported update transaction schema")
    required = {
        "transaction_id",
        "phase",
        "old_path",
        "new_path",
        "staged_path",
        "old_version",
        "new_version",
        "old_sha256",
        "new_sha256",
        "pid",
        "args",
        "created_at",
        "token",
    }
    if not required.issubset(plan):
        raise ValueError("update transaction is incomplete")
    if plan["phase"] not in PHASES:
        raise ValueError("update transaction phase is invalid")
    if not isinstance(plan["args"], list) or any(not isinstance(arg, str) for arg in plan["args"]):
        raise ValueError("update transaction arguments are invalid")
    for field in ("migrated_shortcuts", "failed_shortcuts"):
        value = plan.get(field, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"update transaction {field} is invalid")
    transaction_id = plan["transaction_id"]
    if not isinstance(transaction_id, str):
        raise ValueError("update transaction id is invalid")
    if len(transaction_id) != 32 or any(char not in "0123456789abcdef" for char in transaction_id):
        raise ValueError("update transaction id is invalid")
    token = plan["token"]
    if not isinstance(token, str):
        raise ValueError("update transaction token is invalid")
    if len(token) < 24 or len(token) > 256:
        raise ValueError("update transaction token is invalid")

    if any(not isinstance(plan[field], str) for field in ("old_path", "new_path", "staged_path")):
        raise ValueError("update transaction paths are invalid")
    old_raw = Path(plan["old_path"])
    new_raw = Path(plan["new_path"])
    staged_raw = Path(plan["staged_path"])
    if not old_raw.is_absolute() or not new_raw.is_absolute() or not staged_raw.is_absolute():
        raise ValueError("update transaction paths must be absolute")
    old = old_raw.resolve()
    new = new_raw.resolve()
    staged = staged_raw.resolve()
    if old == new or staged in (old, new) or old.parent != new.parent:
        raise ValueError("update transaction paths are invalid")
    resolved_plan = plan_path.resolve()
    if resolved_plan.name != "transaction.json" or resolved_plan.parent.name != transaction_id:
        raise ValueError("update transaction is stored in the wrong directory")
    if staged.parent != resolved_plan.parent.parent.parent:
        raise ValueError("staged update is stored outside the update directory")

    for field in ("pid", "old_version", "new_version"):
        if type(plan[field]) is not int:
            raise ValueError(f"update transaction {field} is invalid")
    created_value = plan["created_at"]
    if isinstance(created_value, bool) or not isinstance(created_value, (int, float)):
        raise ValueError("update transaction timestamp is invalid")
    try:
        pid = plan["pid"]
        old_version = plan["old_version"]
        new_version = plan["new_version"]
        created_at = float(created_value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("update transaction numeric fields are invalid") from exc
    if pid <= 0 or old_version <= 0 or new_version <= old_version:
        raise ValueError("update version transition or pid is invalid")
    if not math.isfinite(created_at) or created_at <= 0.0:
        raise ValueError("update transaction timestamp is invalid")

    old_sha256 = plan["old_sha256"]
    new_sha256 = plan["new_sha256"]
    if not isinstance(old_sha256, str) or not isinstance(new_sha256, str):
        raise ValueError("update transaction checksums are invalid")
    old_sha256 = old_sha256.lower()
    new_sha256 = new_sha256.lower()
    if not _SHA256_RE.fullmatch(old_sha256) or not _SHA256_RE.fullmatch(new_sha256):
        raise ValueError("update transaction checksums are invalid")

    if new.name.lower() != f"fh-dualsense-enhanced-r{new_version}.exe":
        raise ValueError("new executable does not use its canonical name")
    if old.name.lower() != f"fh-dualsense-enhanced-r{old_version}.exe":
        raise ValueError("old executable does not use its canonical name")
    legacy_value = plan.get("legacy_r6_bootstrap", False)
    warning_value = plan.get("shortcut_warning_shown", False)
    if not isinstance(legacy_value, bool) or not isinstance(warning_value, bool):
        raise ValueError("update transaction boolean fields are invalid")
    legacy = legacy_value
    legacy_backup_value = plan.get("legacy_backup_path", "")
    if not isinstance(legacy_backup_value, str):
        raise ValueError("legacy update backup path is invalid")
    legacy_backup = legacy_backup_value
    if legacy:
        backup = Path(legacy_backup).resolve()
        if backup != Path(str(old) + ".old").resolve():
            raise ValueError("legacy update backup path is invalid")
        plan["legacy_backup_path"] = str(backup)
    elif legacy_backup:
        raise ValueError("normal update contains a legacy backup path")
    plan["legacy_r6_bootstrap"] = legacy
    plan["shortcut_warning_shown"] = warning_value

    plan["old_path"] = str(old)
    plan["new_path"] = str(new)
    plan["staged_path"] = str(staged)
    plan["pid"] = pid
    plan["old_version"] = old_version
    plan["new_version"] = new_version
    plan["created_at"] = created_at
    plan["old_sha256"] = old_sha256
    plan["new_sha256"] = new_sha256
    return plan


def _set_phase(plan_path: Path, plan: dict[str, Any], phase: str, **changes: Any) -> None:
    if phase not in PHASES:
        raise ValueError(f"unknown update transaction phase: {phase}")
    plan.update(changes)
    plan["phase"] = phase
    _atomic_write_json(plan_path, plan)


def _wait_for_pid_windows(pid: int, timeout: float) -> None:
    """Wait for a process without ever using a signalling API."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_process.restype = wintypes.HANDLE
    wait_for_single_object = kernel32.WaitForSingleObject
    wait_for_single_object.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    wait_for_single_object.restype = wintypes.DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = (wintypes.HANDLE,)
    close_handle.restype = wintypes.BOOL

    synchronize = 0x00100000
    wait_object_0 = 0x00000000
    wait_timeout = 0x00000102
    error_invalid_parameter = 87
    error_access_denied = 5
    handle = open_process(synchronize, False, int(pid))
    if not handle:
        error = ctypes.get_last_error()
        if error == error_invalid_parameter:
            return
        if error == error_access_denied:
            raise PermissionError(error, f"access denied while opening process {pid}")
        raise OSError(error, f"OpenProcess failed for process {pid}")
    try:
        result = wait_for_single_object(handle, max(0, int(timeout * 1000)))
    finally:
        close_handle(handle)
    if result == wait_object_0:
        return
    if result == wait_timeout:
        raise TimeoutError(f"process {pid} did not exit")
    raise OSError(f"WaitForSingleObject failed with result 0x{result:08x}")


def wait_for_pid(pid: int, timeout: float = 30.0) -> None:
    if os.name == "nt":
        _wait_for_pid_windows(pid, timeout)
        return
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.2)
    raise TimeoutError(f"process {pid} did not exit")


def _process_running(process) -> bool:
    poll = getattr(process, "poll", None)
    return not callable(poll) or poll() is None


def _read_valid_health(
    plan_path: Path,
    plan: dict[str, Any],
    *,
    expected_pid: int | None = None,
) -> dict[str, Any] | None:
    health_path = plan_path.with_name("health.json")
    try:
        health = json.loads(health_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(health, dict):
        return None
    expected = {
        "schema": SCHEMA_VERSION,
        "transaction_id": plan["transaction_id"],
        "token": plan["token"],
        "version": plan["new_version"],
        "executable": plan["new_path"],
        "sha256": plan["new_sha256"],
    }
    if expected_pid is not None:
        expected["pid"] = int(expected_pid)
    if not all(health.get(key) == value for key, value in expected.items()):
        return None
    if type(health.get("schema")) is not int or type(health.get("version")) is not int:
        return None
    if type(health.get("pid")) is not int or int(health["pid"]) <= 0:
        return None
    initialized_at = health.get("initialized_at")
    if isinstance(initialized_at, bool) or not isinstance(initialized_at, (int, float)):
        return None
    try:
        timestamp = float(initialized_at)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(timestamp) or timestamp <= 0.0:
        return None
    new = Path(plan["new_path"])
    try:
        if not new.is_file() or sha256(new).lower() != plan["new_sha256"]:
            return None
    except OSError:
        return None
    return health


def _health_process_is_running(
    plan_path: Path,
    plan: dict[str, Any],
    *,
    health: dict[str, Any] | None = None,
) -> bool:
    health = _read_valid_health(plan_path, plan) if health is None else health
    if health is None:
        return False
    try:
        process = psutil.Process(int(health["pid"]))
        if not process.is_running():
            return False
        running_path = Path(process.exe()).resolve()
        expected_path = Path(plan["new_path"]).resolve()
        return os.path.normcase(str(running_path)) == os.path.normcase(str(expected_path))
    except psutil.AccessDenied:
        # Access denied is not evidence that the ACK process died. Preserving
        # the healthy candidate is safer than rolling it back underneath a
        # protected process.
        return True
    except (KeyError, TypeError, ValueError, OSError, psutil.Error):
        return False


def _observe_recovery_health(
    plan_path: Path,
    plan: dict[str, Any],
    *,
    survival_seconds: float,
) -> bool:
    health = _read_valid_health(plan_path, plan)
    if health is None:
        return False
    deadline = time.monotonic() + max(0.0, survival_seconds)
    while True:
        if not _health_process_is_running(plan_path, plan, health=health):
            return False
        if time.monotonic() >= deadline:
            return _read_valid_health(plan_path, plan) is not None
        time.sleep(0.05)


def wait_for_health(
    plan_path: Path,
    plan: dict[str, Any],
    process,
    *,
    timeout: float = 30.0,
    survival_seconds: float = 3.0,
) -> None:
    health_path = plan_path.with_name("health.json")
    deadline = time.monotonic() + max(0.0, timeout)
    confirmed_at: float | None = None
    health = None
    while time.monotonic() <= deadline:
        if not _process_running(process):
            raise RuntimeError("updated application exited before health confirmation")
        if confirmed_at is None and health_path.is_file():
            # A PyInstaller one-file launch has an outer bootloader PID and an
            # inner application PID. The unique transaction token authenticates
            # the ACK. Observe the actual application as well as its outer
            # bootloader, which can remain alive while cleaning up a dead child.
            health = _read_valid_health(plan_path, plan)
            if health is not None:
                confirmed_at = time.monotonic()
            if confirmed_at is None:
                health_path.unlink(missing_ok=True)
        if confirmed_at is not None:
            if not _health_process_is_running(plan_path, plan, health=health):
                raise RuntimeError("updated application's health process exited before confirmation")
            if time.monotonic() - confirmed_at >= max(0.0, survival_seconds):
                if _read_valid_health(plan_path, plan) != health:
                    raise RuntimeError("updated application health confirmation changed during observation")
                return
        time.sleep(0.05)
    raise TimeoutError("updated application did not confirm a healthy startup")


def migrate_shortcuts(_old: Path, _new: Path) -> tuple[list[str], list[str]]:
    from shortcut_links import migrate_shortcuts as migrate

    return migrate(_old, _new)


def _unlink_with_retry(path: Path, *, attempts: int = 8) -> bool:
    for attempt in range(max(1, attempts)):
        try:
            path.unlink(missing_ok=True)
            return True
        except OSError:
            if attempt + 1 >= attempts:
                break
            time.sleep(min(0.05 * (2**attempt), 1.0))
    return False


def _stale_release_candidates(
    new: Path,
    new_version: int,
) -> tuple[list[Path], list[Path]]:
    """Return older canonical EXEs and strict updater sidecars in one directory.

    The helper never performs a broad ``*.exe`` or ``*.old`` sweep.  Only
    exact product release names below the healthy new version are eligible.
    Canonical EXEs are returned separately because their shortcuts must be
    migrated before those files can be removed.
    """
    canonical: list[tuple[int, Path]] = []
    sidecars: list[tuple[int, Path]] = []
    new = Path(new).resolve()
    children = tuple(new.parent.iterdir())
    for candidate in children:
        # Never follow a symlink/reparse-point-looking release name outside the
        # install directory during shortcut migration or stale-file cleanup.
        if candidate.is_symlink() or not candidate.is_file():
            continue
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if resolved.parent != new.parent:
            continue
        match = _CANONICAL_EXE_RE.fullmatch(candidate.name)
        if match is not None:
            version = int(match.group("version"))
            if version < int(new_version) and resolved != new:
                canonical.append((version, candidate))
            continue
        match = _STALE_RELEASE_FILE_RE.fullmatch(candidate.name)
        if match is not None:
            version = int(match.group("version"))
            if version < int(new_version):
                sidecars.append((version, candidate))
    canonical.sort(key=lambda item: (-item[0], os.path.normcase(str(item[1]))))
    sidecars.sort(key=lambda item: (-item[0], os.path.normcase(str(item[1]))))
    return [path for _version, path in canonical], [path for _version, path in sidecars]


def _stop_process(process) -> bool:
    """Stop the launched process tree and report whether it is gone."""
    stop_tree = getattr(process, "stop_tree", None)
    if callable(stop_tree):
        # Job membership outlives the outer process; always stop the job even
        # when poll() reports that its bootloader has already exited.
        return stop_tree()
    if process is None or not _process_running(process):
        return True

    # A PyInstaller one-file launch has an outer bootloader plus an inner
    # application process. Terminating only the outer process can orphan the
    # inner process and leave the just-installed EXE locked. psutil is already
    # a pinned application dependency and lets the frozen helper stop the exact
    # descendant tree that it launched before attempting rollback.
    if isinstance(process, _POPEN_CLASS):
        try:
            root = psutil.Process(int(process.pid))
            descendants = root.children(recursive=True)
            process_tree = [*reversed(descendants), root]
            for child in process_tree:
                try:
                    child.terminate()
                except psutil.NoSuchProcess:
                    pass
            _gone, alive = psutil.wait_procs(process_tree, timeout=5.0)
            for child in alive:
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            _gone, alive = psutil.wait_procs(alive, timeout=3.0)
            try:
                process.wait(timeout=0.5)
            except Exception:
                pass
            return not alive and not _process_running(process)
        except Exception:
            # Fall through to the Popen-compatible termination path. A failed
            # stop is handled conservatively by leaving the journal recoverable.
            pass

    terminate = getattr(process, "terminate", None)
    if callable(terminate):
        try:
            terminate()
        except OSError:
            pass
    wait = getattr(process, "wait", None)
    if callable(wait):
        try:
            wait(timeout=5.0)
        except Exception:
            kill = getattr(process, "kill", None)
            if callable(kill):
                try:
                    kill()
                    wait(timeout=3.0)
                except Exception:
                    pass
    return not _process_running(process)


def _launch_update(command, *, cwd):
    if os.name == "nt":
        from update_process import JobProcess, UnconfirmedTerminationError

        try:
            return JobProcess(command, cwd=cwd)
        except UnconfirmedTerminationError as exc:
            # No JobProcess was returned to apply(). Preserve the distinction
            # between "never started" and a failed constructor with survivors.
            raise _UnconfirmedLaunchError(str(exc)) from exc
    return subprocess.Popen(command, cwd=cwd)


def _restore_legacy_old(
    plan: dict[str, Any],
    *,
    remove_wrong_named_new: bool,
) -> None:
    """Restore and verify the legacy rollback EXE before commit or rollback."""
    old = Path(plan["old_path"])
    backup = Path(plan["legacy_backup_path"])
    expected_old = plan["old_sha256"]
    expected_new = plan["new_sha256"]
    if _file_matches(old, expected_old):
        return
    if old.exists():
        if not remove_wrong_named_new or not _file_matches(old, expected_new):
            raise ValueError("legacy rollback target contains unexpected bytes")
        if not _unlink_with_retry(old):
            raise OSError(f"could not remove wrong-named update executable: {old}")
    if not _file_matches(backup, expected_old):
        raise ValueError("legacy rollback version is missing or changed")
    backup.replace(old)
    if not _file_matches(old, expected_old):
        raise ValueError("legacy rollback version could not be restored")


def _continue_commit(plan_path: Path, plan: dict[str, Any]) -> None:
    new = Path(plan["new_path"])
    if not new.is_file() or sha256(new).lower() != plan["new_sha256"]:
        raise ValueError("healthy update executable is missing or changed")
    _set_phase(plan_path, plan, "shortcuts_migrating")
    canonical, sidecars = _stale_release_candidates(new, int(plan["new_version"]))
    all_migrated = list(plan.get("migrated_shortcuts", []))
    all_failed: list[str] = []
    removable: list[Path] = []
    for candidate in canonical:
        migrated, failed = migrate_shortcuts(candidate, new)
        all_migrated.extend(migrated)
        all_failed.extend(failed)
        if not failed:
            removable.append(candidate)

    cleanup_complete = True
    for candidate in (*removable, *sidecars):
        if not _unlink_with_retry(candidate):
            cleanup_complete = False

    all_migrated = list(dict.fromkeys(all_migrated))
    all_failed = list(dict.fromkeys(all_failed))
    if all_failed or not cleanup_complete:
        _set_phase(
            plan_path,
            plan,
            "cleanup_pending",
            migrated_shortcuts=all_migrated,
            failed_shortcuts=all_failed,
        )
        return
    _set_phase(
        plan_path,
        plan,
        "committed",
        migrated_shortcuts=all_migrated,
        failed_shortcuts=[],
    )


def recover(plan_path: Path, *, health_survival_seconds: float = 3.0) -> None:
    """Conservatively resume an interrupted transaction on a later launch."""
    plan_path = Path(plan_path).resolve()
    plan = _load_plan(plan_path)
    phase = plan["phase"]
    if phase in {"committed", "rolled_back"}:
        return

    old = Path(plan["old_path"])
    new = Path(plan["new_path"])
    staged = Path(plan["staged_path"])
    legacy = bool(plan.get("legacy_r6_bootstrap", False))
    old_ok = _file_matches(old, plan["old_sha256"])
    new_ok = _file_matches(new, plan["new_sha256"])
    post_health_phase = phase in {"shortcuts_migrating", "cleanup_pending"}
    healthy = False
    if not post_health_phase and _read_valid_health(plan_path, plan) is not None:
        healthy = _observe_recovery_health(
            plan_path,
            plan,
            survival_seconds=health_survival_seconds,
        )
        if not healthy:
            try:
                plan_path.with_name("health.json").unlink(missing_ok=True)
            except OSError:
                pass

    if post_health_phase or healthy:
        if not new_ok:
            raise ValueError("cannot resume commit because the new executable is invalid")
        if legacy:
            # A crash can occur after moving the wrong-named new bytes but
            # before restoring the legacy rollback EXE. Restore it before
            # shortcut migration so links to the old canonical path remain
            # valid until they have been migrated.
            _restore_legacy_old(plan, remove_wrong_named_new=True)
        _continue_commit(plan_path, plan)
        return

    if phase in {"new_installed", "waiting_health"}:
        if legacy:
            _restore_legacy_old(plan, remove_wrong_named_new=True)
            old_ok = _file_matches(old, plan["old_sha256"])
        if not old_ok:
            raise ValueError("cannot roll back because the old executable is invalid")
        if new.exists():
            if not new_ok:
                raise ValueError("unconfirmed update executable changed; refusing to delete it")
            if not _unlink_with_retry(new):
                raise OSError(f"could not remove unconfirmed update executable: {new}")
        _set_phase(plan_path, plan, "rolled_back")
        return

    if phase in {"prepared", "waiting_old_exit"}:
        if legacy:
            # The wrong-named R7 process may still be running from the R6
            # helper. Its startup bootstrap will create a fresh, bounded plan.
            # If file movement already started before a crash, however, finish
            # restoring the real old version and remove only the hash-matching
            # unconfirmed new target.
            if _file_matches(old, plan["new_sha256"]):
                return
            _restore_legacy_old(plan, remove_wrong_named_new=True)
            if new.exists():
                if not new_ok:
                    raise ValueError("legacy update target changed; refusing to delete it")
                if not _unlink_with_retry(new):
                    raise OSError(f"could not remove unconfirmed update executable: {new}")
            _set_phase(plan_path, plan, "rolled_back")
            return
        if not old_ok:
            raise ValueError("prepared transaction no longer has a valid old executable")
        # If the staged file has already been consumed, the helper crashed in
        # the narrow move -> journal-write gap. The matching canonical target
        # is owned by this attempt and can be rolled back safely. A preexisting
        # matching target is preserved while the staged file still exists.
        if not staged.exists() and new.exists():
            if not new_ok:
                raise ValueError("update target changed; refusing to delete it")
            if not _unlink_with_retry(new):
                raise OSError(f"could not remove unconfirmed update executable: {new}")
        _set_phase(plan_path, plan, "rolled_back")
        return

    raise ValueError(f"unsupported recovery phase: {phase}")


def _rollback_failed_apply(
    plan_path: Path,
    plan: dict[str, Any],
    *,
    process,
    new_owned: bool,
    old_exited: bool,
) -> None:
    """Roll back only files this apply attempt proved it owned."""
    old = Path(plan["old_path"])
    new = Path(plan["new_path"])
    expected_old = plan["old_sha256"]
    expected_new = plan["new_sha256"]
    legacy = bool(plan.get("legacy_r6_bootstrap", False))
    problems: list[str] = []

    if not _stop_process(process):
        # Do not remove executables or resume the old application while a
        # descendant may still own devices or files from this attempt.
        raise RuntimeError("the launched update process tree is still running")

    if new_owned and new.exists():
        if not _file_matches(new, expected_new):
            problems.append("the unconfirmed update executable changed and was preserved")
        elif not _unlink_with_retry(new):
            problems.append("the unconfirmed update executable could not be removed")

    if legacy:
        try:
            _restore_legacy_old(plan, remove_wrong_named_new=old_exited or new_owned)
        except (OSError, ValueError) as exc:
            problems.append(str(exc))

    if not _file_matches(old, expected_old):
        problems.append("the previous executable is not available with its expected checksum")

    if problems:
        # Do not write a false terminal state. A later startup can retry the
        # same hash-bound journal after process/file locks have cleared.
        raise RuntimeError("; ".join(dict.fromkeys(problems)))

    _set_phase(plan_path, plan, "rolled_back")
    if old_exited:
        try:
            subprocess.Popen([str(old), *plan.get("args", [])], cwd=str(old.parent))
        except OSError:
            # The verified old EXE and terminal journal are intact; a failed
            # convenience restart does not make the rollback destructive.
            pass


def apply(
    plan_path: Path,
    *,
    health_timeout: float = 30.0,
    survival_seconds: float = 3.0,
) -> None:
    plan_path = Path(plan_path).resolve()
    plan = _load_plan(plan_path)
    old = Path(plan["old_path"])
    new = Path(plan["new_path"])
    staged = Path(plan["staged_path"])
    expected_old = plan["old_sha256"]
    expected_new = plan["new_sha256"]
    legacy = bool(plan.get("legacy_r6_bootstrap", False))
    backup = Path(plan["legacy_backup_path"]) if legacy else None
    process = None
    health_confirmed = False
    new_owned = False
    old_exited = False

    if plan["phase"] != "prepared":
        raise ValueError(f"update transaction cannot be applied from phase {plan['phase']}")
    if not _file_matches(staged, expected_new):
        raise ValueError("staged update failed checksum validation")
    if legacy:
        if not _file_matches(old, expected_new):
            raise ValueError("legacy running version does not contain the new bytes")
        if backup is None or not _file_matches(backup, expected_old):
            raise ValueError("legacy rollback version failed checksum validation")
    elif not _file_matches(old, expected_old):
        raise ValueError("running version failed checksum validation")

    try:
        _set_phase(plan_path, plan, "waiting_old_exit")
        wait_for_pid(int(plan["pid"]))
        old_exited = True
        if not _file_matches(staged, expected_new):
            raise ValueError("staged update changed while waiting for the running version")
        if legacy:
            if not _file_matches(old, expected_new):
                raise ValueError("legacy running version changed before installation")
            if backup is None or not _file_matches(backup, expected_old):
                raise ValueError("legacy rollback version changed before installation")
            if new.exists():
                if not _file_matches(new, expected_new):
                    raise FileExistsError(f"unexpected canonical update target: {new}")
                old.unlink()
                new_owned = True
            else:
                old.replace(new)
                new_owned = True
            backup.replace(old)
            staged.unlink(missing_ok=True)
        else:
            if not _file_matches(old, expected_old):
                raise ValueError("running version changed before installation")
            if new.exists():
                if not _file_matches(new, expected_new):
                    raise FileExistsError(f"unexpected canonical update target: {new}")
                staged.unlink(missing_ok=True)
                new_owned = True
            else:
                staged.replace(new)
                new_owned = True
        _set_phase(plan_path, plan, "new_installed")
        _set_phase(plan_path, plan, "waiting_health")
        command = [
            str(new),
            *plan.get("args", []),
            "--fhds-update-transaction",
            plan["transaction_id"],
            "--fhds-update-token",
            plan["token"],
        ]
        if not _file_matches(new, expected_new):
            raise ValueError("installed update failed checksum validation before launch")
        process = _launch_update(command, cwd=str(new.parent))
        wait_for_health(
            plan_path,
            plan,
            process,
            timeout=health_timeout,
            survival_seconds=survival_seconds,
        )
        release = getattr(process, "release", None)
        if callable(release):
            release()
        health_confirmed = True
        _continue_commit(plan_path, plan)
    except _UnconfirmedLaunchError as update_error:
        # process is still None, but the constructor could not confirm a stop.
        # Keep both EXEs and the nonterminal journal; never restart the old app
        # while a candidate may still own devices or files.
        raise RuntimeError(
            f"update failed and rollback remains pending: {update_error}"
        ) from update_error
    except Exception as update_error:
        if health_confirmed:
            try:
                _set_phase(plan_path, plan, "cleanup_pending")
            except Exception:
                pass
            raise
        try:
            _rollback_failed_apply(
                plan_path,
                plan,
                process=process,
                new_owned=new_owned,
                old_exited=old_exited,
            )
        except Exception as rollback_error:
            raise RuntimeError(
                f"update failed and rollback remains pending: {rollback_error}"
            ) from update_error
        raise
    finally:
        close = getattr(process, "close", None)
        if callable(close):
            close()


def _show_error(message: str) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            message,
            "FH-DualSense-Enhanced update failed",
            0x10,
        )
    except Exception:
        pass


def _show_warning(message: str) -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            None,
            message,
            "FH-DualSense-Enhanced update",
            0x30,
        )
    except Exception:
        pass


def _warn_shortcut_failures_once(plan_path: Path) -> None:
    plan = _load_plan(plan_path)
    failed = list(plan.get("failed_shortcuts", []))
    if plan.get("phase") != "cleanup_pending" or not failed or plan.get("shortcut_warning_shown"):
        return
    shown = "\n".join(failed[:10])
    if len(failed) > 10:
        shown += f"\n... and {len(failed) - 10} more"
    _show_warning(
        "The update is running, but these shortcuts could not be updated.\n"
        "The previous EXE was kept so those shortcuts still work.\n\n"
        + shown
    )
    _set_phase(plan_path, plan, "cleanup_pending", shortcut_warning_shown=True)


def main() -> int:
    if len(sys.argv) not in (2, 3):
        return 2
    recovery = len(sys.argv) == 3 and sys.argv[1] == "--recover"
    if len(sys.argv) == 3 and not recovery:
        return 2
    plan_path = Path(sys.argv[-1]).resolve()
    try:
        with _transaction_lock(plan_path) as acquired:
            if not acquired:
                # The original apply/recovery helper still owns this exact
                # transaction. It is safer for a duplicate startup recovery to
                # stand down than to mutate the same journal concurrently.
                return 0
            if recovery:
                recover(plan_path)
            else:
                apply(plan_path)
            _warn_shortcut_failures_once(plan_path)
    except Exception as exc:
        log = plan_path.parent.parent.parent / "update-helper-error.log"
        try:
            log.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        except OSError:
            pass
        _show_error(f"The update could not be completed.\n\n{type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
