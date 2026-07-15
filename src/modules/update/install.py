from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from modules.config import paths


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 256), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cleanup_previous_update(target: Path | None = None) -> None:
    if target is None:
        if not getattr(sys, "frozen", False):
            return
        target = Path(sys.executable).resolve()
    old = Path(str(target) + ".old")
    try:
        old.unlink(missing_ok=True)
    except OSError:
        pass


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
    actual = _sha256(staged)
    if actual.lower() != expected_sha256.lower():
        raise ValueError("staged update checksum changed")
    if target is None:
        if not getattr(sys, "frozen", False):
            raise RuntimeError("automatic replacement is available only in a packaged EXE")
        target = Path(sys.executable).resolve()
    target = Path(target).resolve()
    update_dir = paths.DATA / "updates"
    update_dir.mkdir(parents=True, exist_ok=True)
    plan = update_dir / "install-plan.json"
    payload = {
        "pid": int(os.getpid() if pid is None else pid),
        "staged": str(staged),
        "target": str(target),
        "sha256": expected_sha256.lower(),
        "args": [],
        "created_at": time.time(),
    }
    tmp = plan.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(plan)

    if getattr(sys, "frozen", False):
        bundled = paths.ROOT / "data" / "FH-DualSense-Update-Helper.exe"
        if not bundled.is_file():
            raise FileNotFoundError("bundled update helper is missing")
        helper = update_dir / "FH-DualSense-Update-Helper.exe"
        shutil.copy2(bundled, helper)
        command = [str(helper), str(plan)]
    else:
        helper = Path(__file__).resolve().parents[3] / "packaging" / "windows" / "update_helper.py"
        command = [sys.executable, str(helper), str(plan)]
    subprocess.Popen(
        command,
        cwd=str(update_dir),
        close_fds=True,
        creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        if sys.platform.startswith("win") else 0,
    )
    return plan

