import hashlib
import sys
from io import BytesIO
from types import SimpleNamespace

from modules.dualsense import hidhide
from modules.dualsense import hidhide_installer as installer
from modules.xinput.driver import InstallResult, InstallStatus


class _Response(BytesIO):
    def geturl(self):
        return installer.HIDHIDE_INSTALLER_URL


def test_download_pins_bytes_and_does_not_keep_a_tampered_installer(tmp_path, monkeypatch):
    expected = b"MZofficial-test-payload"
    monkeypatch.setattr(installer, "HIDHIDE_INSTALLER_SIZE", len(expected))
    monkeypatch.setattr(installer, "HIDHIDE_INSTALLER_SHA256", hashlib.sha256(expected).hexdigest().upper())
    monkeypatch.setattr(installer, "urlopen", lambda _request, timeout: _Response(b"MZtampered-test-payload"))
    target = tmp_path / "HidHide.exe"

    try:
        installer.download_installer(target, signature_verifier=lambda _path: True)
    except ValueError as exc:
        assert "size or SHA-256" in str(exc)
    else:
        raise AssertionError("tampered installer was accepted")
    assert not target.exists()
    assert not tuple(tmp_path.glob("*.part"))

    monkeypatch.setattr(installer, "urlopen", lambda _request, timeout: _Response(expected))
    assert installer.download_installer(target, signature_verifier=lambda _path: True) == target
    assert target.read_bytes() == expected


def test_install_skips_download_when_driver_is_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(installer.sys, "platform", "win32")
    result = installer.install_and_probe(
        path=tmp_path / "unused.exe",
        probe=lambda: True,
        downloader=lambda _path: (_ for _ in ()).throw(AssertionError("downloaded")),
        installed_marker=lambda: False,
    )
    assert result.status is InstallStatus.SUCCESS


def test_service_registration_counts_as_installed_without_cli(monkeypatch):
    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    registry = SimpleNamespace(
        HKEY_LOCAL_MACHINE=object(),
        OpenKey=lambda _root, path: Key() if path.endswith(r"Services\HidHide") else None,
    )
    monkeypatch.setattr(hidhide.sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "winreg", registry)
    assert hidhide._detect()


def test_installed_driver_is_not_reinstalled_when_control_device_is_busy(tmp_path, monkeypatch):
    monkeypatch.setattr(installer.sys, "platform", "win32")
    monkeypatch.setattr(installer, "probe_hidhide", lambda: False)
    monkeypatch.setattr(installer, "_detect", lambda: True)
    assert installer.detect_hidhide() == installer.HidHideDetection(True, False)
    stages = []
    result = installer.install_and_probe(
        path=tmp_path / "unused.exe",
        probe=lambda: False,
        installed_marker=lambda: True,
        downloader=lambda _path: (_ for _ in ()).throw(AssertionError("reinstalled")),
        on_progress=stages.append,
    )
    assert result.status is InstallStatus.RESTART_REQUIRED
    assert stages == [installer.HidHideInstallProgress(installer.HidHideInstallStage.CHECKING)]


def test_install_reports_actual_download_fraction_then_indeterminate_installer(
    tmp_path, monkeypatch
):
    expected = b"MZprogress-test-payload"
    monkeypatch.setattr(installer.sys, "platform", "win32")
    monkeypatch.setattr(installer, "HIDHIDE_INSTALLER_SIZE", len(expected))
    monkeypatch.setattr(installer, "HIDHIDE_INSTALLER_SHA256", hashlib.sha256(expected).hexdigest().upper())
    monkeypatch.setattr(installer, "urlopen", lambda _request, timeout: _Response(expected))
    probes = iter((False, True))
    progress = []
    result = installer.install_and_probe(
        path=tmp_path / "HidHide.exe",
        probe=lambda: next(probes),
        downloader=lambda path, on_progress: installer.download_installer(
            path,
            signature_verifier=lambda _path: True,
            on_progress=on_progress,
        ),
        runner=lambda _path, **_kwargs: InstallResult(InstallStatus.SUCCESS),
        installed_marker=lambda: False,
        on_progress=progress.append,
    )
    assert result.status is InstallStatus.SUCCESS
    stages = [event.stage for event in progress]
    assert stages[0] is installer.HidHideInstallStage.CHECKING
    assert installer.HidHideInstallStage.INSTALLING in stages
    assert stages[-1] is installer.HidHideInstallStage.PROBING
    assert [event.fraction for event in progress if event.stage is installer.HidHideInstallStage.DOWNLOADING] == [0.0, 1.0]


def test_install_uses_verified_download_and_reports_restart_if_driver_is_not_ready(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(installer.sys, "platform", "win32")
    calls = []

    def runner(path, **kwargs):
        calls.append((path, kwargs))
        return InstallResult(InstallStatus.SUCCESS, exit_code=0)

    result = installer.install_and_probe(
        path=tmp_path / "HidHide.exe",
        probe=lambda: False,
        downloader=lambda path: path,
        runner=runner,
        installed_marker=lambda: False,
    )

    assert result.status is InstallStatus.RESTART_REQUIRED
    assert len(calls) == 1
    assert calls[0][1] == {
        "parameters": "/quiet /norestart",
        "product_name": "HidHide",
        "timeout_ms": installer.HIDHIDE_INSTALL_TIMEOUT_MS,
    }


def test_installer_timeout_can_reconcile_a_ready_driver(tmp_path, monkeypatch):
    monkeypatch.setattr(installer.sys, "platform", "win32")
    probes = iter((False, True))
    result = installer.install_and_probe(
        path=tmp_path / "HidHide.exe",
        probe=lambda: next(probes),
        downloader=lambda path: path,
        runner=lambda _path, **_kwargs: InstallResult(
            InstallStatus.FAILED, error="installer did not finish within the time limit"
        ),
        installed_marker=lambda: False,
    )
    assert result.status is InstallStatus.SUCCESS


def test_official_client_lookup_and_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(installer.sys, "platform", "win32")
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    monkeypatch.setattr(installer, "_find_cached_hidhide_client", lambda: None)
    client = tmp_path / "Nefarius Software Solutions" / "HidHide" / "x64" / "HidHideClient.exe"
    assert installer.find_hidhide_client() is None
    client.parent.mkdir(parents=True)
    client.write_bytes(b"MZ")
    calls = []
    monkeypatch.setattr(installer.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))
    assert installer.open_hidhide_client() == client
    assert calls == [(([str(client)],), {"cwd": str(client.parent), "close_fds": True})]


def test_missing_installed_client_opens_verified_official_msi_source(tmp_path, monkeypatch):
    monkeypatch.setattr(installer.sys, "platform", "win32")
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "Program Files"))
    client = tmp_path / "HidHide MSI source" / "x64" / "HidHideClient.exe"
    client.parent.mkdir(parents=True)
    payload = b"MZofficial-client-test"
    client.write_bytes(payload)
    monkeypatch.setattr(installer, "HIDHIDE_CLIENT_SIZE", len(payload))
    monkeypatch.setattr(installer, "HIDHIDE_CLIENT_SHA256", hashlib.sha256(payload).hexdigest().upper())

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    registry = SimpleNamespace(
        HKEY_LOCAL_MACHINE=object(),
        OpenKey=lambda _root, _path: Key(),
        QueryValueEx=lambda _key, name: (
            installer.HIDHIDE_VERSION if name == "DisplayVersion" else str(client.parent.parent),
            1,
        ),
    )
    monkeypatch.setitem(sys.modules, "winreg", registry)
    calls = []
    monkeypatch.setattr(installer.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))

    assert installer.find_hidhide_client() == client
    assert installer.open_hidhide_client() == client
    assert calls == [(([str(client)],), {"cwd": str(client.parent), "close_fds": True})]

    client.write_bytes(b"MZtampered-client-test")
    assert installer.find_hidhide_client() is None
