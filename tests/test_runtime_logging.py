import logging

from modules.runtime_logging import install_runtime_file_handler


def test_runtime_file_handler_is_bounded_utf8_and_idempotent(tmp_path):
    root = logging.getLogger()
    existing = [
        item
        for item in root.handlers
        if getattr(item, "_fhds_runtime_file_handler", False)
    ]
    for item in existing:
        root.removeHandler(item)
    destination = tmp_path / "runtime.log"
    handler = install_runtime_file_handler(destination)
    try:
        assert handler is not None
        assert install_runtime_file_handler(destination) is handler
        assert handler.maxBytes == 2 * 1024 * 1024
        assert handler.backupCount == 2

        logging.getLogger("fhds.test").warning("persistent diagnostic")
        handler.flush()
        assert "persistent diagnostic" in destination.read_text(encoding="utf-8")
    finally:
        if handler is not None:
            root.removeHandler(handler)
            handler.close()
        for item in existing:
            root.addHandler(item)
