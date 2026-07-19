import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "src" / "data" / "xinput"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_vigem_client_asset_is_exactly_the_audited_x64_binary():
    path = ASSETS / "ViGEmClient.dll"

    assert path.stat().st_size == 130_048
    assert _sha256(path) == "2BF0CB1D809039573C922737D298A1653D4DBC61408060FF45A9BCFDE82E97D2"


def test_vigem_bus_asset_is_exactly_the_official_1_22_installer():
    path = ASSETS / "ViGEmBus_1.22.0_x64_x86_arm64.exe"

    assert path.stat().st_size == 6_278_576
    assert _sha256(path) == "89220A7865076B342892F98865F3499FB7C4CFD673159E89D352C360FD014C6A"


def test_windows_spec_bundles_assets_but_linux_spec_does_not():
    windows_spec = (ROOT / "packaging" / "windows" / "fhds.spec").read_text(
        encoding="utf-8"
    )
    linux_spec = (ROOT / "packaging" / "linux" / "fhds.spec").read_text(
        encoding="utf-8"
    )

    assert "ViGEmClient.dll" in windows_spec
    assert "ViGEmBus_1.22.0_x64_x86_arm64.exe" in windows_spec
    assert "ViGEmClient.dll" not in linux_spec
    assert "ViGEmBus_1.22.0_x64_x86_arm64.exe" not in linux_spec
