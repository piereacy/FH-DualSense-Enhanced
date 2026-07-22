import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "packaging"
    / "windows"
    / "shortcut_links.py"
)
SPEC = importlib.util.spec_from_file_location("fhds_shortcut_links", MODULE_PATH)
shortcut_links = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(shortcut_links)


class FakeLink:
    def __init__(self, path, states):
        self.path = Path(path)
        self.state = states[self.path]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def target(self):
        return self.state["target"]

    def set_target(self, value):
        self.state["pending_target"] = str(value)

    def icon(self):
        return self.state["icon"], self.state["icon_index"]

    def set_icon(self, value, index):
        self.state["pending_icon"] = (str(value), index)

    def save(self):
        if self.state.get("fail_save"):
            raise OSError("locked")
        self.state["target"] = self.state.pop("pending_target")
        if "pending_icon" in self.state:
            self.state["icon"], self.state["icon_index"] = self.state.pop("pending_icon")


def test_shortcut_migration_changes_only_exact_targets_and_matching_icons(tmp_path):
    old = (tmp_path / "FH-DualSense-Enhanced-R6.exe").resolve()
    new = (tmp_path / "FH-DualSense-Enhanced-R7.exe").resolve()
    exact = (tmp_path / "Desktop" / "FHDS.lnk").resolve()
    custom_icon = (tmp_path / "Programs" / "FHDS custom.lnk").resolve()
    unrelated = (tmp_path / "Desktop" / "Other.lnk").resolve()
    icon_file = (tmp_path / "custom.ico").resolve()
    states = {
        exact: {
            "target": str(old),
            "icon": str(old),
            "icon_index": 2,
            "arguments": "--gui",
            "working_directory": str(tmp_path),
        },
        custom_icon: {
            "target": str(old).upper(),
            "icon": str(icon_file),
            "icon_index": 4,
            "arguments": "--tui",
            "working_directory": str(tmp_path),
        },
        unrelated: {
            "target": str(tmp_path / "FH-DualSense-Enhanced-R6-helper.exe"),
            "icon": "",
            "icon_index": 0,
            "arguments": "",
            "working_directory": "",
        },
    }
    notified = []

    migrated, failed = shortcut_links.migrate_shortcuts(
        old,
        new,
        candidates=(exact, custom_icon, unrelated),
        link_factory=lambda path: FakeLink(path, states),
        notifier=notified.append,
    )

    assert migrated == [str(exact), str(custom_icon)]
    assert failed == []
    assert states[exact]["target"] == str(new)
    assert states[exact]["icon"] == str(new)
    assert states[exact]["icon_index"] == 2
    assert states[custom_icon]["target"] == str(new)
    assert states[custom_icon]["icon"] == str(icon_file)
    assert states[custom_icon]["icon_index"] == 4
    assert states[custom_icon]["arguments"] == "--tui"
    assert states[custom_icon]["working_directory"] == str(tmp_path)
    assert states[unrelated]["target"].endswith("R6-helper.exe")
    assert notified == [exact, custom_icon]


def test_shortcut_migration_reports_only_matched_failures(tmp_path):
    old = (tmp_path / "FH-DualSense-Enhanced-R6.exe").resolve()
    new = (tmp_path / "FH-DualSense-Enhanced-R7.exe").resolve()
    locked = (tmp_path / "locked.lnk").resolve()
    broken_unrelated = (tmp_path / "broken.lnk").resolve()
    states = {
        locked: {
            "target": str(old),
            "icon": str(old),
            "icon_index": 0,
            "fail_save": True,
        },
    }

    def factory(path):
        if Path(path) == broken_unrelated:
            raise OSError("invalid shortcut")
        return FakeLink(path, states)

    migrated, failed = shortcut_links.migrate_shortcuts(
        old,
        new,
        candidates=(locked, broken_unrelated),
        link_factory=factory,
        notifier=lambda _path: None,
    )

    assert migrated == []
    assert failed == [str(locked)]


def test_shortcut_migration_treats_no_matches_as_success(tmp_path):
    old = tmp_path / "FH-DualSense-Enhanced-R6.exe"
    new = tmp_path / "FH-DualSense-Enhanced-R7.exe"

    assert shortcut_links.migrate_shortcuts(
        old,
        new,
        candidates=(),
        link_factory=lambda _path: None,
        notifier=lambda _path: None,
    ) == ([], [])


def test_known_shortcut_scan_fails_closed_when_a_known_folder_is_unreadable(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        shortcut_links,
        "_known_folder",
        lambda folder: None if folder is shortcut_links.FOLDER_ROAMING_APP_DATA else tmp_path,
    )

    def fail_scan(_path, _pattern):
        raise OSError("access denied")

    monkeypatch.setattr(Path, "rglob", fail_scan)

    try:
        shortcut_links.known_shortcut_paths()
    except shortcut_links.ShortcutError as exc:
        assert "could not enumerate shortcut directory" in str(exc)
    else:
        raise AssertionError("an incomplete shortcut scan was treated as safe")
