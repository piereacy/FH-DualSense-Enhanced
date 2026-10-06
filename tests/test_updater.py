import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from modules.update import github
from modules.update.github import GitHubReleaseClient, UpdateError
from modules.update.model import UpdatePhase, UpdateRelease
from modules.update.presentation import has_update_notice, localized_status
from modules.update.service import UpdateService
from modules.config.settings import Settings
from modules.update import install
from modules.update.transaction import (
    TransactionPhase,
    create_legacy_transaction,
    create_transaction,
    load_transaction,
    set_phase,
    write_health_ack,
)


def _load_helper():
    helper = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "packaging/windows/update_helper.py")
    )
    # Transaction tests inject Popen on every platform. Native Job ownership is
    # exercised separately in test_update_process.py.
    # Their acknowledgements also use synthetic child PIDs. Real health-process
    # observation is exercised separately in test_update_health.py.
    helper["apply"].__globals__["_health_process_is_running"] = lambda *_args, **_kwargs: True
    helper["apply"].__globals__["_launch_update"] = (
        lambda command, *, cwd: helper["subprocess"].Popen(command, cwd=cwd)
    )
    return helper


def release_payload(version=4, *, checksum=True):
    name = f"FH-DualSense-Enhanced-R{version}.exe"
    assets = [
        {
            "name": name,
            "browser_download_url": f"https://example.test/{name}",
            "size": 8,
        }
    ]
    if checksum:
        assets.append(
            {
                "name": name + ".sha256",
                "browser_download_url": f"https://example.test/{name}.sha256",
                "size": 80,
            }
        )
    return {
        "tag_name": f"R{version}",
        "draft": False,
        "prerelease": False,
        "body": "中文更新说明",
        "html_url": f"https://example.test/R{version}",
        "assets": assets,
    }


def test_frozen_helper_copy_is_reused_when_bytes_match(tmp_path, monkeypatch):
    root = tmp_path / "bundle"
    bundled = root / "data" / "FH-DualSense-Update-Helper.exe"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"helper-r7")
    update_dir = tmp_path / "updates"
    update_dir.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(install.paths, "ROOT", root)

    first = install._helper_prefix(update_dir)
    monkeypatch.setattr(
        install.shutil,
        "copy2",
        lambda *_args, **_kwargs: pytest.fail("matching helper must not be overwritten"),
    )
    second = install._helper_prefix(update_dir)

    expected = str(update_dir / "FH-DualSense-Update-Helper.exe")
    assert first == [expected]
    assert second == [expected]


def test_release_parser_selects_canonical_asset_and_requires_checksum():
    parsed = GitHubReleaseClient._parse_release(release_payload())
    assert parsed is not None
    assert parsed.version == 4
    assert parsed.asset_name == "FH-DualSense-Enhanced-R4.exe"
    assert GitHubReleaseClient._parse_release(release_payload(checksum=False)) is None
    legacy = release_payload()
    legacy["assets"][0]["name"] = "FH-DualSense-Enhanced-R4-legacy-ui.exe"
    assert GitHubReleaseClient._parse_release(legacy) is None

    malformed_size = release_payload()
    malformed_size["assets"][0]["size"] = "not-a-number"
    assert GitHubReleaseClient._parse_release(malformed_size) is None

    duplicate = release_payload()
    duplicate["assets"].append(dict(duplicate["assets"][0]))
    assert GitHubReleaseClient._parse_release(duplicate) is None


def test_update_request_rejects_non_https_before_opening_network(monkeypatch):
    monkeypatch.setattr(
        github.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("unsafe URL must be rejected locally"),
    )

    with pytest.raises(UpdateError, match="HTTPS"):
        github._request("file:///tmp/update.exe", timeout=1.0, max_bytes=1024)


def test_update_request_rejects_an_unsafe_redirect(monkeypatch):
    class RedirectResponse(FakeResponse):
        def geturl(self):
            return "http://example.test/update.exe"

    response = RedirectResponse(b"payload")
    monkeypatch.setattr(
        github.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: response,
    )

    with pytest.raises(UpdateError, match="unsafe URL"):
        github._request("https://example.test/update.exe", timeout=1.0, max_bytes=1024)


def test_frozen_r4_client_can_select_the_canonical_r5_release(monkeypatch):
    payload = json.dumps([release_payload(4), release_payload(5)]).encode("utf-8")
    monkeypatch.setattr(github, "_request", lambda *_args, **_kwargs: FakeResponse(payload))

    release = GitHubReleaseClient().latest(current_version=4)

    assert release is not None
    assert release.tag == "R5"
    assert release.asset_name == "FH-DualSense-Enhanced-R5.exe"


@pytest.mark.parametrize("tag", ["4", "v4", "R4-beta", "R4.0"])
def test_release_parser_rejects_non_release_tags(tag):
    payload = release_payload()
    payload["tag_name"] = tag
    assert GitHubReleaseClient._parse_release(payload) is None


class FakeResponse:
    def __init__(self, payload):
        self.payload = io.BytesIO(payload)
        self.headers = {"Content-Length": str(len(payload))}

    def read(self, size=-1):
        return self.payload.read(size)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_download_verifies_sha256_and_pe_header(monkeypatch, tmp_path):
    exe = b"MZ" + b"r4-test"
    digest = hashlib.sha256(exe).hexdigest()
    release = UpdateRelease(
        version=4,
        tag="R4",
        body="",
        html_url="https://example.test/R4",
        asset_name="FH-DualSense-Enhanced-R4.exe",
        asset_url="https://example.test/app.exe",
        asset_size=len(exe),
        checksum_url="https://example.test/app.exe.sha256",
    )

    def fake_request(url, **_kwargs):
        return FakeResponse(
            (digest + f"  {release.asset_name}\n").encode()
            if url.endswith("sha256")
            else exe
        )

    monkeypatch.setattr(github, "_request", fake_request)
    output = tmp_path / release.asset_name
    actual = GitHubReleaseClient().download(release, output)
    assert actual == digest
    assert output.read_bytes() == exe


def test_download_removes_partial_file_on_bad_checksum(monkeypatch, tmp_path):
    exe = b"MZbroken"
    release = UpdateRelease(
        version=4,
        tag="R4",
        body="",
        html_url="https://example.test/R4",
        asset_name="app.exe",
        asset_url="https://example.test/app.exe",
        asset_size=len(exe),
        checksum_url="https://example.test/app.exe.sha256",
    )

    def fake_request(url, **_kwargs):
        return FakeResponse(("0" * 64).encode() if url.endswith("sha256") else exe)

    monkeypatch.setattr(github, "_request", fake_request)
    output = tmp_path / "app.exe"
    with pytest.raises(UpdateError, match="SHA-256"):
        GitHubReleaseClient().download(release, output)
    assert not output.exists()
    assert not output.with_suffix(".exe.part").exists()


@pytest.mark.parametrize(
    "sidecar",
    [
        "{digest}  FH-DualSense-Enhanced-R99.exe\n",
        "{digest}\n{digest}\n",
        "prefix {digest} suffix\n",
    ],
)
def test_download_rejects_ambiguous_or_wrong_asset_checksum(sidecar, monkeypatch, tmp_path):
    exe = b"MZ-checksum-contract"
    digest = hashlib.sha256(exe).hexdigest()
    release = UpdateRelease(
        version=4,
        tag="R4",
        body="",
        html_url="https://example.test/R4",
        asset_name="FH-DualSense-Enhanced-R4.exe",
        asset_url="https://example.test/app.exe",
        asset_size=len(exe),
        checksum_url="https://example.test/app.exe.sha256",
    )

    def fake_request(url, **_kwargs):
        payload = sidecar.format(digest=digest).encode() if url.endswith("sha256") else exe
        return FakeResponse(payload)

    monkeypatch.setattr(github, "_request", fake_request)
    with pytest.raises(UpdateError, match="checksum"):
        GitHubReleaseClient().download(release, tmp_path / release.asset_name)


class FakeClient:
    def __init__(self, release=None):
        self.release = release

    def latest(self, **_kwargs):
        return self.release


def test_update_service_reports_available(monkeypatch, tmp_path):
    from modules.update import service

    release = GitHubReleaseClient._parse_release(release_payload())
    monkeypatch.setattr(service.paths, "DATA", tmp_path)
    updater = UpdateService(Settings(), client=FakeClient(release))
    updater._check_impl(background=False)
    snapshot = updater.snapshot()
    assert snapshot.phase is UpdatePhase.AVAILABLE
    assert snapshot.release == release


def test_update_service_reports_up_to_date(monkeypatch, tmp_path):
    from modules.update import service

    monkeypatch.setattr(service.paths, "DATA", tmp_path)
    updater = UpdateService(Settings(), client=FakeClient())
    updater._check_impl(background=False)
    assert updater.snapshot().phase is UpdatePhase.UP_TO_DATE


@pytest.mark.parametrize("check_result", ["same", "offline", "none"])
def test_verified_pending_update_round_trips_across_restart(monkeypatch, tmp_path, check_result):
    from modules.update import service

    update_dir = tmp_path / "updates"
    update_dir.mkdir()
    future_version = service._current_version() + 1
    staged = update_dir / f"FH-DualSense-Enhanced-R{future_version}.exe"
    staged.write_bytes(b"MZ-persisted-update")
    release = UpdateRelease(
        version=future_version,
        tag=f"R{future_version}",
        body="release",
        html_url=f"https://example.test/R{future_version}",
        asset_name=staged.name,
        asset_url=f"https://example.test/R{future_version}.exe",
        asset_size=staged.stat().st_size,
        checksum_url=f"https://example.test/R{future_version}.exe.sha256",
    )
    monkeypatch.setattr(service.paths, "DATA", tmp_path)
    writer = UpdateService(Settings(), client=FakeClient())
    digest = hashlib.sha256(staged.read_bytes()).hexdigest()
    writer._save_pending(release, staged, digest)

    reader = UpdateService(Settings(), client=FakeClient())

    assert reader.snapshot().phase is UpdatePhase.READY
    assert reader.snapshot().release == release
    assert reader.snapshot().staged_path == str(staged.resolve())

    if check_result == "offline":
        def offline(**_kwargs):
            raise UpdateError("offline")
        monkeypatch.setattr(reader.client, "latest", offline)
    elif check_result == "same":
        reader.client.release = release
    reader._check_impl(background=True)
    assert reader.snapshot().phase is UpdatePhase.READY
    assert reader.snapshot().staged_path == str(staged.resolve())


def test_corrupt_pending_update_is_discarded_without_deleting_the_candidate(
    monkeypatch,
    tmp_path,
):
    from modules.update import service

    update_dir = tmp_path / "updates"
    update_dir.mkdir()
    staged = update_dir / "FH-DualSense-Enhanced-R9.exe"
    staged.write_bytes(b"not-an-executable")
    release = UpdateRelease(
        version=9,
        tag="R9",
        body="release",
        html_url="https://example.test/R9",
        asset_name=staged.name,
        asset_url="https://example.test/R9.exe",
        asset_size=staged.stat().st_size,
        checksum_url="https://example.test/R9.exe.sha256",
    )
    monkeypatch.setattr(service.paths, "DATA", tmp_path)
    writer = UpdateService(Settings(), client=FakeClient())
    writer._save_pending(release, staged, hashlib.sha256(staged.read_bytes()).hexdigest())

    reader = UpdateService(Settings(), client=FakeClient())

    assert reader.snapshot().phase is UpdatePhase.IDLE
    assert not (update_dir / "pending.json").exists()
    assert staged.read_bytes() == b"not-an-executable"


def test_update_status_presentation_localizes_phase_and_release_tag():
    def translate(value):
        return f"T:{value}"

    release = GitHubReleaseClient._parse_release(release_payload())

    assert localized_status(
        UpdateService(Settings(), client=FakeClient()).snapshot(),
        translate,
    ) == "T:Update status: idle"
    available = UpdateService(Settings(), client=FakeClient(release))
    available._check_impl(background=False)
    assert localized_status(available.snapshot(), translate) == "T:Update available: R4"
    assert has_update_notice(available.snapshot()) is True

    up_to_date = UpdateService(Settings(), client=FakeClient())
    up_to_date._check_impl(background=False)
    assert has_update_notice(up_to_date.snapshot()) is False


def test_unsupported_runtime_cannot_start_or_install_updates(tmp_path, monkeypatch):
    from modules.update import service

    monkeypatch.setattr(service.paths, "DATA", tmp_path)
    updater = UpdateService(
        Settings(),
        client=FakeClient(),
        supported=False,
    )

    assert updater.check_now() is False
    assert updater.download() is False
    assert "Windows standalone EXE" in updater.snapshot().message
    with pytest.raises(RuntimeError, match="Windows standalone EXE"):
        updater.install_on_exit()


def test_failed_helper_launch_restores_ready_state_for_retry(tmp_path, monkeypatch):
    from modules.update import service

    staged = tmp_path / "FH-DualSense-Enhanced-R9.exe"
    updater = UpdateService(Settings(), client=FakeClient())
    updater._last_sha256 = "a" * 64
    updater._set(
        phase=UpdatePhase.READY,
        message="Update ready to install",
        staged_path=str(staged),
    )
    monkeypatch.setattr(
        service,
        "launch_update_helper",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("instance conflict")),
    )

    with pytest.raises(RuntimeError, match="instance conflict"):
        updater.install_on_exit()

    assert updater.snapshot().phase is UpdatePhase.READY
    assert updater.snapshot().staged_path == str(staged)


def test_self_update_support_requires_frozen_windows(monkeypatch):
    monkeypatch.setattr(install.sys, "platform", "win32")
    monkeypatch.delattr(install.sys, "frozen", raising=False)
    assert install.self_update_supported() is False

    monkeypatch.setattr(install.sys, "frozen", True, raising=False)
    assert install.self_update_supported() is True

    monkeypatch.setattr(install.sys, "platform", "linux")
    assert install.self_update_supported() is False


class FakeRunningProcess:
    def __init__(self, pid=456):
        self.pid = pid
        self.running = True

    def poll(self):
        return None if self.running else 0

    def terminate(self):
        self.running = False

    def kill(self):
        self.running = False

    def wait(self, timeout=None):
        del timeout
        if self.running:
            raise subprocess.TimeoutExpired("fake", 0)
        return 0


def test_update_helper_commits_side_by_side_without_old_file(tmp_path, monkeypatch):
    helper = _load_helper()
    target = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    target.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=target,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="a" * 32,
        token="helper-test-token-with-24-bytes",
    )
    helper["wait_for_pid"].__globals__["wait_for_pid"] = lambda *_args: None
    launched = []

    def fake_popen(command, **kwargs):
        launched.append((command, kwargs))
        process = FakeRunningProcess()
        if Path(command[0]).name == "FH-DualSense-Enhanced-R7.exe":
            health = {
                "schema": 1,
                "transaction_id": transaction.transaction_id,
                "token": transaction.token,
                # PyInstaller one-file writes health from its inner child PID,
                # not the outer bootloader PID returned by Popen.
                "pid": process.pid + 1,
                "version": 7,
                "executable": str(transaction.new),
                "sha256": transaction.new_sha256,
                "initialized_at": 200.0,
            }
            plan.with_name("health.json").write_text(json.dumps(health), encoding="utf-8")
        return process

    monkeypatch.setattr(
        helper["subprocess"],
        "Popen",
        fake_popen,
    )
    monkeypatch.setitem(helper["apply"].__globals__, "migrate_shortcuts", lambda *_args: ([], []))

    helper["apply"](plan, survival_seconds=0)

    assert not target.exists()
    assert transaction.new.read_bytes() == b"MZ-new"
    assert not Path(str(target) + ".old").exists()
    assert load_transaction(plan).phase is TransactionPhase.COMMITTED
    assert launched[0][0] == [
        str(transaction.new),
        "--fhds-update-transaction",
        transaction.transaction_id,
        "--fhds-update-token",
        transaction.token,
    ]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("created_at", float("nan"), "timestamp"),
        ("created_at", True, "timestamp"),
        ("pid", 0, "pid"),
        ("pid", "123", "pid"),
        ("new_version", 7.0, "new_version"),
        ("new_sha256", "not-a-sha256", "checksum"),
        ("legacy_backup_path", {"path": "bad"}, "backup path"),
    ],
)
def test_update_helper_rejects_malformed_transaction_fields(tmp_path, field, value, message):
    helper = _load_helper()
    target = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    target.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    _transaction, plan_path = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=target,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="f" * 32,
        token="malformed-helper-test-token",
    )
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload[field] = value
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        helper["_load_plan"](plan_path)


def test_healthy_update_removes_all_strictly_named_older_releases_and_sidecars(
    tmp_path, monkeypatch
):
    helper = _load_helper()
    r5 = tmp_path / "FH-DualSense-Enhanced-R5.exe"
    r5_old = tmp_path / "FH-DualSense-Enhanced-R5.exe.old"
    r5_sidecar = tmp_path / "FH-DualSense-Enhanced-R5.exe.sha256"
    r6 = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    r8 = tmp_path / "FH-DualSense-Enhanced-R8.exe"
    unrelated_old = tmp_path / "notes.old"
    for path in (r5, r5_old, r5_sidecar, r6, r8, unrelated_old):
        path.write_bytes(b"MZ-placeholder")
    new = tmp_path / "FH-DualSense-Enhanced-R7.exe"
    new.write_bytes(b"MZ-new")
    staged = tmp_path / "data" / "updates" / new.name
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=r6,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="e" * 32,
        token="stale-release-cleanup-token",
    )
    calls = []
    monkeypatch.setitem(
        helper["_continue_commit"].__globals__,
        "migrate_shortcuts",
        lambda old, target: calls.append((old, target)) or ([], []),
    )

    helper["_continue_commit"](plan, json.loads(plan.read_text(encoding="utf-8")))

    assert [old.name for old, _target in calls] == [r6.name, r5.name]
    assert all(target == transaction.new for _old, target in calls)
    assert transaction.new.is_file()
    assert not r6.exists()
    assert not r5.exists()
    assert not r5_old.exists()
    assert not r5_sidecar.exists()
    assert r8.is_file()
    assert unrelated_old.is_file()
    assert load_transaction(plan).phase is TransactionPhase.COMMITTED


def test_stale_release_scan_never_follows_a_canonical_named_symlink(tmp_path):
    helper = _load_helper()
    install = tmp_path / "install"
    outside = tmp_path / "outside"
    install.mkdir()
    outside.mkdir()
    new = install / "FH-DualSense-Enhanced-R7.exe"
    new.write_bytes(b"MZ-new")
    outside_target = outside / "do-not-delete.exe"
    outside_target.write_bytes(b"MZ-user")
    link = install / "FH-DualSense-Enhanced-R5.exe"
    try:
        link.symlink_to(outside_target)
    except OSError as exc:
        pytest.skip(f"file symlinks unavailable: {exc}")

    canonical, sidecars = helper["_stale_release_candidates"](new, 7)

    assert canonical == []
    assert sidecars == []
    assert outside_target.read_bytes() == b"MZ-user"


def test_stale_shortcut_failure_keeps_only_its_canonical_old_executable(
    tmp_path, monkeypatch
):
    helper = _load_helper()
    r5 = tmp_path / "FH-DualSense-Enhanced-R5.exe"
    r5_old = tmp_path / "FH-DualSense-Enhanced-R5.exe.old"
    r6 = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    for path in (r5, r5_old, r6):
        path.write_bytes(b"MZ-old")
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=r6,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="d" * 32,
        token="stale-shortcut-failure-token",
    )
    staged.replace(transaction.new)

    def migrate(old, _new):
        if old == r5.resolve():
            return [], ["Desktop/old-r5.lnk"]
        return ["Desktop/current.lnk"], []

    monkeypatch.setitem(helper["_continue_commit"].__globals__, "migrate_shortcuts", migrate)

    helper["_continue_commit"](plan, json.loads(plan.read_text(encoding="utf-8")))

    recovered = load_transaction(plan)
    assert recovered.phase is TransactionPhase.CLEANUP_PENDING
    assert recovered.failed_shortcuts == ("Desktop/old-r5.lnk",)
    assert r5.is_file()
    assert not r5_old.exists()
    assert not r6.exists()
    assert transaction.new.is_file()


def test_update_helper_rolls_back_when_new_process_is_not_healthy(tmp_path, monkeypatch):
    helper = _load_helper()
    target = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    target.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=target,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="b" * 32,
        token="rollback-test-token-with-24-bytes",
    )
    helper["wait_for_pid"].__globals__["wait_for_pid"] = lambda *_args: None
    launched = []
    monkeypatch.setattr(
        helper["subprocess"],
        "Popen",
        lambda command, **kwargs: launched.append(command) or FakeRunningProcess(),
    )
    monkeypatch.setitem(
        helper["apply"].__globals__,
        "wait_for_health",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("not healthy")),
    )

    with pytest.raises(TimeoutError, match="not healthy"):
        helper["apply"](plan, survival_seconds=0)

    assert target.read_bytes() == b"MZ-old"
    assert not transaction.new.exists()
    assert load_transaction(plan).phase is TransactionPhase.ROLLED_BACK
    assert launched[-1] == [str(target)]


def test_healthy_new_version_is_not_rolled_back_by_shortcut_subsystem_failure(tmp_path, monkeypatch):
    helper = _load_helper()
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="5" * 32,
        token="healthy-shortcut-failure-token",
    )
    helper["wait_for_pid"].__globals__["wait_for_pid"] = lambda *_args: None

    def fake_popen(command, **_kwargs):
        process = FakeRunningProcess()
        if Path(command[0]) == transaction.new:
            plan.with_name("health.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "transaction_id": transaction.transaction_id,
                        "token": transaction.token,
                        "pid": process.pid,
                        "version": 7,
                        "executable": str(transaction.new),
                        "sha256": transaction.new_sha256,
                        "initialized_at": 200.0,
                    }
                ),
                encoding="utf-8",
            )
        return process

    monkeypatch.setattr(helper["subprocess"], "Popen", fake_popen)
    monkeypatch.setitem(
        helper["apply"].__globals__,
        "migrate_shortcuts",
        lambda *_args: (_ for _ in ()).throw(OSError("shell unavailable")),
    )

    with pytest.raises(OSError, match="shell unavailable"):
        helper["apply"](plan, survival_seconds=0)

    assert old.is_file()
    assert transaction.new.is_file()
    assert load_transaction(plan).phase is TransactionPhase.CLEANUP_PENDING


def test_recovery_rolls_back_unconfirmed_side_by_side_update(tmp_path):
    helper = _load_helper()
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="f" * 32,
        token="recovery-rollback-token-24-bytes",
    )
    staged.replace(transaction.new)
    set_phase(plan, TransactionPhase.WAITING_HEALTH)

    helper["recover"](plan)

    assert old.read_bytes() == b"MZ-old"
    assert not transaction.new.exists()
    assert load_transaction(plan).phase is TransactionPhase.ROLLED_BACK


def test_recovery_refuses_to_delete_changed_unconfirmed_target(tmp_path):
    helper = _load_helper()
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="9" * 32,
        token="changed-target-token-with-24-bytes",
    )
    staged.replace(transaction.new)
    transaction.new.write_bytes(b"MZ-someone-else")
    set_phase(plan, TransactionPhase.WAITING_HEALTH)

    with pytest.raises(ValueError, match="refusing to delete"):
        helper["recover"](plan)

    assert transaction.new.read_bytes() == b"MZ-someone-else"
    assert load_transaction(plan).phase is TransactionPhase.WAITING_HEALTH


def test_recovery_closes_move_to_journal_crash_gap(tmp_path):
    helper = _load_helper()
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="0" * 32,
        token="move-journal-gap-token-with-24-bytes",
    )
    set_phase(plan, TransactionPhase.WAITING_OLD_EXIT)
    staged.replace(transaction.new)

    helper["recover"](plan)

    assert old.read_bytes() == b"MZ-old"
    assert not transaction.new.exists()
    assert load_transaction(plan).phase is TransactionPhase.ROLLED_BACK


def test_preexisting_matching_target_is_preserved_before_adoption(tmp_path):
    helper = _load_helper()
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    new = tmp_path / staged.name
    new.write_bytes(b"MZ-new")
    _transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="a0" * 16,
        token="preexisting-target-token-24-bytes",
    )
    helper["wait_for_pid"].__globals__["wait_for_pid"] = lambda *_args: (_ for _ in ()).throw(
        TimeoutError("old still running")
    )

    with pytest.raises(TimeoutError, match="old still running"):
        helper["apply"](plan)

    assert new.read_bytes() == b"MZ-new"
    assert staged.read_bytes() == b"MZ-new"
    assert load_transaction(plan).phase is TransactionPhase.ROLLED_BACK


def test_failed_rollback_stays_recoverable_instead_of_claiming_success(tmp_path, monkeypatch):
    helper = _load_helper()
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="b0" * 16,
        token="rollback-pending-token-24-bytes",
    )
    helper["wait_for_pid"].__globals__["wait_for_pid"] = lambda *_args: None
    monkeypatch.setattr(helper["subprocess"], "Popen", lambda *_args, **_kwargs: FakeRunningProcess())
    monkeypatch.setitem(
        helper["apply"].__globals__,
        "wait_for_health",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("not healthy")),
    )
    real_unlink = helper["_unlink_with_retry"]
    monkeypatch.setitem(
        helper["apply"].__globals__,
        "_unlink_with_retry",
        lambda path, **kwargs: False if Path(path) == transaction.new else real_unlink(path, **kwargs),
    )

    with pytest.raises(RuntimeError, match="rollback remains pending"):
        helper["apply"](plan)

    assert transaction.new.is_file()
    assert old.is_file()
    assert load_transaction(plan).phase is TransactionPhase.WAITING_HEALTH


def test_recovery_finishes_shortcuts_and_cleanup_after_valid_health(tmp_path, monkeypatch):
    helper = _load_helper()
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="1" * 32,
        token="recovery-commit-token-with-24-bytes",
    )
    staged.replace(transaction.new)
    set_phase(plan, TransactionPhase.WAITING_HEALTH)
    write_health_ack(
        root=plan.parent.parent,
        transaction_id=transaction.transaction_id,
        token=transaction.token,
        executable=transaction.new,
        version=7,
        pid=456,
    )
    monkeypatch.setitem(
        helper["recover"].__globals__,
        "migrate_shortcuts",
        lambda *_args: (["Desktop/FHDS.lnk"], []),
    )
    monkeypatch.setitem(
        helper["recover"].__globals__,
        "_health_process_is_running",
        lambda *_args, **_kwargs: True,
    )

    helper["recover"](plan, health_survival_seconds=0)

    recovered = load_transaction(plan)
    assert recovered.phase is TransactionPhase.COMMITTED
    assert recovered.migrated_shortcuts == ("Desktop/FHDS.lnk",)
    assert not old.exists()
    assert transaction.new.is_file()


def test_recovery_rolls_back_a_valid_ack_from_a_dead_process(tmp_path, monkeypatch):
    helper = _load_helper()
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="1b" * 16,
        token="dead-health-process-token-24-bytes",
    )
    staged.replace(transaction.new)
    set_phase(plan, TransactionPhase.WAITING_HEALTH)
    health = write_health_ack(
        root=plan.parent.parent,
        transaction_id=transaction.transaction_id,
        token=transaction.token,
        executable=transaction.new,
        version=7,
        pid=999_999,
    )
    monkeypatch.setitem(
        helper["recover"].__globals__,
        "_health_process_is_running",
        lambda *_args, **_kwargs: False,
    )

    helper["recover"](plan, health_survival_seconds=0)

    assert not health.exists()
    assert not transaction.new.exists()
    assert old.read_bytes() == b"MZ-old"
    assert load_transaction(plan).phase is TransactionPhase.ROLLED_BACK


def test_recovery_keeps_old_executable_when_shortcut_retry_still_fails(tmp_path, monkeypatch):
    helper = _load_helper()
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="2" * 32,
        token="recovery-shortcut-token-24-bytes",
    )
    staged.replace(transaction.new)
    set_phase(plan, TransactionPhase.CLEANUP_PENDING)
    monkeypatch.setitem(
        helper["recover"].__globals__,
        "migrate_shortcuts",
        lambda *_args: ([], ["Desktop/locked.lnk"]),
    )

    helper["recover"](plan)

    recovered = load_transaction(plan)
    assert recovered.phase is TransactionPhase.CLEANUP_PENDING
    assert recovered.failed_shortcuts == ("Desktop/locked.lnk",)
    assert old.is_file()
    assert transaction.new.is_file()

    warnings = []
    monkeypatch.setitem(
        helper["_warn_shortcut_failures_once"].__globals__,
        "_show_warning",
        warnings.append,
    )
    helper["_warn_shortcut_failures_once"](plan)
    helper["_warn_shortcut_failures_once"](plan)

    assert len(warnings) == 1
    assert "Desktop/locked.lnk" in warnings[0]
    assert load_transaction(plan).shortcut_warning_shown is True


def test_launch_update_helper_writes_transaction_plan(tmp_path, monkeypatch):
    update_root = tmp_path / "data"
    target = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = update_root / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    target.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    monkeypatch.setattr(install.paths, "DATA", update_root)
    monkeypatch.delattr(install.sys, "frozen", raising=False)
    launched = []
    monkeypatch.setattr(
        install.subprocess,
        "Popen",
        lambda command, **kwargs: launched.append((command, kwargs)),
    )

    plan = install.launch_update_helper(
        staged,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        target=target,
        pid=321,
    )

    transaction = load_transaction(plan)
    assert transaction.phase is TransactionPhase.PREPARED
    assert transaction.old == target.resolve()
    assert transaction.new.name == "FH-DualSense-Enhanced-R7.exe"
    assert launched[0][0][-1] == str(plan)


def test_launch_update_helper_refuses_another_instance_in_same_directory(tmp_path, monkeypatch):
    target = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir()
    target.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    monkeypatch.setattr(
        install,
        "_other_install_instances",
        lambda *_args, **_kwargs: ((999, str(tmp_path / "FH-DualSense-Enhanced-R6.exe")),),
    )

    with pytest.raises(RuntimeError, match="close other"):
        install.launch_update_helper(
            staged,
            expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
            target=target,
            pid=321,
        )


def test_instance_guard_ignores_current_pyinstaller_onefile_parent(tmp_path, monkeypatch):
    executable = tmp_path / "FH-DualSense-Enhanced-R5.exe"
    processes = [
        type("Process", (), {"info": {"pid": 100, "ppid": 1, "exe": str(executable)}})(),
        type("Process", (), {"info": {"pid": 200, "ppid": 100, "exe": str(executable)}})(),
    ]
    monkeypatch.setattr(install.sys, "platform", "win32")
    monkeypatch.setattr(install.psutil, "process_iter", lambda _fields: processes)

    assert install._other_install_instances(tmp_path, current_pid=200) == ()


def test_instance_guard_still_reports_a_separate_onefile_pair(tmp_path, monkeypatch):
    executable = tmp_path / "FH-DualSense-Enhanced-R5.exe"
    processes = [
        type("Process", (), {"info": {"pid": 100, "ppid": 1, "exe": str(executable)}})(),
        type("Process", (), {"info": {"pid": 200, "ppid": 100, "exe": str(executable)}})(),
        type("Process", (), {"info": {"pid": 300, "ppid": 1, "exe": str(executable)}})(),
        type("Process", (), {"info": {"pid": 400, "ppid": 300, "exe": str(executable)}})(),
    ]
    monkeypatch.setattr(install.sys, "platform", "win32")
    monkeypatch.setattr(install.psutil, "process_iter", lambda _fields: processes)

    assert install._other_install_instances(tmp_path, current_pid=200) == (
        (300, str(executable.resolve())),
        (400, str(executable.resolve())),
    )


def test_instance_guard_skips_unreadable_records_and_keeps_scanning(tmp_path, monkeypatch):
    executable = tmp_path / "FH-DualSense-Enhanced-R5.exe"

    class UnreadableProcess:
        @property
        def info(self):
            raise install.psutil.AccessDenied(pid=123)

    records = [
        {"pid": "invalid", "ppid": 1, "exe": str(executable)},
        {"pid": 124, "ppid": "invalid", "exe": str(executable)},
        {"pid": 125, "ppid": 1, "exe": ""},
        {"pid": 126, "ppid": 1, "exe": str(tmp_path / "other.exe")},
        {"pid": 127, "ppid": 1, "exe": str(tmp_path / "other" / executable.name)},
        {"pid": 300, "ppid": 1, "exe": str(executable)},
    ]
    processes = [UnreadableProcess(), *(type("Process", (), {"info": info})() for info in records)]
    monkeypatch.setattr(install.sys, "platform", "win32")
    monkeypatch.setattr(install.psutil, "process_iter", lambda _fields: processes)

    assert install._other_install_instances(tmp_path, current_pid=200) == (
        (300, str(executable.resolve())),
    )


def test_restart_arguments_strip_both_internal_argument_forms():
    assert install._restart_args(
        [
            "--gui",
            "--fhds-update-transaction",
            "a" * 32,
            "--port=5300",
            "--fhds-update-token=secret-token",
            "--fhds-update-transaction=" + "b" * 32,
            "--tui",
        ]
    ) == ("--gui", "--port=5300", "--tui")


def test_legacy_bootstrap_refuses_a_separate_instance_before_copying(tmp_path, monkeypatch):
    running = tmp_path / "FH-DualSense-Enhanced-R5.exe"
    backup = Path(str(running) + ".old")
    running.write_bytes(b"MZ-r7")
    backup.write_bytes(b"MZ-r6")
    versions = {running.resolve(): 7, backup.resolve(): 6}
    monkeypatch.setattr(
        install,
        "_other_install_instances",
        lambda *_args, **_kwargs: ((999, str(running)),),
    )

    with pytest.raises(RuntimeError, match="close other"):
        install.launch_legacy_bootstrap(
            executable=running,
            current_version=7,
            pid=321,
            version_reader=lambda path: versions.get(Path(path).resolve()),
        )


def test_update_helper_consumes_r6_old_during_legacy_bootstrap(tmp_path, monkeypatch):
    helper = _load_helper()
    running = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    backup = Path(str(running) + ".old")
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    running.write_bytes(b"MZ-r7")
    staged.write_bytes(b"MZ-r7")
    backup.write_bytes(b"MZ-r6")
    transaction, plan = create_legacy_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        wrong_named_executable=running,
        backup=backup,
        new_version=7,
        pid=123,
        transaction_id="c" * 32,
        token="legacy-helper-token-with-24-bytes",
    )
    helper["wait_for_pid"].__globals__["wait_for_pid"] = lambda *_args: None

    def fake_popen(command, **_kwargs):
        process = FakeRunningProcess()
        if Path(command[0]) == transaction.new:
            plan.with_name("health.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "transaction_id": transaction.transaction_id,
                        "token": transaction.token,
                        "pid": process.pid,
                        "version": 7,
                        "executable": str(transaction.new),
                        "sha256": transaction.new_sha256,
                        "initialized_at": 200.0,
                    }
                ),
                encoding="utf-8",
            )
        return process

    monkeypatch.setattr(helper["subprocess"], "Popen", fake_popen)
    monkeypatch.setitem(helper["apply"].__globals__, "migrate_shortcuts", lambda *_args: ([], []))

    helper["apply"](plan, survival_seconds=0)

    assert transaction.new.read_bytes() == b"MZ-r7"
    assert not running.exists()
    assert not backup.exists()
    assert load_transaction(plan).phase is TransactionPhase.COMMITTED


def test_update_helper_legacy_health_failure_restores_real_r6(tmp_path, monkeypatch):
    helper = _load_helper()
    running = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    backup = Path(str(running) + ".old")
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    running.write_bytes(b"MZ-r7")
    staged.write_bytes(b"MZ-r7")
    backup.write_bytes(b"MZ-r6")
    transaction, plan = create_legacy_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        wrong_named_executable=running,
        backup=backup,
        new_version=7,
        pid=123,
        transaction_id="d" * 32,
        token="legacy-rollback-token-with-24-bytes",
    )
    helper["wait_for_pid"].__globals__["wait_for_pid"] = lambda *_args: None
    launched = []
    monkeypatch.setattr(
        helper["subprocess"],
        "Popen",
        lambda command, **_kwargs: launched.append(command) or FakeRunningProcess(),
    )
    monkeypatch.setitem(
        helper["apply"].__globals__,
        "wait_for_health",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("legacy unhealthy")),
    )

    with pytest.raises(TimeoutError, match="legacy unhealthy"):
        helper["apply"](plan, survival_seconds=0)

    assert running.read_bytes() == b"MZ-r6"
    assert not transaction.new.exists()
    assert not backup.exists()
    assert load_transaction(plan).phase is TransactionPhase.ROLLED_BACK
    assert launched[-1] == [str(running)]


def test_legacy_recovery_restores_backup_after_move_to_journal_crash(tmp_path):
    helper = _load_helper()
    running = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    backup = Path(str(running) + ".old")
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    running.write_bytes(b"MZ-r7")
    staged.write_bytes(b"MZ-r7")
    backup.write_bytes(b"MZ-r6")
    transaction, plan = create_legacy_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        wrong_named_executable=running,
        backup=backup,
        new_version=7,
        pid=123,
        transaction_id="e0" * 16,
        token="legacy-gap-token-with-24-bytes",
    )
    set_phase(plan, TransactionPhase.WAITING_OLD_EXIT)
    running.replace(transaction.new)

    helper["recover"](plan)

    assert running.read_bytes() == b"MZ-r6"
    assert not transaction.new.exists()
    assert not backup.exists()
    assert load_transaction(plan).phase is TransactionPhase.ROLLED_BACK


def test_healthy_legacy_gap_restores_old_before_shortcut_migration(tmp_path, monkeypatch):
    helper = _load_helper()
    running = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    backup = Path(str(running) + ".old")
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    running.write_bytes(b"MZ-r7")
    staged.write_bytes(b"MZ-r7")
    backup.write_bytes(b"MZ-r6")
    transaction, plan = create_legacy_transaction(
        root=tmp_path / "data" / "updates" / "transactions",
        staged=staged,
        wrong_named_executable=running,
        backup=backup,
        new_version=7,
        pid=123,
        transaction_id="f0" * 16,
        token="legacy-healthy-gap-token-24-bytes",
    )
    set_phase(plan, TransactionPhase.WAITING_OLD_EXIT)
    running.replace(transaction.new)
    write_health_ack(
        root=plan.parent.parent,
        transaction_id=transaction.transaction_id,
        token=transaction.token,
        executable=transaction.new,
        version=7,
        pid=456,
    )
    migrated_from = []

    def migrate(old, _new):
        migrated_from.append((Path(old), Path(old).read_bytes()))
        return [], []

    monkeypatch.setitem(helper["recover"].__globals__, "migrate_shortcuts", migrate)
    monkeypatch.setitem(
        helper["recover"].__globals__,
        "_health_process_is_running",
        lambda *_args, **_kwargs: True,
    )

    helper["recover"](plan, health_survival_seconds=0)

    assert migrated_from == [(running, b"MZ-r6")]
    assert transaction.new.read_bytes() == b"MZ-r7"
    assert not running.exists()
    assert not backup.exists()
    assert load_transaction(plan).phase is TransactionPhase.COMMITTED


def test_legacy_bootstrap_detection_requires_matching_embedded_versions(tmp_path):
    running = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    backup = Path(str(running) + ".old")
    running.write_bytes(b"MZ-r7")
    backup.write_bytes(b"MZ-r6")
    versions = {running.resolve(): 7, backup.resolve(): 6}

    candidate = install.detect_legacy_bootstrap(
        executable=running,
        current_version=7,
        version_reader=lambda path: versions.get(Path(path).resolve()),
    )

    assert candidate is not None
    assert candidate.executable == running.resolve()
    assert candidate.backup == backup.resolve()
    assert candidate.old_version == 6
    assert candidate.new_version == 7

    versions[running.resolve()] = 6
    assert install.detect_legacy_bootstrap(
        executable=running,
        current_version=7,
        version_reader=lambda path: versions.get(Path(path).resolve()),
    ) is None


def test_legacy_bootstrap_detection_accepts_filename_lag_from_prior_legacy_update(tmp_path):
    running = tmp_path / "FH-DualSense-Enhanced-R5.exe"
    backup = Path(str(running) + ".old")
    running.write_bytes(b"MZ-r7")
    backup.write_bytes(b"MZ-r6")
    versions = {running.resolve(): 7, backup.resolve(): 6}

    candidate = install.detect_legacy_bootstrap(
        executable=running,
        current_version=7,
        version_reader=lambda path: versions.get(Path(path).resolve()),
    )

    assert candidate is not None
    assert candidate.executable == running.resolve()
    assert candidate.backup == backup.resolve()
    assert candidate.old_version == 6
    assert candidate.new_version == 7

    versions[backup.resolve()] = 4
    assert install.detect_legacy_bootstrap(
        executable=running,
        current_version=7,
        version_reader=lambda path: versions.get(Path(path).resolve()),
    ) is None


def test_launch_legacy_bootstrap_repairs_filename_lag_and_starts_new_helper(
    tmp_path, monkeypatch
):
    running = tmp_path / "FH-DualSense-Enhanced-R5.exe"
    backup = Path(str(running) + ".old")
    running.write_bytes(b"MZ-r7")
    backup.write_bytes(b"MZ-r6")
    data = tmp_path / "data"
    monkeypatch.setattr(install.paths, "DATA", data)
    monkeypatch.delattr(install.sys, "frozen", raising=False)
    versions = {running.resolve(): 7, backup.resolve(): 6}
    launched = []
    monkeypatch.setattr(
        install.subprocess,
        "Popen",
        lambda command, **kwargs: launched.append((command, kwargs)),
    )

    plan = install.launch_legacy_bootstrap(
        executable=running,
        current_version=7,
        pid=321,
        argv=["--gui"],
        version_reader=lambda path: versions.get(Path(path).resolve()),
    )

    assert plan is not None
    transaction = load_transaction(plan)
    assert transaction.legacy_r6_bootstrap is True
    assert transaction.args == ("--gui",)
    assert transaction.staged.read_bytes() == b"MZ-r7"
    assert transaction.old == running.resolve()
    assert transaction.old_version == 5
    assert transaction.new.name == "FH-DualSense-Enhanced-R7.exe"
    assert transaction.legacy_backup_path == str(backup.resolve())
    assert launched[0][0][-1] == str(plan)


@pytest.mark.skipif(os.name != "nt", reason="Win32 wait-handle contract")
def test_update_helper_waits_for_windows_process_without_signalling_it():
    helper = _load_helper()
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.15)"])
    started = time.monotonic()

    helper["wait_for_pid"](child.pid, timeout=2.0)

    assert time.monotonic() - started >= 0.10
    assert child.wait(timeout=1.0) == 0


def test_update_helper_transaction_lock_is_cross_process(tmp_path):
    helper_path = Path(__file__).resolve().parents[1] / "packaging/windows/update_helper.py"
    plan = tmp_path / "transactions" / ("1a" * 16) / "transaction.json"
    plan.parent.mkdir(parents=True)
    ready = tmp_path / "lock-ready.txt"
    release = tmp_path / "lock-release.txt"
    script = f"""
import runpy
import time
from pathlib import Path
h = runpy.run_path({str(helper_path)!r})
with h['_transaction_lock'](Path({str(plan)!r})) as acquired:
    Path({str(ready)!r}).write_text(str(acquired), encoding='utf-8')
    deadline = time.monotonic() + 10.0
    while not Path({str(release)!r}).exists() and time.monotonic() < deadline:
        time.sleep(0.05)
"""
    child = subprocess.Popen([sys.executable, "-c", script])
    try:
        deadline = time.monotonic() + 5.0
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.read_text(encoding="utf-8") == "True"
        helper = runpy.run_path(str(helper_path))
        with helper["_transaction_lock"](plan) as acquired:
            assert acquired is False
    finally:
        release.write_text("release", encoding="utf-8")
        child.wait(timeout=5.0)

    assert child.returncode == 0


def test_update_helper_rejects_package_changed_during_old_process_wait(tmp_path, monkeypatch):
    helper = _load_helper()
    target = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    target.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=staged.parent / "transactions",
        staged=staged,
        target=target,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="b" * 32,
        token="helper-test-token-with-24-bytes",
    )
    monkeypatch.setitem(
        helper["apply"].__globals__, "wait_for_pid",
        lambda *_args: staged.write_bytes(b"MZ-tampered"),
    )
    launched = []
    monkeypatch.setattr(
        helper["subprocess"], "Popen",
        lambda command, **_kwargs: launched.append(command) or FakeRunningProcess(),
    )
    with pytest.raises(ValueError, match="changed while waiting"):
        helper["apply"](plan, survival_seconds=0)
    assert target.read_bytes() == b"MZ-old"
    assert not transaction.new.exists()
    assert all(Path(command[0]) == target for command in launched)
    assert load_transaction(plan).phase is TransactionPhase.ROLLED_BACK


@pytest.mark.parametrize("launch_failure", ["assign", "resume"])
@pytest.mark.parametrize("termination_confirmed", [False, True])
def test_failed_launch_rolls_back_only_after_confirmed_termination(
    tmp_path, monkeypatch, launch_failure, termination_confirmed,
):
    helper = _load_helper()
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    staged = tmp_path / "data" / "updates" / "FH-DualSense-Enhanced-R7.exe"
    staged.parent.mkdir(parents=True)
    old.write_bytes(b"MZ-old")
    staged.write_bytes(b"MZ-new")
    transaction, plan = create_transaction(
        root=staged.parent / "transactions",
        staged=staged,
        target=old,
        expected_sha256=hashlib.sha256(b"MZ-new").hexdigest(),
        pid=123,
        transaction_id="c" * 32,
        token="unconfirmed-launch-token-24-bytes",
    )
    process_module = ModuleType("update_process")
    process_module.__dict__.update(runpy.run_path(str(
        Path(__file__).resolve().parents[1] / "packaging/windows/update_process.py"
    )))
    api = Mock()
    api.create_suspended.return_value = ("process", "thread", 123)
    getattr(api, launch_failure).side_effect = OSError("launch failed")
    api.active_processes.return_value = 0
    if not termination_confirmed:
        api.terminate_job.side_effect = OSError("job termination failed")
        api.terminate_process.side_effect = OSError("process termination failed")
    monkeypatch.setitem(process_module.JobProcess.__init__.__globals__, "_WindowsAPI", lambda: api)
    monkeypatch.setitem(sys.modules, "update_process", process_module)
    globals_ = helper["apply"].__globals__
    monkeypatch.setitem(globals_, "_launch_update", helper["_launch_update"])
    monkeypatch.setitem(globals_, "os", SimpleNamespace(name="nt", path=os.path))
    monkeypatch.setitem(globals_, "wait_for_pid", lambda *_args: None)
    launched = []
    monkeypatch.setattr(
        helper["subprocess"], "Popen",
        lambda command, **_kwargs: launched.append(command) or FakeRunningProcess(),
    )

    error_type = OSError if termination_confirmed else RuntimeError
    error_message = "launch failed" if termination_confirmed else "rollback remains pending"
    with pytest.raises(error_type, match=error_message):
        helper["apply"](plan)

    assert old.read_bytes() == b"MZ-old"
    if termination_confirmed:
        assert load_transaction(plan).phase is TransactionPhase.ROLLED_BACK
        assert not transaction.new.exists()
        assert [Path(command[0]) for command in launched] == [old]
    else:
        assert load_transaction(plan).phase is TransactionPhase.WAITING_HEALTH
        assert transaction.new.read_bytes() == b"MZ-new"
        assert launched == []
