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


def test_exact_multi_name_lookup_scans_once_and_rejects_similarly_named_helpers(
    monkeypatch,
):
    processes = [
        _process(
            1,
            "ForzaHorizon5Telemetry.exe",
            "D:/Tools/ForzaHorizon5Telemetry.exe",
        ),
        _process(2, "ForzaHorizon4.exe", "E:/Steam/ForzaHorizon4.exe"),
    ]
    scans = []

    def process_iter(fields):
        scans.append(tuple(fields))
        return processes

    monkeypatch.setattr(process_watch.psutil, "process_iter", process_iter)

    found = process_watch.find_game_process(
        (),
        exact_names=("ForzaHorizon4.exe", "ForzaHorizon5.exe", "ForzaHorizon6.exe"),
    )

    assert found is not None
    assert found.pid == 2
    assert scans == [("name", "exe")]


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


def test_root_filtered_scan_preserves_iteration_failure_after_a_mismatch(
    tmp_path, monkeypatch
):
    executable = "ForzaHorizon6.exe"

    def process_iter(_fields):
        yield _process(1, executable, str(tmp_path / "Other" / executable))
        raise OSError("process table interrupted")

    monkeypatch.setattr(process_watch.psutil, "process_iter", process_iter)

    with pytest.raises(process_watch.ProcessScanError, match="process table interrupted"):
        process_watch.find_game_process(
            (),
            exact_name=executable,
            exact_executable=tmp_path / "Selected" / executable,
            strict=True,
        )


def test_root_filtered_scan_keeps_an_unresolvable_path_as_a_conservative_match(
    tmp_path, monkeypatch
):
    executable = "ForzaHorizon6.exe"
    processes = [_process(1, executable, str(tmp_path / executable))]
    monkeypatch.setattr(process_watch.psutil, "process_iter", lambda _fields: processes)

    def inaccessible_path(_path):
        raise OSError("executable path unavailable")

    monkeypatch.setattr(process_watch.Path, "resolve", inaccessible_path)

    found = process_watch.find_game_process(
        (),
        exact_name=executable,
        exact_executable=tmp_path / "Selected" / executable,
        strict=True,
    )

    assert found is not None
    assert found.pid == 1


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
