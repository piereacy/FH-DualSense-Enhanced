from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import psutil

from modules.config import paths

from .transaction import (
    TransactionError,
    create_legacy_transaction,
    create_transaction,
    load_transaction,
    release_version,
    set_phase,
    sha256_file,
    TransactionPhase,
    write_health_ack,
)


log = logging.getLogger("fhds.update.install")
_recovery_launched: set[str] = set()


@dataclass(frozen=True, slots=True)
class LegacyBootstrapCandidate:
    executable: Path
    backup: Path
    old_version: int
    new_version: int


def self_update_supported() -> bool:
    """Only a frozen Windows EXE can safely replace itself with this helper."""
    return sys.platform.startswith("win") and bool(getattr(sys, "frozen", False))


def cleanup_previous_update(target: Path | None = None) -> None:
    """Compatibility hook retained for callers from R6.

    R7 transactions own cleanup through their persisted journal.  Deleting a
    sibling solely because its name ends in ``.old`` can destroy the only
    rollback copy after an interrupted R6 -> R7 bootstrap, so this function is
    deliberately conservative until startup recovery has inspected the files.
    """
    return None


def _helper_prefix(update_dir: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        bundled = paths.ROOT / "data" / "FH-DualSense-Update-Helper.exe"
        if not bundled.is_file():
            raise FileNotFoundError("bundled update helper is missing")
        helper = update_dir / "FH-DualSense-Update-Helper.exe"
        if not helper.is_file() or sha256_file(helper) != sha256_file(bundled):
            temporary = helper.with_name(f".{helper.name}.{os.getpid()}.tmp")
            try:
                shutil.copy2(bundled, temporary)
                if sha256_file(temporary) != sha256_file(bundled):
                    raise TransactionError("copied update helper checksum changed")
                temporary.replace(helper)
            finally:
                temporary.unlink(missing_ok=True)
        return [str(helper)]
    helper = Path(__file__).resolve().parents[3] / "packaging" / "windows" / "update_helper.py"
    if not helper.is_file():
        raise FileNotFoundError(helper)
    return [sys.executable, str(helper)]


def _spawn_helper(command: list[str], update_dir: Path) -> None:
    subprocess.Popen(
        command,
        cwd=str(update_dir),
        close_fds=True,
        creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        if sys.platform.startswith("win") else 0,
    )


def _ensure_install_directory_writable(directory: Path) -> None:
    probe = Path(directory) / f".fhds-update-write-test-{os.getpid()}"
    try:
        with probe.open("xb") as stream:
            stream.write(b"")
    except OSError as exc:
        raise PermissionError(f"application directory is not writable: {directory}") from exc
    finally:
        probe.unlink(missing_ok=True)


def _other_install_instances(directory: Path, *, current_pid: int) -> tuple[tuple[int, str], ...]:
    if not sys.platform.startswith("win"):
        return ()
    try:
        import psutil
    except ImportError:
        return ()
    expected = Path(directory).resolve()
    matches: list[tuple[int, str]] = []
    for process in psutil.process_iter(("pid", "exe")):
        try:
            pid = int(process.info.get("pid") or 0)
            executable = process.info.get("exe") or ""
            path = Path(executable).resolve() if executable else None
        except (OSError, ValueError, psutil.Error):
            continue
        if pid <= 0 or pid == int(current_pid) or path is None or path.parent != expected:
            continue
        try:
            release_version(path.name)
        except TransactionError:
            continue
        matches.append((pid, str(path)))
    return tuple(matches)


def _health_file_matches(transaction, plan_path: Path) -> bool:
    try:
        payload = json.loads(plan_path.with_name("health.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(
        isinstance(payload, dict)
        and payload.get("schema") == transaction.schema
        and payload.get("transaction_id") == transaction.transaction_id
        and payload.get("token") == transaction.token
        and payload.get("version") == transaction.new_version
        and payload.get("executable") == transaction.new_path
        and payload.get("sha256") == transaction.new_sha256
        and transaction.new.is_file()
        and sha256_file(transaction.new).lower() == transaction.new_sha256
    )


def _health_process_is_running(transaction, plan_path: Path) -> bool:
    """Return whether a valid health ACK still belongs to a live new EXE."""
    if not _health_file_matches(transaction, plan_path):
        return False
    try:
        payload = json.loads(plan_path.with_name("health.json").read_text(encoding="utf-8"))
        pid = int(payload["pid"])
        if pid <= 0:
            return False
        process = psutil.Process(pid)
        if not process.is_running():
            return False
        running_path = Path(process.exe()).resolve()
        return os.path.normcase(str(running_path)) == os.path.normcase(str(transaction.new.resolve()))
    except psutil.AccessDenied:
        # Access denied is not proof of death. Keeping both EXEs is safer than
        # rolling back underneath a process that may still be starting.
        return True
    except (KeyError, TypeError, ValueError, OSError, psutil.Error):
        return False


def _health_belongs_to_pid(transaction, plan_path: Path, pid: int) -> bool:
    if not _health_file_matches(transaction, plan_path):
        return False
    try:
        payload = json.loads(plan_path.with_name("health.json").read_text(encoding="utf-8"))
        return int(payload.get("pid", 0)) == int(pid) and int(pid) > 0
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False


def recover_incomplete_updates(
    *,
    active_transaction_id: str = "",
    executable: Path | None = None,
    ready: bool = False,
) -> tuple[Path, ...]:
    """Resume trustworthy journals that belong to the executable now running."""
    if executable is None and not self_update_supported():
        return ()
    current = Path(sys.executable if executable is None else executable).resolve()
    transaction_root = (paths.DATA / "updates" / "transactions").resolve()
    if not transaction_root.is_dir():
        return ()
    update_dir = transaction_root.parent
    launched: list[Path] = []
    for plan_path in sorted(transaction_root.glob("*/transaction.json")):
        try:
            transaction = load_transaction(plan_path)
        except TransactionError as exc:
            log.warning("Ignoring invalid update transaction %s: %s", plan_path, exc)
            continue
        if (
            transaction.transaction_id == active_transaction_id
            or transaction.transaction_id in _recovery_launched
            or transaction.phase in {TransactionPhase.COMMITTED, TransactionPhase.ROLLED_BACK}
        ):
            continue

        current_is_old = current == transaction.old
        current_is_new = current == transaction.new
        if not current_is_old and not current_is_new:
            continue

        should_launch = False
        if current_is_new and transaction.phase in {
            TransactionPhase.NEW_INSTALLED,
            TransactionPhase.WAITING_HEALTH,
        }:
            if ready:
                if (
                    _health_process_is_running(transaction, plan_path)
                    and not _health_belongs_to_pid(transaction, plan_path, os.getpid())
                ):
                    # Another healthy R7 process still owns this journal.
                    continue
                # Replace any stale ACK from a previous crashed process. The
                # helper must only commit after this process reaches ready.
                write_health_ack(
                    root=transaction_root,
                    transaction_id=transaction.transaction_id,
                    token=transaction.token,
                    executable=current,
                    version=transaction.new_version,
                )
                should_launch = True
            else:
                should_launch = _health_belongs_to_pid(
                    transaction,
                    plan_path,
                    os.getpid(),
                )
        elif current_is_new and transaction.phase in {
            TransactionPhase.SHORTCUTS_MIGRATING,
            TransactionPhase.CLEANUP_PENDING,
        }:
            should_launch = True
        elif current_is_old and transaction.phase in {
            TransactionPhase.NEW_INSTALLED,
            TransactionPhase.WAITING_HEALTH,
        }:
            if _health_process_is_running(transaction, plan_path):
                # The new process still owns this transaction. Do not let an
                # accidentally launched old shortcut race its health window.
                continue
            plan_path.with_name("health.json").unlink(missing_ok=True)
            should_launch = True
        elif current_is_old and transaction.phase in {
            TransactionPhase.SHORTCUTS_MIGRATING,
            TransactionPhase.CLEANUP_PENDING,
        }:
            # Reaching these phases proves the new process survived its health
            # window. Resume shortcut work; deletion of this running old EXE
            # will remain cleanup-pending until a later new-version launch.
            should_launch = True
        elif (
            current_is_old
            and not transaction.legacy_r6_bootstrap
            and transaction.phase in {TransactionPhase.PREPARED, TransactionPhase.WAITING_OLD_EXIT}
        ):
            set_phase(plan_path, TransactionPhase.ROLLED_BACK)

        if should_launch:
            prefix = _helper_prefix(update_dir)
            _spawn_helper([*prefix, "--recover", str(plan_path)], update_dir)
            _recovery_launched.add(transaction.transaction_id)
            launched.append(plan_path)
    return tuple(launched)


def _restart_args(argv: list[str] | None = None) -> tuple[str, ...]:
    """Return public CLI arguments without updater-internal credentials."""
    source = list(sys.argv[1:] if argv is None else argv)
    result: list[str] = []
    skip_next = False
    for item in source:
        if skip_next:
            skip_next = False
            continue
        if item in ("--fhds-update-transaction", "--fhds-update-token"):
            skip_next = True
            continue
        result.append(item)
    return tuple(result)


def _pe_major_version(path: Path) -> int | None:
    """Return the fixed PE file-version major component on Windows."""
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        from ctypes import wintypes

        version = ctypes.WinDLL("version", use_last_error=True)
        get_size = version.GetFileVersionInfoSizeW
        get_size.argtypes = (wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD))
        get_size.restype = wintypes.DWORD
        get_info = version.GetFileVersionInfoW
        get_info.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID)
        get_info.restype = wintypes.BOOL
        query = version.VerQueryValueW
        query.argtypes = (
            wintypes.LPCVOID,
            wintypes.LPCWSTR,
            ctypes.POINTER(wintypes.LPVOID),
            ctypes.POINTER(wintypes.UINT),
        )
        query.restype = wintypes.BOOL

        ignored = wintypes.DWORD()
        size = int(get_size(str(Path(path)), ctypes.byref(ignored)))
        if size <= 0:
            return None
        buffer = ctypes.create_string_buffer(size)
        if not get_info(str(Path(path)), 0, size, buffer):
            return None
        pointer = wintypes.LPVOID()
        length = wintypes.UINT()
        if not query(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
            return None

        class VSFixedFileInfo(ctypes.Structure):
            _fields_ = [
                ("signature", wintypes.DWORD),
                ("struct_version", wintypes.DWORD),
                ("file_version_ms", wintypes.DWORD),
                ("file_version_ls", wintypes.DWORD),
                ("product_version_ms", wintypes.DWORD),
                ("product_version_ls", wintypes.DWORD),
                ("file_flags_mask", wintypes.DWORD),
                ("file_flags", wintypes.DWORD),
                ("file_os", wintypes.DWORD),
                ("file_type", wintypes.DWORD),
                ("file_subtype", wintypes.DWORD),
                ("file_date_ms", wintypes.DWORD),
                ("file_date_ls", wintypes.DWORD),
            ]

        info = ctypes.cast(pointer, ctypes.POINTER(VSFixedFileInfo)).contents
        if info.signature != 0xFEEF04BD:
            return None
        return int(info.file_version_ms >> 16)
    except (OSError, ValueError):
        return None


def detect_legacy_bootstrap(
    *,
    executable: Path | None = None,
    current_version: int | None = None,
    version_reader=None,
) -> LegacyBootstrapCandidate | None:
    """Recognize the exact R6-helper output without trusting filenames alone."""
    if executable is None:
        if not self_update_supported():
            return None
        executable = Path(sys.executable)
    executable = Path(executable).resolve()
    try:
        old_version = release_version(executable.name)
    except TransactionError:
        return None
    if current_version is None:
        from modules.config.preferences import _release_version

        label = _release_version()
        try:
            current_version = int(label.removeprefix("R"))
        except ValueError:
            return None
    current_version = int(current_version)
    if current_version <= old_version:
        return None
    backup = Path(str(executable) + ".old").resolve()
    if not executable.is_file() or not backup.is_file():
        return None
    reader = version_reader or _pe_major_version
    if reader(executable) != current_version or reader(backup) != old_version:
        return None
    return LegacyBootstrapCandidate(executable, backup, old_version, current_version)


def launch_legacy_bootstrap(
    *,
    executable: Path | None = None,
    current_version: int | None = None,
    pid: int | None = None,
    argv: list[str] | None = None,
    version_reader=None,
) -> Path | None:
    """Start R7's second-stage helper when R6 launched it under the R6 name."""
    candidate = detect_legacy_bootstrap(
        executable=executable,
        current_version=current_version,
        version_reader=version_reader,
    )
    if candidate is None:
        return None
    update_dir = (paths.DATA / "updates").resolve()
    update_dir.mkdir(parents=True, exist_ok=True)
    staged = update_dir / f"FH-DualSense-Enhanced-R{candidate.new_version}.exe"
    temporary = staged.with_name(f".{staged.name}.{os.getpid()}.legacy.tmp")
    try:
        shutil.copy2(candidate.executable, temporary)
        if sha256_file(temporary) != sha256_file(candidate.executable):
            raise TransactionError("legacy staged copy checksum changed")
        temporary.replace(staged)
    finally:
        temporary.unlink(missing_ok=True)

    prefix = _helper_prefix(update_dir)

    _transaction, plan = create_legacy_transaction(
        root=update_dir / "transactions",
        staged=staged,
        wrong_named_executable=candidate.executable,
        backup=candidate.backup,
        new_version=candidate.new_version,
        pid=int(os.getpid() if pid is None else pid),
        args=_restart_args(argv),
    )
    _spawn_helper([*prefix, str(plan)], update_dir)
    return plan


def launch_update_helper(
    staged: Path,
    *,
    expected_sha256: str,
    target: Path | None = None,
    pid: int | None = None,
) -> Path:
    staged = Path(staged).resolve()
    if not staged.is_file():
        raise FileNotFoundError(staged)
    if target is None:
        if not getattr(sys, "frozen", False):
            raise RuntimeError("automatic replacement is available only in a packaged EXE")
        target = Path(sys.executable).resolve()
    target = Path(target).resolve()
    _ensure_install_directory_writable(target.parent)
    current_pid = int(os.getpid() if pid is None else pid)
    other_instances = _other_install_instances(target.parent, current_pid=current_pid)
    if other_instances:
        details = ", ".join(f"PID {other_pid}: {path}" for other_pid, path in other_instances)
        raise RuntimeError(
            "close other FH-DualSense-Enhanced instances in this application directory "
            f"before updating ({details})"
        )
    update_dir = paths.DATA / "updates"
    update_dir.mkdir(parents=True, exist_ok=True)
    prefix = _helper_prefix(update_dir)

    _transaction, plan = create_transaction(
        root=update_dir / "transactions",
        staged=staged,
        target=target,
        expected_sha256=expected_sha256,
        pid=current_pid,
        args=_restart_args(),
    )
    _spawn_helper([*prefix, str(plan)], update_dir)
    return plan
