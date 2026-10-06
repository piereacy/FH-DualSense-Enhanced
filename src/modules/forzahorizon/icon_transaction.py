"""Cross-process exclusion for controller-icon writes to one game root."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


class IconTransactionBusyError(RuntimeError):
    """Another process owns this installation's controller-icon transaction."""


@contextmanager
def icon_transaction(root: Path) -> Generator[None]:
    # Portable copies can use different data directories while targeting the
    # same game. Keep exclusion independent of the backup directory. Do not
    # unlink a lock file: a waiter may still hold its previous inode open.
    identity = os.path.normcase(str(root.resolve()))
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    directory = Path(tempfile.gettempdir()) / "fhds-controller-icon-locks"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / f"{key}.lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise IconTransactionBusyError(
                    "Another controller-icon operation is in progress; retry when it finishes"
                ) from exc
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise IconTransactionBusyError(
                    "Another controller-icon operation is in progress; retry when it finishes"
                ) from exc
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
