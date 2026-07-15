import hashlib
import io
import json
from pathlib import Path

import pytest

from modules.update import github
from modules.update.github import GitHubReleaseClient, UpdateError
from modules.update.model import UpdatePhase, UpdateRelease
from modules.update.service import UpdateService
from modules.config.settings import Settings


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
