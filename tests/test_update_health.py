"""Health acknowledgements must remain valid while the application survives."""

import hashlib
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def health_context(tmp_path):
    helper = runpy.run_path(str(Path(__file__).resolve().parents[1] / "packaging/windows/update_helper.py"))
    executable = tmp_path / "FH-DualSense-Enhanced-R7.exe"
    executable.write_bytes(b"MZ-new")
    plan = {
        "transaction_id": "a" * 32, "token": "health-test-token-with-24-bytes",
        "new_version": 7, "new_path": str(executable),
        "new_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
    }
    ack = {
        "schema": 1, "transaction_id": plan["transaction_id"], "token": plan["token"],
        "version": 7, "executable": str(executable), "sha256": plan["new_sha256"],
        "pid": 12345, "initialized_at": 100.0,
    }
    path = tmp_path / "plan.json"
    path.with_name("health.json").write_text(json.dumps(ack), encoding="utf-8")
    return helper, path, plan, ack


@pytest.mark.parametrize("malformed", ["utf8", "overflow"])
def test_malformed_health_is_unconfirmed_instead_of_raising(health_context, malformed):
    helper, path, plan, ack = health_context
    if malformed == "utf8":
        path.with_name("health.json").write_bytes(b'\xff')
    else:
        ack["initialized_at"] = 10 ** 400
        path.with_name("health.json").write_text(json.dumps(ack), encoding="utf-8")
    assert helper["_read_valid_health"](path, plan) is None


def test_unreadable_candidate_does_not_validate_health(health_context, monkeypatch):
    helper, path, plan, _ack = health_context

    def unreadable(_path):
        raise PermissionError("candidate locked")

    monkeypatch.setitem(helper["_read_valid_health"].__globals__, "sha256", unreadable)
    assert helper["_read_valid_health"](path, plan) is None


@pytest.mark.parametrize("child_lifetime", [0.0, 0.05])
def test_live_bootloader_cannot_mask_application_exit(health_context, monkeypatch, child_lifetime):
    helper, path, plan, _ack = health_context
    clock = [0.0]
    globals_ = helper["wait_for_health"].__globals__
    monkeypatch.setitem(globals_, "time", SimpleNamespace(
        monotonic=lambda: clock[0], sleep=lambda delay: clock.__setitem__(0, clock[0] + delay),
    ))
    def application(pid):
        assert pid == 12345
        return SimpleNamespace(is_running=lambda: clock[0] < child_lifetime,
                               exe=lambda: plan["new_path"])

    monkeypatch.setattr(helper["psutil"], "Process", application)
    bootloader = SimpleNamespace(poll=lambda: None)
    with pytest.raises(RuntimeError, match="health"):
        helper["wait_for_health"](path, plan, bootloader, timeout=1, survival_seconds=0.2)


def test_healthy_application_survives_the_full_observation(health_context, monkeypatch):
    helper, path, plan, _ack = health_context
    clock = [0.0]
    observations = []
    globals_ = helper["wait_for_health"].__globals__
    monkeypatch.setitem(globals_, "time", SimpleNamespace(
        monotonic=lambda: clock[0], sleep=lambda delay: clock.__setitem__(0, clock[0] + delay),
    ))
    monkeypatch.setitem(globals_, "_health_process_is_running",
                        lambda *_args, **_kwargs: observations.append(clock[0]) or True)
    helper["wait_for_health"](path, plan, SimpleNamespace(poll=lambda: None),
                             timeout=1, survival_seconds=0.2)
    assert observations[0] == 0
    assert observations[-1] >= 0.2


def test_health_cannot_change_during_survival_observation(health_context, monkeypatch):
    helper, path, plan, ack = health_context
    clock = [0.0]

    def advance(delay):
        clock[0] += delay
        ack["initialized_at"] += 1
        path.with_name("health.json").write_text(json.dumps(ack), encoding="utf-8")

    globals_ = helper["wait_for_health"].__globals__
    monkeypatch.setitem(globals_, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=advance))
    monkeypatch.setitem(globals_, "_health_process_is_running", lambda *_args, **_kwargs: True)
    with pytest.raises(RuntimeError, match="changed during observation"):
        helper["wait_for_health"](path, plan, SimpleNamespace(poll=lambda: None),
                                 timeout=1, survival_seconds=0.2)
