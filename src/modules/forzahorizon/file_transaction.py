"""Crash-safe exclusion for game-file transactions across portable instances."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


class FileTransactionError(RuntimeError):
    """The installation's file transaction could not be locked."""


@contextmanager
def game_file_transaction(root: Path, *, resource: str) -> Generator[None]:
    # Portable copies may use different data directories. Resolve aliases before
    # deriving the lock key and retain the inode after release for existing waiters.
    identity = os.path.normcase(str(root.resolve()))
    key = hashlib.sha256(f"{resource}\0{identity}".encode()).hexdigest()
    directory = Path(tempfile.gettempdir()) / "fhds-game-file-locks"
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        stream = (directory / f"{key}.lock").open("a+b")
    except OSError as exc:
        raise FileTransactionError(f"Could not open the game-file transaction lock: {exc}") from exc

    with stream:
        try:
            if os.name == "nt":
                import msvcrt

                stream.seek(0, os.SEEK_END)
                if stream.tell() == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise FileTransactionError(
                "Another game-file operation is in progress or its lock is unavailable; "
                "retry when it finishes"
            ) from exc
        # Closing the descriptor releases either OS lock, including on errors;
        # process termination releases it too, without stale-lock-file recovery.
        yield
