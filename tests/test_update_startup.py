import hashlib
import json
import os

import pytest

import main as app_main
from modules.update import install
from modules.update.transaction import (
    TransactionPhase,
    create_transaction,
    load_transaction,
    set_phase,
    write_health_ack,
)


def test_application_health_ack_is_written_only_for_matching_r7_binary(tmp_path, monkeypatch):
    install = tmp_path / "install"
    data = install / "data"
    install.mkdir()
    old = install / "FH-DualSense-Enhanced-R6.exe"
    staged = data / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=data / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="e" * 32,
        token="startup-health-token-with-24-bytes",
    )
    staged.replace(transaction.new)
    monkeypatch.setattr(app_main.paths, "DATA", data)
    monkeypatch.setattr(app_main.preferences, "_release_version", lambda: "R7")

    health = app_main.acknowledge_update_health(
        transaction.transaction_id,
        transaction.token,
        executable=transaction.new,
        pid=456,
    )

    payload = json.loads(health.read_text(encoding="utf-8"))
    assert payload["pid"] == 456
    assert payload["version"] == 7
    assert payload["executable"] == str(transaction.new)
    assert plan.is_file()


def test_application_health_ack_rejects_partial_internal_arguments():
    with pytest.raises(ValueError, match="both"):
        app_main.acknowledge_update_health("a" * 32, "")
    with pytest.raises(ValueError, match="both"):
        app_main.acknowledge_update_health("", "secret")
    assert app_main.acknowledge_update_health("", "") is None


def test_internal_update_arguments_are_hidden_from_public_help():
    help_text = app_main._parser().format_help()
    assert "fhds-update-transaction" not in help_text
    assert "fhds-update-token" not in help_text


def test_cli_udp_overrides_are_opt_in_so_saved_preferences_survive_startup():
    defaults = app_main._parser().parse_args([])
    explicit = app_main._parser().parse_args(["--host", "::1", "--port", "5400"])

    assert defaults.host is None
    assert defaults.port is None
    assert explicit.host == "::1"
    assert explicit.port == 5400


def test_ready_orphaned_new_version_writes_health_and_launches_recovery(tmp_path, monkeypatch):
    install_dir = tmp_path / "install"
    data = install_dir / "data"
    install_dir.mkdir()
    old = install_dir / "FH-DualSense-Enhanced-R6.exe"
    staged = data / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=data / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="3" * 32,
        token="orphan-ready-token-with-24-bytes",
    )
    staged.replace(transaction.new)
    set_phase(plan, TransactionPhase.WAITING_HEALTH)
    monkeypatch.setattr(install.paths, "DATA", data)
    monkeypatch.setattr(install, "_helper_prefix", lambda _root: ["helper.exe"])
    launched = []
    monkeypatch.setattr(
        install,
        "_spawn_helper",
        lambda command, root: launched.append((command, root)),
    )
    install._recovery_launched.clear()

    recovered = install.recover_incomplete_updates(
        executable=transaction.new,
        ready=True,
    )

    assert recovered == (plan,)
    assert plan.with_name("health.json").is_file()
    assert launched == [
        (["helper.exe", "--recover", str(plan)], data / "updates")
    ]


def test_orphaned_new_version_does_not_trust_stale_health_before_ready(tmp_path, monkeypatch):
    install_dir = tmp_path / "install"
    data = install_dir / "data"
    install_dir.mkdir()
    old = install_dir / "FH-DualSense-Enhanced-R6.exe"
    staged = data / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=data / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="8" * 32,
        token="stale-orphan-token-with-24-bytes",
    )
    staged.replace(transaction.new)
    set_phase(plan, TransactionPhase.WAITING_HEALTH)
    health = write_health_ack(
        root=data / "updates" / "transactions",
        transaction_id=transaction.transaction_id,
        token=transaction.token,
        executable=transaction.new,
        version=7,
        pid=999_999,
    )
    monkeypatch.setattr(install.paths, "DATA", data)
    monkeypatch.setattr(install, "_health_process_is_running", lambda *_args: False)
    monkeypatch.setattr(install, "_helper_prefix", lambda _root: ["helper.exe"])
    launched = []
    monkeypatch.setattr(install, "_spawn_helper", lambda command, root: launched.append((command, root)))
    install._recovery_launched.clear()

    assert install.recover_incomplete_updates(executable=transaction.new, ready=False) == ()
    assert launched == []
    assert json.loads(health.read_text(encoding="utf-8"))["pid"] == 999_999

    assert install.recover_incomplete_updates(executable=transaction.new, ready=True) == (plan,)
    assert json.loads(health.read_text(encoding="utf-8"))["pid"] == os.getpid()
    assert launched == [(["helper.exe", "--recover", str(plan)], data / "updates")]


def test_old_version_marks_pre_install_transaction_rolled_back(tmp_path, monkeypatch):
    data = tmp_path / "data"
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = data / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    _transaction, plan = create_transaction(
        root=data / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="4" * 32,
        token="prepared-recovery-token-24-bytes",
    )
    monkeypatch.setattr(install.paths, "DATA", data)
    install._recovery_launched.clear()

    assert install.recover_incomplete_updates(executable=old, ready=False) == ()
    assert load_transaction(plan).phase is TransactionPhase.ROLLED_BACK


def test_old_version_discards_stale_health_before_recovery(tmp_path, monkeypatch):
    data = tmp_path / "data"
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = data / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=data / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="5" * 32,
        token="stale-health-token-with-24-bytes",
    )
    staged.replace(transaction.new)
    set_phase(plan, TransactionPhase.WAITING_HEALTH)
    health = write_health_ack(
        root=data / "updates" / "transactions",
        transaction_id=transaction.transaction_id,
        token=transaction.token,
        executable=transaction.new,
        version=7,
        pid=999_999,
    )
    monkeypatch.setattr(install.paths, "DATA", data)
    monkeypatch.setattr(install, "_health_process_is_running", lambda *_args: False)
    monkeypatch.setattr(install, "_helper_prefix", lambda _root: ["helper.exe"])
    launched = []
    monkeypatch.setattr(install, "_spawn_helper", lambda command, root: launched.append((command, root)))
    install._recovery_launched.clear()

    recovered = install.recover_incomplete_updates(executable=old, ready=False)

    assert recovered == (plan,)
    assert not health.exists()
    assert launched == [(["helper.exe", "--recover", str(plan)], data / "updates")]


def test_old_version_does_not_race_a_live_new_health_process(tmp_path, monkeypatch):
    data = tmp_path / "data"
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = data / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=data / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="6" * 32,
        token="live-health-token-with-24-bytes",
    )
    staged.replace(transaction.new)
    set_phase(plan, TransactionPhase.WAITING_HEALTH)
    write_health_ack(
        root=data / "updates" / "transactions",
        transaction_id=transaction.transaction_id,
        token=transaction.token,
        executable=transaction.new,
        version=7,
        pid=456,
    )
    monkeypatch.setattr(install.paths, "DATA", data)
    monkeypatch.setattr(install, "_health_process_is_running", lambda *_args: True)
    monkeypatch.setattr(install, "_spawn_helper", lambda *_args: pytest.fail("must not launch recovery"))
    install._recovery_launched.clear()

    assert install.recover_incomplete_updates(executable=old, ready=False) == ()
    assert load_transaction(plan).phase is TransactionPhase.WAITING_HEALTH


def test_old_version_resumes_post_health_shortcut_phase(tmp_path, monkeypatch):
    data = tmp_path / "data"
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = data / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=data / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="7" * 32,
        token="shortcut-resume-token-with-24-bytes",
    )
    staged.replace(transaction.new)
    set_phase(plan, TransactionPhase.SHORTCUTS_MIGRATING)
    monkeypatch.setattr(install.paths, "DATA", data)
    monkeypatch.setattr(install, "_helper_prefix", lambda _root: ["helper.exe"])
    launched = []
    monkeypatch.setattr(install, "_spawn_helper", lambda command, root: launched.append((command, root)))
    install._recovery_launched.clear()

    assert install.recover_incomplete_updates(executable=old, ready=False) == (plan,)
    assert launched == [(["helper.exe", "--recover", str(plan)], data / "updates")]
