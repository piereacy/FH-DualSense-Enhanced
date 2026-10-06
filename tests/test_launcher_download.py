"""Exercise interrupted bootstrap downloads without contacting the network."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name == "nt" or shutil.which("bash") is None, reason="requires Bash")
@pytest.mark.parametrize("recovery", ["retry", "manual"])
def test_interrupted_linux_download_can_retry_or_use_the_manual_bundle(tmp_path, recovery):
    root = Path(__file__).resolve().parents[1]
    launcher = tmp_path / "linux_start.sh"
    shutil.copyfile(root / "linux_start.sh", launcher)
    bins = tmp_path / "bin"
    bins.mkdir()
    curl = bins / "curl"
    curl.write_text('''#!/bin/bash
while [[ $# -gt 0 ]]; do
    if [[ "$1" == "-o" ]]; then out="$2"; shift 2; else shift; fi
done
if [[ ! -f "${out}.called" ]]; then
    printf called > "${out}.called"
    printf partial-download > "$out"
    exit 18
fi
printf complete-bundle > "$out"
''', encoding="utf-8")
    uv = bins / "uv"
    uv.write_text('''#!/bin/bash
cat "$2"
''', encoding="utf-8")
    curl.chmod(0o755)
    uv.chmod(0o755)
    env = dict(os.environ, PATH=str(bins) + os.pathsep + os.environ["PATH"])
    first = subprocess.run(["bash", str(launcher)], env=env, capture_output=True, text=True, check=False)
    bundle = tmp_path / "app/FH-DualSense-Enhanced.zuv.py"
    assert first.returncode == 1
    assert not bundle.exists()
    assert not bundle.with_name(bundle.name + ".part").exists()

    if recovery == "manual":
        (tmp_path / bundle.name).write_text("manual-bundle", encoding="utf-8")
    second = subprocess.run(["bash", str(launcher)], env=env, capture_output=True, text=True, check=False)
    assert second.returncode == 0
    expected = "manual-bundle" if recovery == "manual" else "complete-bundle"
    assert bundle.read_text(encoding="utf-8") == expected
    assert expected in second.stdout
    assert not bundle.with_name(bundle.name + ".part").exists()
