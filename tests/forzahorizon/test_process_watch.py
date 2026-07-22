from types import SimpleNamespace

import pytest

from modules.forzahorizon import process_watch


def _process(pid, name, exe):
    return SimpleNamespace(pid=pid, info={"name": name, "exe": exe})


def test_exact_fh6_process_lookup_returns_the_full_executable_path(monkeypatch):
    processes = [
        _process(1, "ForzaHelper.exe", "D:/Tools/ForzaHelper.exe"),
        _process(2, "ForzaHorizon6.exe", "E:/SteamLibrary/ForzaHorizon6.exe"),
    ]
    monkeypatch.setattr(process_watch.psutil, "process_iter", lambda _fields: processes)

    found = process_watch.find_game_process((), exact_name="ForzaHorizon6.exe")

    assert found is not None
    assert found.pid == 2
    assert found.name == "ForzaHorizon6.exe"
    assert found.exe == "E:/SteamLibrary/ForzaHorizon6.exe"


def test_process_lookup_skips_protected_entries(monkeypatch):
    class Protected:
        pid = 1

        @property
        def info(self):
            raise process_watch.psutil.AccessDenied(1)

    processes = [Protected(), _process(2, "ForzaHorizon6.exe", "D:/FH6/ForzaHorizon6.exe")]
    monkeypatch.setattr(process_watch.psutil, "process_iter", lambda _fields: processes)

    assert process_watch.find_game_process((), exact_name="ForzaHorizon6.exe").pid == 2


def test_strict_process_scan_distinguishes_os_failure_from_no_match(monkeypatch):
    def fail(_fields):
        raise RuntimeError("process table unavailable")

    monkeypatch.setattr(process_watch.psutil, "process_iter", fail)

    assert process_watch.find_game_process((), exact_name="ForzaHorizon6.exe") is None
    with pytest.raises(process_watch.ProcessScanError, match="process table unavailable"):
        process_watch.find_game_process(
            (), exact_name="ForzaHorizon6.exe", strict=True
        )


def test_process_watcher_does_not_exit_when_strict_scan_fails(monkeypatch):
    watcher = process_watch.ProcessWatcher(poll_interval_s=float("nan"))
    watcher._matched = "ForzaHorizon6.exe"
    monkeypatch.setattr(
        process_watch,
        "find_game_process",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            process_watch.ProcessScanError("unavailable")
        ),
    )

    assert watcher.poll_interval == 1.0
    assert watcher.should_exit() is False
