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
from pathlib import Path
from typing import Any


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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, allow_nan=False),
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


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
        if isinstance(plan[field], bool):
            raise ValueError(f"update transaction {field} is invalid")
    try:
        pid = int(plan["pid"])
        old_version = int(plan["old_version"])
        new_version = int(plan["new_version"])
        created_at = float(plan["created_at"])
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
    legacy_backup = str(plan.get("legacy_backup_path", ""))
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
    except (OSError, json.JSONDecodeError):
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
    if not isinstance(health.get("pid"), int) or int(health["pid"]) <= 0:
        return None
    new = Path(plan["new_path"])
    if not new.is_file() or sha256(new).lower() != plan["new_sha256"]:
        return None
    return health


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
    while time.monotonic() <= deadline:
        if not _process_running(process):
            raise RuntimeError("updated application exited before health confirmation")
        if confirmed_at is None and health_path.is_file():
            # A PyInstaller one-file launch has an outer bootloader PID and an
            # inner application PID. The unique transaction token authenticates
            # the ACK; process survival below continues to monitor the outer
            # process that owns the child lifetime.
            health = _read_valid_health(plan_path, plan)
            if health is not None:
                confirmed_at = time.monotonic()
            if confirmed_at is None:
                health_path.unlink(missing_ok=True)
        if confirmed_at is not None and time.monotonic() - confirmed_at >= max(0.0, survival_seconds):
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


def _stop_process(process) -> None:
    if process is None or not _process_running(process):
        return
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
            pass


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


def recover(plan_path: Path) -> None:
    """Conservatively resume an interrupted transaction on a later launch."""
    plan_path = Path(plan_path).resolve()
    plan = _load_plan(plan_path)
    phase = plan["phase"]
    if phase in {"committed", "rolled_back"}:
        return

    old = Path(plan["old_path"])
    new = Path(plan["new_path"])
    old_ok = old.is_file() and sha256(old).lower() == plan["old_sha256"]
    new_ok = new.is_file() and sha256(new).lower() == plan["new_sha256"]
    healthy = _read_valid_health(plan_path, plan) is not None

    if phase in {"shortcuts_migrating", "cleanup_pending"} or healthy:
        if not new_ok:
            raise ValueError("cannot resume commit because the new executable is invalid")
        _continue_commit(plan_path, plan)
        return

    if phase in {"new_installed", "waiting_health"}:
        if not old_ok:
            raise ValueError("cannot roll back because the old executable is invalid")
        if new.exists() and not _unlink_with_retry(new):
            raise OSError(f"could not remove unconfirmed update executable: {new}")
        _set_phase(plan_path, plan, "rolled_back")
        return

    if phase in {"prepared", "waiting_old_exit"}:
        if bool(plan.get("legacy_r6_bootstrap", False)):
            # The wrong-named R7 process may still be running from the R6
            # helper. Its startup bootstrap will create a fresh, bounded plan.
            return
        if not old_ok:
            raise ValueError("prepared transaction no longer has a valid old executable")
        _set_phase(plan_path, plan, "rolled_back")
        return

    raise ValueError(f"unsupported recovery phase: {phase}")


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

    if not staged.is_file() or sha256(staged).lower() != expected_new:
        raise ValueError("staged update failed checksum validation")
    if legacy:
        if not old.is_file() or sha256(old).lower() != expected_new:
            raise ValueError("legacy running version does not contain the new bytes")
        if backup is None or not backup.is_file() or sha256(backup).lower() != expected_old:
            raise ValueError("legacy rollback version failed checksum validation")
    elif not old.is_file() or sha256(old).lower() != expected_old:
        raise ValueError("running version failed checksum validation")

    try:
        _set_phase(plan_path, plan, "waiting_old_exit")
        wait_for_pid(int(plan["pid"]))
        if legacy:
            if not old.is_file() or sha256(old).lower() != expected_new:
                raise ValueError("legacy running version changed before installation")
            if backup is None or not backup.is_file() or sha256(backup).lower() != expected_old:
                raise ValueError("legacy rollback version changed before installation")
            if new.exists():
                if not new.is_file() or sha256(new).lower() != expected_new:
                    raise FileExistsError(f"unexpected canonical update target: {new}")
                old.unlink()
            else:
                old.replace(new)
            backup.replace(old)
            staged.unlink(missing_ok=True)
        else:
            if not old.is_file() or sha256(old).lower() != expected_old:
                raise ValueError("running version changed before installation")
            if new.exists():
                if not new.is_file() or sha256(new).lower() != expected_new:
                    raise FileExistsError(f"unexpected canonical update target: {new}")
                staged.unlink(missing_ok=True)
            else:
                staged.replace(new)
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
        process = subprocess.Popen(command, cwd=str(new.parent))
        wait_for_health(
            plan_path,
            plan,
            process,
            timeout=health_timeout,
            survival_seconds=survival_seconds,
        )
        health_confirmed = True
        _continue_commit(plan_path, plan)
    except Exception:
        if health_confirmed:
            try:
                _set_phase(plan_path, plan, "cleanup_pending")
            except Exception:
                pass
            raise
        _stop_process(process)
        _unlink_with_retry(new)
        if legacy and backup is not None:
            try:
                if old.is_file() and sha256(old).lower() != expected_old:
                    _unlink_with_retry(old)
                if not old.exists() and backup.is_file() and sha256(backup).lower() == expected_old:
                    backup.replace(old)
            except OSError:
                pass
        try:
            _set_phase(plan_path, plan, "rolled_back")
        finally:
            if old.is_file() and sha256(old).lower() == expected_old:
                try:
                    subprocess.Popen([str(old), *plan.get("args", [])], cwd=str(old.parent))
                except OSError:
                    pass
        raise


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
