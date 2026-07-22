from modules.config import paths
from modules.xinput.driver import (
    DriverProbe,
    DriverProbeStatus,
    InstallResult,
    InstallStatus,
    install_and_probe,
    probe_vigem_bus,
    validate_installer,
    verify_installer_hash,
)
from modules.xinput.vigem_client import ViGEmError, ViGEmErrorCode


class _Client:
    def __init__(self, error=None):
        self.error = error
        self.closed = False

    def connect(self):
        if self.error:
            raise self.error

    def close(self):
        self.closed = True


def test_probe_accepts_any_bus_that_client_can_connect_to():
    client = _Client()

    result = probe_vigem_bus(lambda: client)

    assert result.status is DriverProbeStatus.AVAILABLE
    assert client.closed is True


def test_probe_classifies_missing_bus_separately_from_client_error():
    missing = probe_vigem_bus(
        lambda: _Client(ViGEmError("connect", ViGEmErrorCode.BUS_NOT_FOUND))
    )
    broken = probe_vigem_bus(lambda: _Client(ViGEmError("load dll")))

    assert missing.status is DriverProbeStatus.MISSING
    assert broken.status is DriverProbeStatus.ERROR


def test_bundled_installer_hash_is_pinned():
    assert verify_installer_hash(paths.VIGEM_BUS_INSTALLER)


def test_validate_installer_requires_hash_before_signature(tmp_path):
    tampered = tmp_path / "installer.exe"
    tampered.write_bytes(b"not the official installer")
    signature_calls = []

    try:
        validate_installer(
            tampered,
            signature_verifier=lambda path: signature_calls.append(path) or True,
        )
    except Exception as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("tampered installer was accepted")
    assert signature_calls == []


def test_validate_installer_rejects_bad_authenticode_signature():
    try:
        validate_installer(paths.VIGEM_BUS_INSTALLER, signature_verifier=lambda _path: False)
    except Exception as exc:
        assert "Authenticode" in str(exc)
    else:
        raise AssertionError("unsigned installer was accepted")


def test_authenticode_api_failure_is_reported_as_a_validation_error():
    def fail_signature(_path):
        raise OSError("wintrust unavailable")

    try:
        validate_installer(paths.VIGEM_BUS_INSTALLER, signature_verifier=fail_signature)
    except Exception as exc:
        assert "Authenticode" in str(exc)
        assert "wintrust unavailable" in str(exc)
    else:
        raise AssertionError("signature verifier failure escaped validation")


def _install_with(result, probe_status=DriverProbeStatus.AVAILABLE):
    return install_and_probe(
        paths.VIGEM_BUS_INSTALLER,
        signature_verifier=lambda _path: True,
        runner=lambda _path: result,
        probe=lambda: DriverProbe(probe_status, "post-install probe failed"),
    )


def test_cancelled_uac_remains_cancelled_without_probe():
    result = _install_with(InstallResult(InstallStatus.CANCELLED))

    assert result.status is InstallStatus.CANCELLED


def test_reboot_exit_code_remains_restart_required_without_probe():
    result = _install_with(
        InstallResult(InstallStatus.RESTART_REQUIRED, exit_code=3010)
    )

    assert result.status is InstallStatus.RESTART_REQUIRED
    assert result.exit_code == 3010


def test_success_requires_bus_to_be_available_after_installer_exit():
    ready = _install_with(InstallResult(InstallStatus.SUCCESS, exit_code=0))
    restart = _install_with(
        InstallResult(InstallStatus.SUCCESS, exit_code=0),
        DriverProbeStatus.MISSING,
    )

    assert ready.status is InstallStatus.SUCCESS
    assert restart.status is InstallStatus.RESTART_REQUIRED
    assert "post-install probe failed" in restart.error


def test_installer_failure_is_preserved():
    result = _install_with(
        InstallResult(InstallStatus.FAILED, exit_code=5, error="installer failed")
    )

    assert result == InstallResult(
        InstallStatus.FAILED,
        exit_code=5,
        error="installer failed",
    )


def test_installer_runner_and_post_probe_exceptions_become_stable_results():
    runner_failure = install_and_probe(
        paths.VIGEM_BUS_INSTALLER,
        signature_verifier=lambda _path: True,
        runner=lambda _path: (_ for _ in ()).throw(OSError("cannot elevate")),
    )
    probe_failure = install_and_probe(
        paths.VIGEM_BUS_INSTALLER,
        signature_verifier=lambda _path: True,
        runner=lambda _path: InstallResult(InstallStatus.SUCCESS, exit_code=0),
        probe=lambda: (_ for _ in ()).throw(OSError("bus query failed")),
    )

    assert runner_failure.status is InstallStatus.FAILED
    assert "cannot elevate" in runner_failure.error
    assert probe_failure.status is InstallStatus.RESTART_REQUIRED
    assert "bus query failed" in probe_failure.error
