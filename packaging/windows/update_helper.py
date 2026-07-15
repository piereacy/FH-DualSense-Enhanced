"""Minimal Windows self-update helper, packaged separately from the main EXE."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def wait_for_pid(pid: int, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.2)
    raise TimeoutError(f"process {pid} did not exit")


def apply(plan_path: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    pid = int(plan["pid"])
    staged = Path(plan["staged"]).resolve()
    target = Path(plan["target"]).resolve()
    expected = str(plan["sha256"]).lower()
    if not staged.is_file() or sha256(staged).lower() != expected:
        raise ValueError("staged update failed checksum validation")
    if staged == target or target.parent == staged:
        raise ValueError("invalid update paths")

    wait_for_pid(pid)
    old = Path(str(target) + ".old")
    old.unlink(missing_ok=True)
    moved_old = False
    try:
        if target.exists():
            target.replace(old)
            moved_old = True
        staged.replace(target)
        subprocess.Popen([str(target), *plan.get("args", [])], cwd=str(target.parent))
        plan_path.unlink(missing_ok=True)
    except Exception:
        try:
            if target.exists():
                target.unlink()
            if moved_old and old.exists():
                old.replace(target)
        finally:
            raise


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        apply(Path(sys.argv[1]).resolve())
    except Exception as exc:
        log = Path(sys.argv[1]).with_name("update-helper-error.log")
        log.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
