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
BT_PARENT_ID = (
    r"BTHENUM\{00001124-0000-1000-8000-00805F9B34FB}_VID&0002054C_PID&0CE6\USER"
)


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

    def set_blacklist(self, entries):
        self.calls.append(("set_blacklist", tuple(entries)))
        self.blacklist = tuple(entries)

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


def _service(tmp_path: Path, api: _Api, *, app=APP_NT_PATH, automatic_legacy=False):
    executable = tmp_path / "FH-DualSense-Enhanced-R11.exe"
    executable.write_bytes(b"MZ")
    return hidhide.HidHideService(
        api_factory=lambda: api,
        application_path=executable,
        ownership_path=tmp_path / "hidhide_owned.json",
        device_ownership_path=tmp_path / "hidhide_device_owned.json",
        full_image_resolver=lambda _path: app,
        standalone_supported=lambda: True,
        automatic_legacy=automatic_legacy,
    )


def test_ioctl_values_match_the_hidhide_17_contract():
    assert hidhide.IOCTL_GET_WHITELIST == 0x80016000
    assert hidhide.IOCTL_SET_WHITELIST == 0x80016004
    assert hidhide.IOCTL_GET_BLACKLIST == 0x80016008
    assert hidhide.IOCTL_SET_BLACKLIST == 0x8001600C
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


def test_decoder_accepts_zero_padding_from_hidhide_15_but_rejects_extra_data():
    padded = "first\0second\0\0".encode("utf-16-le") + b"\0" * 64
    assert hidhide._decode_multi_sz(padded) == ("first", "second")
    with pytest.raises(hidhide.HidHideError):
        hidhide._decode_multi_sz(padded + "extra\0\0".encode("utf-16-le"))
    with pytest.raises(hidhide.HidHideError):
        hidhide._decode_multi_sz("\0bad\0\0".encode("utf-16-le"))


def test_driver_reader_accepts_hidhide_empty_collection_size():
    class Session(hidhide._WindowsDriverSession):
        def __init__(self):
            pass

        def _ioctl(self, _code, *, input_bytes=None, output_size=0):
            assert input_bytes is None
            return (b"", 2) if output_size == 0 else (b"\0\0", 2)

    assert Session().get_whitelist() == ()


def test_driver_reader_accepts_hidhide_15_overallocated_list():
    payload = "rule\0\0".encode("utf-16-le") + b"\0" * 48

    class Session(hidhide._WindowsDriverSession):
        def __init__(self):
            pass

        def _ioctl(self, _code, *, input_bytes=None, output_size=0):
            assert input_bytes is None
            return (b"", len(payload)) if output_size == 0 else (payload, len(payload))

    assert Session().get_whitelist() == ("rule",)


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


@pytest.mark.parametrize(
    ("instance_id", "expected"),
    [
        (INSTANCE_ID, True),
        (BT_PARENT_ID, True),
        (r"HID\VID_054C&PID_0DF2\EDGE", True),
        (r"HID\VID_054C&PID_0CE60\OTHER", False),
        (r"HID\VID_054C&PID_05C4\DS4", False),
        (r"HID\VID_1234&PID_5678\OTHER", False),
    ],
)
def test_only_dualsense_device_rules_are_safe_for_automatic_global_hiding(
    instance_id, expected
):
    assert hidhide._is_dualsense_device_rule(instance_id) is expected


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


def test_prepare_access_recovers_previously_hidden_controller_without_hiding_more(tmp_path):
    user_rule = r"\Device\Volume\Other.exe"
    user_device = r"BTHENUM\{00001124-0000-1000-8000-00805F9B34FB}_VID&0002054C_PID&0CE6\USER"
    api = _Api(whitelist=(user_rule,), blacklist=(user_device,), active=True)
    service = _service(tmp_path, api, automatic_legacy=True)

    ready = service.prepare_application_access()

    assert ready.phase is hidhide.HidHidePhase.READY
    assert api.whitelist == (user_rule, APP_NT_PATH)
    assert api.blacklist == (user_device,)
    assert api.active is True
    assert service.started is False
    assert not any(call == "clear_session" for call in api.calls)
    assert not any(call[0] in {"set_blacklist", "set_active", "add_session"}
                   for call in api.calls if isinstance(call, tuple))
    journal = json.loads((tmp_path / "hidhide_owned.json").read_text(encoding="utf-8"))
    assert journal["whitelist_paths"] == [APP_NT_PATH]

    service.stop(remove_allowlist=True)
    assert api.whitelist == (user_rule,)
    assert api.blacklist == (user_device,)


def test_prepare_access_refuses_inverse_mode_without_writing_rules(tmp_path):
    api = _Api(whitelist=(r"\Device\Volume\Other.exe",), inverse=True)
    service = _service(tmp_path, api, automatic_legacy=True)

    assert service.prepare_application_access().phase is hidhide.HidHidePhase.ERROR
    assert api.whitelist == (r"\Device\Volume\Other.exe",)
    assert not any(isinstance(call, tuple) for call in api.calls)


def test_prepare_access_preserves_an_existing_user_application_rule(tmp_path):
    api = _Api(whitelist=(APP_NT_PATH,), active=True)
    service = _service(tmp_path, api, automatic_legacy=True)

    assert service.prepare_application_access().phase is hidhide.HidHidePhase.READY
    assert not any(call[0] == "set_whitelist" for call in api.calls if isinstance(call, tuple))
    service.stop(remove_allowlist=True)
    assert api.whitelist == (APP_NT_PATH,)


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


def test_session_driver_enables_and_restores_unconfigured_device_hiding(tmp_path):
    original = (r"\Device\Volume\UserRule.exe",)
    api = _Api(
        whitelist=original,
        active=False,
    )
    service = _service(tmp_path, api)

    snapshot = service.start()

    assert snapshot.phase is hidhide.HidHidePhase.READY
    assert api.active is True
    assert service.stop(remove_allowlist=True).phase is hidhide.HidHidePhase.DISABLED
    assert api.active is False
    assert api.whitelist == original


def test_disabled_hiding_with_existing_dualsense_rules_is_enabled_and_restored(tmp_path):
    original = (BT_PARENT_ID, INSTANCE_ID)
    api = _Api(blacklist=original, active=False)
    service = _service(tmp_path, api)

    assert service.start().phase is hidhide.HidHidePhase.READY
    assert api.active is True
    assert service.register_device({"path": DEVICE_PATH}) is True
    assert service.snapshot().phase is hidhide.HidHidePhase.ACTIVE
    journal = json.loads((tmp_path / "hidhide_device_owned.json").read_text(encoding="utf-8"))
    assert journal["active_baseline"] == list(original)
    assert journal["device_instance_ids"] == []

    assert service.stop(remove_allowlist=True).phase is hidhide.HidHidePhase.DISABLED
    assert api.active is False
    assert api.blacklist == original


def test_disabled_hiding_with_other_device_rules_requires_manual_review(tmp_path):
    original = (r"\Device\Volume\UserRule.exe",)
    api = _Api(
        whitelist=original,
        blacklist=(r"HID\VID_1234&PID_5678\USER",),
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


def test_auto_enabled_hiding_stays_on_if_user_adds_another_rule(tmp_path):
    other_device = r"HID\VID_1234&PID_5678\USER"
    api = _Api(blacklist=(INSTANCE_ID,), active=False)
    service = _service(tmp_path, api)

    assert service.start().phase is hidhide.HidHidePhase.READY
    api.blacklist = (*api.blacklist, other_device)

    assert service.stop().phase is hidhide.HidHidePhase.DISABLED
    assert api.active is True
    assert api.blacklist == (INSTANCE_ID, other_device)


def test_auto_enabled_hiding_stays_on_if_user_removes_original_rules(tmp_path):
    api = _Api(blacklist=(INSTANCE_ID,), active=False)
    service = _service(tmp_path, api)

    assert service.start().phase is hidhide.HidHidePhase.READY
    api.blacklist = ()

    assert service.stop().phase is hidhide.HidHidePhase.DISABLED
    assert api.active is True
    assert api.blacklist == ()


def test_auto_enabled_hiding_recovers_after_interrupted_session(tmp_path):
    api = _Api(blacklist=(BT_PARENT_ID, INSTANCE_ID), active=True)
    journal = tmp_path / "hidhide_device_owned.json"
    journal.write_text(
        json.dumps(
            {
                "schema": 1,
                "device_instance_ids": [],
                "active_owned": True,
                "active_baseline": [BT_PARENT_ID, INSTANCE_ID],
            }
        ),
        encoding="utf-8",
    )
    service = _service(tmp_path, api)

    assert service.stop().phase is hidhide.HidHidePhase.DISABLED
    assert api.active is False
    assert api.blacklist == (BT_PARENT_ID, INSTANCE_ID)


def test_inverse_cloak_user_rule_is_respected_instead_of_removed(tmp_path):
    api = _Api(whitelist=(APP_NT_PATH,), active=True, inverse=True)
    service = _service(tmp_path, api)

    snapshot = service.start()

    assert snapshot.phase is hidhide.HidHidePhase.ERROR
    assert "inverse" in snapshot.last_error
    assert api.whitelist == (APP_NT_PATH,)


def test_official_hidhide_without_session_ioctl_requires_manual_rules(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    api = _Api(active=True)
    api.clear_error = _OldDriverError("unsupported")
    service = _service(tmp_path, api)

    snapshot = service.start()

    assert snapshot.phase is hidhide.HidHidePhase.ERROR
    assert snapshot.manual_configuration is True
    assert "Applications" in snapshot.last_error
    assert api.whitelist == ()
    assert api.session == []
    assert not any(isinstance(call, tuple) for call in api.calls)

    # A journal from an older FHDS session must not cause 1.5 rules to be
    # changed while this manual configuration is incomplete.
    (tmp_path / "hidhide_owned.json").write_text(
        json.dumps({"schema": 1, "whitelist_paths": [OLD_APP_NT_PATH]}),
        encoding="utf-8",
    )
    assert service.stop(remove_allowlist=True).phase is hidhide.HidHidePhase.DISABLED
    assert not any(isinstance(call, tuple) for call in api.calls)


def test_official_hidhide_manual_rules_are_verified_without_writes(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    api = _Api(
        whitelist=(APP_NT_PATH,),
        blacklist=(INSTANCE_ID,),
        active=True,
    )
    api.clear_error = _OldDriverError("unsupported")
    service = _service(tmp_path, api)

    ready = service.start()
    assert ready.phase is hidhide.HidHidePhase.READY
    assert ready.manual_configuration is True
    assert service.register_device({"path": DEVICE_PATH}) is True
    active = service.snapshot()
    assert active.phase is hidhide.HidHidePhase.ACTIVE
    assert active.manual_configuration is True
    assert active.hidden_device_count == 1
    assert service.stop(remove_allowlist=True).phase is hidhide.HidHidePhase.DISABLED
    assert api.whitelist == (APP_NT_PATH,)
    assert api.blacklist == (INSTANCE_ID,)
    assert api.active is True
    assert api.session == []
    assert not any(isinstance(call, tuple) for call in api.calls)
    assert not (tmp_path / "hidhide_owned.json").exists()


def test_manual_rules_are_rechecked_when_a_device_is_registered_again(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    api = _Api(whitelist=(APP_NT_PATH,), blacklist=(INSTANCE_ID,), active=True)
    api.clear_error = _OldDriverError("unsupported")
    service = _service(tmp_path, api)

    assert service.start().phase is hidhide.HidHidePhase.READY
    assert service.register_device({"path": DEVICE_PATH}) is True
    api.blacklist = ()
    assert service.register_device({"path": DEVICE_PATH}) is False
    assert service.snapshot().phase is hidhide.HidHidePhase.ERROR
    assert not any(isinstance(call, tuple) for call in api.calls)


def test_legacy_driver_automatically_configures_and_cleans_only_its_rules(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    api = _Api(whitelist=(OLD_APP_NT_PATH,))
    api.clear_error = _OldDriverError("unsupported")
    service = _service(tmp_path, api, automatic_legacy=True)

    assert service.start().phase is hidhide.HidHidePhase.READY
    assert api.active is True
    assert api.whitelist == (OLD_APP_NT_PATH, APP_NT_PATH)
    assert service.register_device({"path": DEVICE_PATH}) is True
    assert api.blacklist == (INSTANCE_ID,)
    assert service.stop(remove_allowlist=True).phase is hidhide.HidHidePhase.DISABLED
    assert api.blacklist == ()
    assert api.active is False
    assert api.whitelist == (OLD_APP_NT_PATH,)


def test_legacy_isolation_readback_detects_removed_rule_and_restores_it(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    api = _Api(whitelist=(APP_NT_PATH,), active=True)
    api.clear_error = _OldDriverError("unsupported")
    service = _service(tmp_path, api, automatic_legacy=True)
    assert service.start().phase is hidhide.HidHidePhase.READY
    assert service.register_device({"path": DEVICE_PATH})
    assert service.verify_active().phase is hidhide.HidHidePhase.ACTIVE

    api.blacklist = ()
    missing = service.verify_active()
    assert missing.phase is hidhide.HidHidePhase.READY
    assert missing.hidden_device_count == 0
    assert service.register_device({"path": DEVICE_PATH})
    assert api.blacklist == (INSTANCE_ID,)

    api.active = False
    assert service.verify_active().phase is hidhide.HidHidePhase.ERROR
    assert "turned off" in service.snapshot().last_error
    assert service.snapshot().hidden_device_count == 0


def test_legacy_auto_config_preserves_existing_user_rules(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    other_device = r"HID\VID_1234&PID_5678\USER"
    api = _Api(
        whitelist=(APP_NT_PATH,),
        blacklist=(other_device,),
        active=True,
    )
    api.clear_error = _OldDriverError("unsupported")
    service = _service(tmp_path, api, automatic_legacy=True)

    assert service.start().phase is hidhide.HidHidePhase.READY
    assert service.register_device({"path": DEVICE_PATH}) is True
    assert service.stop(remove_allowlist=True).phase is hidhide.HidHidePhase.DISABLED
    assert api.blacklist == (other_device,)
    assert api.active is True
    assert api.whitelist == (APP_NT_PATH,)


def test_legacy_auto_config_recovers_owned_rule_after_interrupted_process(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    api = _Api(whitelist=(APP_NT_PATH,), blacklist=(INSTANCE_ID,), active=True)
    api.clear_error = _OldDriverError("unsupported")
    (tmp_path / "hidhide_device_owned.json").write_text(
        json.dumps({"schema": 1, "device_instance_ids": [INSTANCE_ID], "active_owned": True}),
        encoding="utf-8",
    )
    (tmp_path / "hidhide_owned.json").write_text(
        json.dumps({"schema": 1, "whitelist_paths": [APP_NT_PATH]}),
        encoding="utf-8",
    )
    service = _service(tmp_path, api, automatic_legacy=True)

    assert service.start().phase is hidhide.HidHidePhase.READY
    assert api.blacklist == ()
    assert api.active is True
    assert service.stop(remove_allowlist=True).phase is hidhide.HidHidePhase.DISABLED
    assert api.active is False


def test_legacy_auto_config_cleans_stale_rules_before_rejecting_inverse_mode(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    api = _Api(blacklist=(INSTANCE_ID,), active=True, inverse=True)
    api.clear_error = _OldDriverError("unsupported")
    (tmp_path / "hidhide_device_owned.json").write_text(
        json.dumps({"schema": 1, "device_instance_ids": [INSTANCE_ID], "active_owned": True}),
        encoding="utf-8",
    )
    service = _service(tmp_path, api, automatic_legacy=True)

    snapshot = service.start()
    assert snapshot.phase is hidhide.HidHidePhase.ERROR
    assert "inverse" in snapshot.last_error
    assert api.blacklist == ()
    assert api.active is False


def test_stale_auto_rule_is_removed_even_when_xbox_mode_is_not_started(tmp_path):
    api = _Api(blacklist=(INSTANCE_ID,), active=True)
    (tmp_path / "hidhide_device_owned.json").write_text(
        json.dumps({"schema": 1, "device_instance_ids": [INSTANCE_ID], "active_owned": True}),
        encoding="utf-8",
    )
    service = _service(tmp_path, api, automatic_legacy=True)

    assert service.stop().phase is hidhide.HidHidePhase.DISABLED
    assert api.blacklist == ()
    assert api.active is False


def test_legacy_auto_config_enables_existing_inactive_dualsense_rules(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    original = (BT_PARENT_ID, INSTANCE_ID)
    api = _Api(blacklist=original, active=False)
    api.clear_error = _OldDriverError("unsupported")
    service = _service(tmp_path, api, automatic_legacy=True)

    snapshot = service.start()
    assert snapshot.phase is hidhide.HidHidePhase.READY
    assert api.active is True
    assert service.register_device({"path": DEVICE_PATH}) is True
    assert service.stop().phase is hidhide.HidHidePhase.DISABLED
    assert api.active is False
    assert api.blacklist == original


def test_legacy_auto_config_rejects_other_inactive_device_rules(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    other_device = r"HID\VID_1234&PID_5678\USER"
    user_app = r"\Device\Volume\Other.exe"
    api = _Api(
        whitelist=(user_app,), blacklist=(BT_PARENT_ID, other_device), active=False
    )
    api.clear_error = _OldDriverError("unsupported")
    service = _service(tmp_path, api, automatic_legacy=True)

    snapshot = service.start()
    assert snapshot.phase is hidhide.HidHidePhase.ERROR
    assert "non-DualSense" in snapshot.last_error
    assert api.active is False
    assert api.blacklist == (BT_PARENT_ID, other_device)
    assert api.whitelist == (user_app,)


def test_official_hidhide_manual_mode_rejects_unhidden_device(tmp_path):
    class _OldDriverError(OSError):
        winerror = 1

    api = _Api(whitelist=(APP_NT_PATH,), active=True)
    api.clear_error = _OldDriverError("unsupported")
    service = _service(tmp_path, api)

    assert service.start().phase is hidhide.HidHidePhase.READY
    assert service.register_device({"path": DEVICE_PATH}) is False
    snapshot = service.snapshot()
    assert snapshot.phase is hidhide.HidHidePhase.ERROR
    assert snapshot.manual_configuration is True
    assert "Devices" in snapshot.last_error
    assert api.blacklist == ()
    assert not any(isinstance(call, tuple) for call in api.calls)


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
