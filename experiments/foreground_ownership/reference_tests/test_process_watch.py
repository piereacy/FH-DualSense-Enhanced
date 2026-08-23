from types import SimpleNamespace

import pytest

from modules.forzahorizon import process_watch


def _process(pid, name, exe):
    return SimpleNamespace(pid=pid, info={"name": name, "exe": exe})


class _ForegroundProcess:
    def __init__(self, pid, name, exe):
        self.pid = pid
        self._name = name
        self._exe = exe

    def name(self):
        return self._name

    def exe(self):
        return self._exe


def test_windows_foreground_lookup_matches_the_exact_executable_owner():
    found = process_watch.find_foreground_process(
        exact_names=("ForzaHorizon4.exe", "ForzaHorizon5.exe", "ForzaHorizon6.exe"),
        strict=True,
        platform="win32",
        foreground_pid=lambda: 55,
        process_factory=lambda pid: _ForegroundProcess(
            pid,
            "ForzaHorizon5.exe",
            "D:/Games/FH5/ForzaHorizon5.exe",
        ),
    )

    assert found == process_watch.GameProcess(
        "ForzaHorizon5.exe",
        "D:/Games/FH5/ForzaHorizon5.exe",
        55,
    )


def test_windows_foreground_lookup_rejects_a_background_forza_process():
    # Only the foreground PID is queried. A separately running Forza process
    # must not keep the controller session active while another game has focus.
    found = process_watch.find_foreground_process(
        exact_names=("ForzaHorizon5.exe",),
        strict=True,
        platform="win32",
        foreground_pid=lambda: 91,
        process_factory=lambda pid: _ForegroundProcess(
            pid,
            "StarRail.exe",
            "D:/Games/StarRail/StarRail.exe",
        ),
    )

    assert found is None


def test_windows_foreground_lookup_treats_a_focus_transition_as_inactive():
    def vanished(_pid):
        raise process_watch.psutil.NoSuchProcess(77)

    assert process_watch.find_foreground_process(
        exact_names=("ForzaHorizon5.exe",),
        strict=True,
        platform="win32",
        foreground_pid=lambda: 77,
        process_factory=vanished,
    ) is None


def test_windows_foreground_lookup_fails_closed_when_the_api_fails():
    def fail():
        raise OSError("foreground API unavailable")

    assert process_watch.find_foreground_process(
        exact_names=("ForzaHorizon5.exe",),
        platform="win32",
        foreground_pid=fail,
    ) is None
    with pytest.raises(process_watch.ProcessScanError, match="foreground API unavailable"):
        process_watch.find_foreground_process(
            exact_names=("ForzaHorizon5.exe",),
            strict=True,
            platform="win32",
            foreground_pid=fail,
        )


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
