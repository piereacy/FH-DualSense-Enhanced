"""Small persistent runtime log for failures that outlive the UI session."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import paths

RUNTIME_LOG = paths.DATA / "runtime.log"
_HANDLER_MARKER = "_fhds_runtime_file_handler"


def install_runtime_file_handler(
    path: Path | None = None,
) -> RotatingFileHandler | None:
    """Install one bounded UTF-8 file handler and return it when available."""
    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            return handler

    destination = Path(path) if path is not None else RUNTIME_LOG
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            destination,
            maxBytes=2 * 1024 * 1024,
            backupCount=2,
            encoding="utf-8",
            delay=True,
        )
    except OSError:
        return None
    setattr(handler, _HANDLER_MARKER, True)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
    return handler
