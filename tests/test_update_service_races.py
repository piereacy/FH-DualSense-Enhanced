import hashlib
import threading
from types import SimpleNamespace

import pytest

from modules.config.settings import Settings
from modules.update import service
from modules.update.model import UpdatePhase, UpdateRelease


def _release(version, content):
    name = f"FH-DualSense-Enhanced-R{version}.exe"
    return UpdateRelease(
        version=version,
        tag=f"R{version}",
        body="",
        html_url=f"https://example.test/R{version}",
        asset_name=name,
        asset_url=f"https://example.test/{name}",
        asset_size=len(content),
        checksum_url=f"https://example.test/{name}.sha256",
    )


@pytest.fixture
def ready_update(tmp_path, monkeypatch):
    monkeypatch.setattr(service.paths, "DATA", tmp_path)
    content = b"MZ verified update"
    release = _release(service._current_version() + 1, content)

    def download(_release, destination, *, progress):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        progress(len(content), len(content))
        return hashlib.sha256(content).hexdigest()

    updater = service.UpdateService(
        Settings(),
        client=SimpleNamespace(latest=lambda **_kwargs: release, download=download),
    )
    updater._check_impl(background=False)
    updater._download_impl()
    assert updater.snapshot().phase is UpdatePhase.READY
    return updater


def test_installing_update_rejects_new_download_and_check(ready_update, monkeypatch, tmp_path):
    entered = threading.Event()
    finish = threading.Event()
    outcomes = []

    def launch(staged, *, expected_sha256):
        assert service.UpdateService._hash_file(staged) == expected_sha256
        entered.set()
        assert finish.wait(5)
        return tmp_path / "transaction.json"

    monkeypatch.setattr(service, "launch_update_helper", launch)
    installer = threading.Thread(target=lambda: outcomes.append(ready_update.install_on_exit()))
    installer.start()
    try:
        assert entered.wait(5)
        assert ready_update.download() is False
        assert ready_update.check_now() is False
        assert ready_update.snapshot().phase is UpdatePhase.INSTALLING
    finally:
        finish.set()
        installer.join(5)
        if ready_update._worker is not None:
            ready_update._worker.join(5)
    assert not installer.is_alive()
    assert outcomes == [tmp_path / "transaction.json"]


def test_stopping_during_check_does_not_start_a_followup_download(tmp_path, monkeypatch):
    monkeypatch.setattr(service.paths, "DATA", tmp_path)
    entered = threading.Event()
    finish = threading.Event()
    downloads = []
    release = _release(service._current_version() + 1, b"MZ update")

    def latest(**_kwargs):
        entered.set()
        assert finish.wait(5)
        return release

    def download(*_args, **_kwargs):
        downloads.append(True)
        raise RuntimeError("download should not have started after stop")

    settings = Settings()
    settings.auto_download_updates = True
    updater = service.UpdateService(settings, client=SimpleNamespace(latest=latest, download=download))
    worker = threading.Thread(target=lambda: updater._check_impl(background=True))
    worker.start()
    try:
        assert entered.wait(5)
        updater.stop()
    finally:
        finish.set()
        worker.join(5)
    assert not worker.is_alive()
    assert downloads == []
    assert updater.check_now() is False
    assert updater.download() is False


def test_stopped_service_does_not_schedule_install(ready_update, monkeypatch):
    launches = []
    monkeypatch.setattr(service, "launch_update_helper", lambda *_args, **_kwargs: launches.append(True))
    ready_update.stop()
    with pytest.raises(RuntimeError, match="stopped"):
        ready_update.install_on_exit()
    assert launches == []


def test_background_check_cannot_replace_the_update_being_installed(ready_update, monkeypatch, tmp_path):
    entered = threading.Event()
    finish = threading.Event()
    downloads = []
    candidate = ready_update.snapshot()

    def latest(**_kwargs):
        entered.set()
        assert finish.wait(5)
        return _release(candidate.release.version + 1, b"MZ different update")

    def launch(staged, *, expected_sha256):
        assert str(staged) == candidate.staged_path
        assert service.UpdateService._hash_file(staged) == expected_sha256
        return tmp_path / "transaction.json"

    ready_update.settings.auto_download_updates = True
    monkeypatch.setattr(ready_update.client, "latest", latest)
    monkeypatch.setattr(ready_update.client, "download", lambda *_args, **_kwargs: downloads.append(True))
    monkeypatch.setattr(service, "launch_update_helper", launch)
    worker = threading.Thread(target=lambda: ready_update._check_impl(background=True))
    worker.start()
    try:
        assert entered.wait(5)
        assert ready_update.install_on_exit() == tmp_path / "transaction.json"
    finally:
        finish.set()
        worker.join(5)
    assert not worker.is_alive()
    snapshot = ready_update.snapshot()
    assert snapshot.phase is UpdatePhase.INSTALLING
    assert snapshot.staged_path == candidate.staged_path
    assert snapshot.release == candidate.release
    assert downloads == []


def test_download_already_started_can_finish_a_reusable_cache_after_stop(ready_update, monkeypatch):
    entered = threading.Event()
    finish = threading.Event()
    download = ready_update.client.download

    def in_progress(*args, **kwargs):
        entered.set()
        assert finish.wait(5)
        return download(*args, **kwargs)

    monkeypatch.setattr(ready_update.client, "download", in_progress)
    assert ready_update.download() is True
    try:
        assert entered.wait(5)
        ready_update.stop()
    finally:
        finish.set()
        ready_update._worker.join(5)
    assert not ready_update._worker.is_alive()
    assert ready_update.download() is False
    restarted = service.UpdateService(Settings(), client=ready_update.client)
    assert restarted.snapshot().phase is UpdatePhase.READY
    assert restarted.snapshot().staged_path == ready_update.snapshot().staged_path
