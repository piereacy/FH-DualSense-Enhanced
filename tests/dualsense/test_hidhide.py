import json
from pathlib import Path

import pytest

from modules.dualsense import hidhide


APP_NT_PATH = r"\Device\HarddiskVolume3\Games\FH-DualSense-Enhanced-R11.exe"
OLD_APP_NT_PATH = r"\Device\HarddiskVolume3\Games\FH-DualSense-Enhanced-R10.exe"
DEVICE_PATH = (
    rb"\\?\hid#vid_054c&pid_0ce6&mi_03#8&2f5a32d1&0&0000"
    rb"#{4d1e55b2-f16f-11cf-88cb-001111000030}"
)
INSTANCE_ID = r"HID\VID_054C&PID_0CE6&MI_03\8&2F5A32D1&0&0000"


class _Api:
    def __init__(
        self,
        *,
        whitelist=(),
        blacklist=(),
        active=False,
        inverse=False,
    ):
        self.whitelist = tuple(whitelist)
        self.blacklist = tuple(blacklist)
        self.active = active
        self.inverse = inverse
        self.session = []
        self.calls = []
        self.clear_error = None

    def __enter__(self):
        self.calls.append("open")
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        self.calls.append("close")

    def get_whitelist(self):
        self.calls.append("get_whitelist")
        return self.whitelist

    def set_whitelist(self, entries):
        self.calls.append(("set_whitelist", tuple(entries)))
        self.whitelist = tuple(entries)

    def get_blacklist(self):
        self.calls.append("get_blacklist")
        return self.blacklist

    def get_active(self):
        self.calls.append("get_active")
        return self.active

    def set_active(self, active):
        self.calls.append(("set_active", active))
        self.active = bool(active)

    def get_inverse(self):
        self.calls.append("get_inverse")
        return self.inverse

    def add_session_blacklist(self, entries):
        self.calls.append(("add_session", tuple(entries)))
        self.session.extend(entries)

    def clear_session_blacklist(self):
        self.calls.append("clear_session")
        if self.clear_error is not None:
            raise self.clear_error
        self.session.clear()


def _service(tmp_path: Path, api: _Api, *, app=APP_NT_PATH):
    executable = tmp_path / "FH-DualSense-Enhanced-R11.exe"
    executable.write_bytes(b"MZ")
    return hidhide.HidHideService(
        api_factory=lambda: api,
        application_path=executable,
        ownership_path=tmp_path / "hidhide_owned.json",
        full_image_resolver=lambda _path: app,
        standalone_supported=lambda: True,
    )


def test_ioctl_values_match_the_hidhide_17_contract():
    assert hidhide.IOCTL_GET_WHITELIST == 0x80016000
    assert hidhide.IOCTL_SET_WHITELIST == 0x80016004
    assert hidhide.IOCTL_GET_BLACKLIST == 0x80016008
    assert hidhide.IOCTL_GET_ACTIVE == 0x80016010
    assert hidhide.IOCTL_SET_ACTIVE == 0x80016014
    assert hidhide.IOCTL_GET_WLINVERSE == 0x80016018
    assert hidhide.IOCTL_ADD_SESSION_BLACKLIST == 0x80016020
    assert hidhide.IOCTL_CLR_SESSION_BLACKLIST == 0x80016024


@pytest.mark.parametrize(
    ("entries", "payload"),
    [
        ((), b"\0\0"),
        (("one",), "one\0\0".encode("utf-16-le")),
        (("one", "two"), "one\0two\0\0".encode("utf-16-le")),
    ],
)
def test_multi_sz_round_trip(entries, payload):
    assert hidhide._encode_multi_sz(entries) == payload
    assert hidhide._decode_multi_sz(payload) == entries


def test_decoder_accepts_a_standard_double_nul_empty_multi_sz_too():
    assert hidhide._decode_multi_sz(b"\0\0\0\0") == ()


def test_driver_reader_accepts_hidhide_empty_collection_size():
    class Session(hidhide._WindowsDriverSession):
        def __init__(self):
            pass

        def _ioctl(self, _code, *, input_bytes=None, output_size=0):
            assert input_bytes is None
            return (b"", 2) if output_size == 0 else (b"\0\0", 2)

    assert Session().get_whitelist() == ()


def test_multi_sz_rejects_embedded_nul_and_bad_termination():
    with pytest.raises(ValueError):
        hidhide._encode_multi_sz(("bad\0entry",))
    with pytest.raises(hidhide.HidHideError):
        hidhide._decode_multi_sz("not-terminated".encode("utf-16-le"))


def test_hidapi_path_converts_to_setupapi_device_instance_id():
    assert hidhide.device_instance_id_from_hid_path(DEVICE_PATH) == INSTANCE_ID
    assert hidhide.device_instance_id_from_hid_path(DEVICE_PATH.decode()) == INSTANCE_ID


@pytest.mark.parametrize("value", [b"usb-test", "", r"\\?\USB#VID_054C"])
def test_non_interface_paths_are_rejected(value):
    with pytest.raises(ValueError):
        hidhide.device_instance_id_from_hid_path(value)


def test_service_allowlists_then_session_hides_without_owning_global_active(tmp_path):
    api = _Api(whitelist=(r"\Device\Volume\Other.exe",), active=True)
    service = _service(tmp_path, api)

    ready = service.start()
    assert ready.phase is hidhide.HidHidePhase.READY
    assert api.whitelist == (r"\Device\Volume\Other.exe", APP_NT_PATH)
    assert api.active is True
    assert not any(call[0] == "set_active" for call in api.calls if isinstance(call, tuple))
    assert service.register_device({"path": DEVICE_PATH}) is True
    assert service.register_device({"path": DEVICE_PATH}) is True
    assert api.session == [INSTANCE_ID]
    assert service.snapshot().hidden_device_count == 1

    stopped = service.stop()
    assert stopped.phase is hidhide.HidHidePhase.DISABLED
    assert api.session == []
    assert api.active is True
    # The application rule remains while the user setting remains enabled.
    assert APP_NT_PATH in api.whitelist

    service.stop(remove_allowlist=True)
    assert APP_NT_PATH not in api.whitelist
    journal = json.loads((tmp_path / "hidhide_owned.json").read_text(encoding="utf-8"))
    assert journal["whitelist_paths"] == []


def test_user_owned_application_rule_is_never_removed(tmp_path):
    api = _Api(whitelist=(APP_NT_PATH,), active=True)
    service = _service(tmp_path, api)

    assert service.start().phase is hidhide.HidHidePhase.READY
    service.stop(remove_allowlist=True)

    assert api.whitelist == (APP_NT_PATH,)
    assert api.active is True


def test_versioned_executable_migration_removes_only_the_owned_old_path(tmp_path):
    journal = tmp_path / "hidhide_owned.json"
    journal.write_text(
        json.dumps({"schema": 1, "whitelist_paths": [OLD_APP_NT_PATH]}),
        encoding="utf-8",
    )
    user_rule = r"\Device\HarddiskVolume3\Tools\UserFeeder.exe"
    api = _Api(whitelist=(user_rule, OLD_APP_NT_PATH), active=True)
    service = _service(tmp_path, api)

    assert service.start().phase is hidhide.HidHidePhase.READY

    assert api.whitelist == (user_rule, APP_NT_PATH)
    state = json.loads(journal.read_text(encoding="utf-8"))
    assert state["whitelist_paths"] == [APP_NT_PATH]


@pytest.mark.parametrize("blacklist", [(), (r"HID\VID_1234&PID_5678\USER",)])
def test_disabled_global_hiding_requires_official_client_and_is_never_activated(
    tmp_path,
    blacklist,
):
    original = (r"\Device\Volume\UserRule.exe",)
    api = _Api(
        whitelist=original,
        blacklist=blacklist,
        active=False,
    )
    service = _service(tmp_path, api)

    snapshot = service.start()

    assert snapshot.phase is hidhide.HidHidePhase.ERROR
    assert "Configuration Client" in snapshot.last_error
    assert api.whitelist == original
    assert api.active is False
    assert api.session == []
    assert not any(call[0] == "set_active" for call in api.calls if isinstance(call, tuple))


def test_inverse_cloak_user_rule_is_respected_instead_of_removed(tmp_path):
    api = _Api(whitelist=(APP_NT_PATH,), active=True, inverse=True)
    service = _service(tmp_path, api)

    snapshot = service.start()

    assert snapshot.phase is hidhide.HidHidePhase.ERROR
    assert "inverse" in snapshot.last_error
    assert api.whitelist == (APP_NT_PATH,)


def test_old_hidhide_without_session_ioctl_is_reported_as_unavailable(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    api = _Api(active=True)
    api.clear_error = _OldDriverError("unsupported")
    service = _service(tmp_path, api)

    snapshot = service.start()

    assert snapshot.phase is hidhide.HidHidePhase.UNAVAILABLE
    assert "1.7" in snapshot.last_error
    assert api.whitelist == ()


def test_source_mode_never_opens_or_changes_hidhide(tmp_path):
    calls = []
    journal = tmp_path / "hidhide_owned.json"
    journal.write_text(
        json.dumps({"schema": 1, "whitelist_paths": [OLD_APP_NT_PATH]}),
        encoding="utf-8",
    )
    service = hidhide.HidHideService(
        api_factory=lambda: calls.append(True),
        ownership_path=journal,
        standalone_supported=lambda: False,
    )

    snapshot = service.start()
    stopped = service.stop(remove_allowlist=True)

    assert snapshot.phase is hidhide.HidHidePhase.UNAVAILABLE
    assert stopped.phase is hidhide.HidHidePhase.DISABLED
    assert calls == []


def test_active_user_configuration_is_not_disabled_on_stop(tmp_path):
    api = _Api(active=True)
    service = _service(tmp_path, api)

    service.start()
    service.register_device({"path": DEVICE_PATH})
    service.stop()

    assert api.active is True
    assert not any(call == ("set_active", False) for call in api.calls)


def test_failed_session_cleanup_keeps_state_for_a_later_retry(tmp_path):
    api = _Api(active=True)
    service = _service(tmp_path, api)
    service.start()
    service.register_device({"path": DEVICE_PATH})
    api.clear_error = OSError("control device busy")

    failed = service.stop()

    assert failed.phase is hidhide.HidHidePhase.ERROR
    assert failed.hidden_device_count == 1
    assert service.started is True
    assert api.session == [INSTANCE_ID]

    api.clear_error = None
    recovered = service.stop()

    assert recovered.phase is hidhide.HidHidePhase.DISABLED
    assert service.started is False
    assert api.session == []


def test_global_active_state_remains_user_owned_when_permanent_rules_change(tmp_path):
    api = _Api(active=True)
    service = _service(tmp_path, api)
    service.start()
    api.blacklist = (r"HID\VID_1234&PID_5678\USER",)

    service.stop()

    assert api.active is True
    assert not any(call[0] == "set_active" for call in api.calls if isinstance(call, tuple))
