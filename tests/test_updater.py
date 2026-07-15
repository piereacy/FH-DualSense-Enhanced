import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time

import pytest

from modules.update import github
from modules.update.github import GitHubReleaseClient, UpdateError
from modules.update.model import UpdatePhase, UpdateRelease
from modules.update.presentation import localized_status
from modules.update.service import UpdateService
from modules.config.settings import Settings
from modules.update import install


def release_payload(version=4, variant="Miku-Console", *, checksum=True):
    name = f"FH-DualSense-Enhanced-R{version}-{variant}.exe"
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


def test_release_parser_selects_matching_variant_and_requires_checksum():
    parsed = GitHubReleaseClient._parse_release(release_payload(), "console")
    assert parsed is not None
    assert parsed.version == 4
    assert parsed.asset_name.endswith("Miku-Console.exe")
    assert GitHubReleaseClient._parse_release(release_payload(checksum=False), "console") is None
    assert GitHubReleaseClient._parse_release(release_payload(), "stage") is None


@pytest.mark.parametrize("tag", ["4", "v4", "R4-beta", "R4.0"])
def test_release_parser_rejects_non_release_tags(tag):
    payload = release_payload()
    payload["tag_name"] = tag
    assert GitHubReleaseClient._parse_release(payload, "console") is None


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
        asset_name="FH-DualSense-Enhanced-R4-Miku-Console.exe",
        asset_url="https://example.test/app.exe",
        asset_size=len(exe),
        checksum_url="https://example.test/app.exe.sha256",
    )

    def fake_request(url, **_kwargs):
        return FakeResponse((digest + "  app.exe\n").encode() if url.endswith("sha256") else exe)

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


class FakeClient:
    def __init__(self, release=None):
        self.release = release

    def latest(self, **_kwargs):
        return self.release


def test_update_service_reports_available(monkeypatch, tmp_path):
    from modules.update import service

    release = GitHubReleaseClient._parse_release(release_payload(), "console")
    monkeypatch.setattr(service.paths, "DATA", tmp_path)
    updater = UpdateService(Settings(), variant="console", client=FakeClient(release))
    updater._check_impl(background=False)
    snapshot = updater.snapshot()
    assert snapshot.phase is UpdatePhase.AVAILABLE
    assert snapshot.release == release


def test_update_service_reports_up_to_date(monkeypatch, tmp_path):
    from modules.update import service

    monkeypatch.setattr(service.paths, "DATA", tmp_path)
    updater = UpdateService(Settings(), variant="console", client=FakeClient())
    updater._check_impl(background=False)
    assert updater.snapshot().phase is UpdatePhase.UP_TO_DATE


def test_update_status_presentation_localizes_phase_and_release_tag():
    translate = lambda value: f"T:{value}"
    release = GitHubReleaseClient._parse_release(release_payload(), "console")

    assert localized_status(
        UpdateService(Settings(), variant="console", client=FakeClient()).snapshot(),
        translate,
    ) == "T:Update status: idle"
    available = UpdateService(Settings(), variant="console", client=FakeClient(release))
    available._check_impl(background=False)
    assert localized_status(available.snapshot(), translate) == "T:Update available: R4"


def test_unsupported_runtime_cannot_start_or_install_updates(tmp_path, monkeypatch):
    from modules.update import service

    monkeypatch.setattr(service.paths, "DATA", tmp_path)
    updater = UpdateService(
        Settings(),
        variant="console",
        client=FakeClient(),
        supported=False,
    )

    assert updater.check_now() is False
    assert updater.download() is False
    assert "Windows standalone EXE" in updater.snapshot().message
    with pytest.raises(RuntimeError, match="Windows standalone EXE"):
        updater.install_on_exit()


def test_self_update_support_requires_frozen_windows(monkeypatch):
    monkeypatch.setattr(install.sys, "platform", "win32")
    monkeypatch.delattr(install.sys, "frozen", raising=False)
    assert install.self_update_supported() is False

    monkeypatch.setattr(install.sys, "frozen", True, raising=False)
    assert install.self_update_supported() is True

    monkeypatch.setattr(install.sys, "platform", "linux")
    assert install.self_update_supported() is False


def test_update_helper_atomically_replaces_target_and_keeps_rollback(tmp_path, monkeypatch):
    helper = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "packaging/windows/update_helper.py")
    )
    target = tmp_path / "FH-DualSense-Enhanced-R4-Miku-Console.exe"
    staged = tmp_path / "staged.exe"
    plan = tmp_path / "install-plan.json"
    target.write_bytes(b"old")
    staged.write_bytes(b"new")
    plan.write_text(json.dumps({
        "pid": 123,
        "staged": str(staged),
        "target": str(target),
        "sha256": hashlib.sha256(b"new").hexdigest(),
        "args": [],
    }), encoding="utf-8")
    helper["wait_for_pid"].__globals__["wait_for_pid"] = lambda *_args: None
    launched = []
    monkeypatch.setattr(
        helper["subprocess"],
        "Popen",
        lambda command, **kwargs: launched.append((command, kwargs)),
    )

    helper["apply"](plan)

    assert target.read_bytes() == b"new"
    assert Path(str(target) + ".old").read_bytes() == b"old"
    assert not plan.exists()
    assert launched[0][0] == [str(target)]


@pytest.mark.skipif(os.name != "nt", reason="Win32 wait-handle contract")
def test_update_helper_waits_for_windows_process_without_signalling_it():
    helper = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "packaging/windows/update_helper.py")
    )
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.15)"])
    started = time.monotonic()

    helper["wait_for_pid"](child.pid, timeout=2.0)

    assert time.monotonic() - started >= 0.10
    assert child.wait(timeout=1.0) == 0
