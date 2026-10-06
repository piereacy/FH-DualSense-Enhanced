"""Execute the workflow's real parser without tag, network or release mutations."""

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
import tomllib

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/release.yml"
VERSION = tomllib.loads((ROOT / "src/pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
RELEASE = f"R{VERSION}"
pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="requires Bash")


def _parse(tmp_path, *, event="push", ref="refs/heads/dev", subject="", channel=""):
    source = WORKFLOW.read_text(encoding="utf-8")
    step = source.split("      - name: Parse trigger\n", 1)[1].split("      - name:", 1)[0]
    script = textwrap.dedent(step.split("        run: |\n", 1)[1])
    output = tmp_path / "outputs"
    env = dict(os.environ, GITHUB_EVENT_NAME=event, GITHUB_REF=ref,
               RELEASE_CHANNEL=channel, GITHUB_OUTPUT=str(output), TEST_SUBJECT=subject)
    # Only git log is part of parsing. Anything else is an unexpected mutation.
    stub = 'git() { if [[ "$*" == "log -1 --pretty=%s" ]]; then printf "%s\\n" "$TEST_SUBJECT"; else return 98; fi; }\n'
    result = subprocess.run(["bash", "-c", stub + script], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=False)
    values = dict(line.split("=", 1) for line in output.read_text().splitlines()) if output.exists() else {}
    return result, values


@pytest.mark.parametrize("channel,ref,subject,tag,prerelease", [
    ("preview", "refs/heads/main", f"release {RELEASE}", f"{RELEASE}-preview", "true"),
    ("preview", f"refs/tags/{RELEASE}", f"release {RELEASE}", f"{RELEASE}-preview", "true"),
    ("preview", "refs/heads/main", "release R99999", f"{RELEASE}-preview", "true"),
    ("stable", "refs/heads/dev", f"prerelease {RELEASE}", RELEASE, "false"),
    ("stable", f"refs/tags/{RELEASE}-preview", "prerelease", RELEASE, "false"),
])
def test_manual_channel_has_priority_over_ref_and_subject(tmp_path, channel, ref, subject, tag, prerelease):
    result, values = _parse(tmp_path, event="workflow_dispatch", channel=channel, ref=ref, subject=subject)
    assert result.returncode == 0, result.stderr
    assert values["tag"] == tag
    assert values["prerelease"] == prerelease
    assert values["windows_asset"] == f"FH-DualSense-Enhanced-{RELEASE}.exe"


@pytest.mark.parametrize("subject,tag,prerelease", [
    (f"prerelease {RELEASE}", f"{RELEASE}-preview", "true"),
    (f"build: [prerelease] release {RELEASE}", f"{RELEASE}-preview", "true"),
    (f"release {RELEASE}", RELEASE, "false"),
    (f"build: release {RELEASE}: ready", RELEASE, "false"),
    (f"prelease {RELEASE}", "", ""),
    (f"unrelease {RELEASE}", "", ""),
    (f"release {RELEASE}-preview", "", ""),
    (f"release {RELEASE}suffix", "", ""),
    (f"release {RELEASE}.1", "", ""),
    ("prerelease_notes", "", ""),
    ("ordinary commit", "", ""),
    ("release v1.6.2", "v1.6.2", "false"),
    ("release v1.6.2.post1", "v1.6.2.post1", "false"),
    ("release v1.6.2-preview", "", ""),
])
def test_commit_channel_requires_complete_trigger_words_and_versions(tmp_path, subject, tag, prerelease):
    result, values = _parse(tmp_path, subject=subject)
    assert result.returncode == 0, result.stderr
    assert (values["tag"], values["prerelease"]) == (tag, prerelease)


@pytest.mark.parametrize("tag,expected,prerelease", [
    (RELEASE, RELEASE, "false"),
    (f"{RELEASE}-preview", f"{RELEASE}-preview", "true"),
    (f"{RELEASE}-rc1", "", ""),
    ("v1.6.2", "v1.6.2", "false"),
    ("v1.6.2.post1", "v1.6.2.post1", "false"),
    ("v1.bad.2", "", ""),
])
def test_tag_channel_is_explicit_and_unknown_tags_do_not_use_commit_subject(tmp_path, tag, expected, prerelease):
    result, values = _parse(tmp_path, ref=f"refs/tags/{tag}", subject=f"release {RELEASE}")
    assert result.returncode == 0, result.stderr
    assert (values["tag"], values["prerelease"]) == (expected, prerelease)


@pytest.mark.parametrize("kwargs", [
    {"event": "workflow_dispatch", "channel": "unknown"},
    {"subject": "release R99999"},
    {"ref": "refs/tags/R99999-preview"},
])
def test_invalid_channel_or_version_cannot_produce_release_outputs(tmp_path, kwargs):
    result, values = _parse(tmp_path, **kwargs)
    assert result.returncode != 0
    assert not values


def test_preview_notes_name_the_canonical_windows_asset(tmp_path):
    result, values = _parse(tmp_path, subject=f"prerelease {RELEASE}")
    assert result.returncode == 0, result.stderr
    assert values["tag"].endswith("-preview")
    assert values["windows_asset"] == f"FH-DualSense-Enhanced-{RELEASE}.exe"
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert workflow.count("${{ needs.prepare.outputs.windows_asset }}") == 2
    assert "format('FH-DualSense-Enhanced-{0}.exe', needs.prepare.outputs.tag)" not in workflow
