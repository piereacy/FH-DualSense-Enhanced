"""Candidate process ownership survives the outer bootloader exiting."""

import importlib.util
import os
import sys
import time
from pathlib import Path

import psutil
import pytest

MODULE = Path(__file__).resolve().parents[1] / "packaging/windows/update_process.py"
SPEC = importlib.util.spec_from_file_location("fhds_update_process", MODULE)
update_process = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update_process)


class Api:
    def __init__(self, fail=None):
        self.fail = fail
        self.events = []
        self.handles = set()
        self.closed = set()
        self.active = 0
        self.armed = False
        self.assigned = False
        self.outer_exit = None

    def event(self, name):
        self.events.append(name)
        if name == self.fail:
            self.fail = None
            raise OSError(f"failed {name}")

    def create_job(self):
        self.event("create_job")
        self.handles.add("job")
        return "job"

    def kill_on_close(self, job, enabled):
        self.event("arm" if enabled else "disarm")
        self.armed = enabled

    def create_suspended(self, command, cwd):
        self.event("create_suspended")
        self.handles.update(("process", "thread"))
        self.active = 1
        return "process", "thread", 123

    def assign(self, job, process):
        self.event("assign")
        self.assigned = True

    def resume(self, thread):
        self.event("resume")
        self.active = 2  # application spawned its inner process

    def poll(self, process):
        return self.outer_exit

    def terminate_job(self, job):
        self.event("terminate_job")
        self.active = 0
        self.outer_exit = 1

    def terminate_process(self, process):
        self.event("terminate_process")
        self.active = 0
        self.outer_exit = 1

    def wait(self, process, timeout):
        self.event("wait")

    def active_processes(self, job):
        return self.active

    def close(self, handle):
        self.event(f"close_{handle}")
        self.closed.add(handle)
        if handle == "job" and self.armed and self.assigned:
            self.active = 0


def test_candidate_is_assigned_before_any_thread_runs():
    api = Api()
    process = update_process.JobProcess(["candidate.exe", "--tui"], cwd="C:/game", api=api)
    assert api.events[:6] == ["create_job", "arm", "create_suspended", "assign", "resume", "close_thread"]
    assert process.pid == 123
    process.close()
    assert api.closed == api.handles
    assert api.active == 0


def test_rollback_stops_descendants_after_outer_process_exits():
    api = Api()
    process = update_process.JobProcess(["candidate.exe"], cwd="C:/game", api=api)
    api.outer_exit = 0
    api.active = 1
    assert process.poll() == 0
    assert process.stop_tree(timeout=0)
    assert "terminate_job" in api.events
    assert api.active == 0
    process.close()


def test_healthy_candidate_survives_releasing_job_handles():
    api = Api()
    process = update_process.JobProcess(["candidate.exe"], cwd="C:/game", api=api)
    process.release()
    assert api.active == 2
    assert api.closed == api.handles
    assert api.events.index("disarm") < api.events.index("close_job")
    process.release()
    assert api.events.count("disarm") == 1


@pytest.mark.parametrize("handle", ["process", "job"])
def test_release_keeps_failed_close_handles_for_final_cleanup(handle):
    api = Api()
    process = update_process.JobProcess(["candidate.exe"], cwd="C:/game", api=api)
    api.fail = f"close_{handle}"

    process.release()

    assert api.active == 2
    assert getattr(process, f"_{handle}") == handle
    assert handle not in api.closed
    process.close()
    assert api.closed == api.handles
    assert api.active == 2


def test_failed_release_keeps_job_armed_for_rollback():
    api = Api()
    process = update_process.JobProcess(["candidate.exe"], cwd="C:/game", api=api)
    api.fail = "disarm"

    with pytest.raises(OSError, match="failed disarm"):
        process.release()

    assert api.armed
    assert api.active == 2
    assert "job" not in api.closed
    assert process.stop_tree(timeout=0)
    process.close()
    assert api.active == 0
    assert api.closed == api.handles


@pytest.mark.parametrize("failure", ["create_job", "arm", "create_suspended", "assign", "resume", "close_thread"])
def test_failed_candidate_launch_reaps_suspended_process_and_closes_handles(failure):
    api = Api(fail=failure)
    with pytest.raises(OSError, match=f"failed {failure}"):
        update_process.JobProcess(["candidate.exe"], cwd="C:/game", api=api)
    assert api.active == 0
    assert api.closed == api.handles
    if failure == "assign":
        assert "terminate_process" in api.events
        assert "wait" in api.events


@pytest.mark.parametrize("failure", ["assign", "resume"])
def test_failed_launch_reports_unconfirmed_termination_explicitly(failure):
    api = Api(fail=failure)

    def fail_stop(_handle):
        raise OSError("termination failed")

    api.terminate_process = api.terminate_job = fail_stop
    with pytest.raises(update_process.UnconfirmedTerminationError) as error:
        update_process.JobProcess(["candidate.exe"], cwd="C:/game", api=api)

    assert isinstance(error.value.__cause__, OSError)
    assert str(error.value.__cause__) == f"failed {failure}"
    assert api.closed == api.handles
    if failure == "assign":
        # Closing the unassigned job cannot stop the suspended process.
        assert api.active == 1


def test_unconfirmed_job_stop_reports_failure(monkeypatch):
    api = Api()
    process = update_process.JobProcess(["candidate.exe"], cwd="C:/game", api=api)
    api.terminate_job = lambda job: None
    assert not process.stop_tree(timeout=0)
    process.close()
    assert api.active == 0


@pytest.mark.skipif(os.name != "nt", reason="requires a real Windows Job Object")
def test_windows_job_reaps_real_orphan_child(tmp_path):
    marker = tmp_path / "child.pid"
    program = (
        "import subprocess,sys;from pathlib import Path;"
        "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        "Path(sys.argv[1]).write_text(str(p.pid))"
    )
    process = update_process.JobProcess([sys.executable, "-c", program, str(marker)], cwd=str(tmp_path))
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() or process.poll() is None:
            assert time.monotonic() < deadline
            time.sleep(0.05)
        child_pid = int(marker.read_text())
        assert psutil.pid_exists(child_pid)
        assert process.stop_tree()
        assert not psutil.pid_exists(child_pid)
    finally:
        process.stop_tree()
        process.close()
