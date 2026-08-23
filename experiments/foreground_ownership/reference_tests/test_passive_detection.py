import ctypes

import pytest

from modules.dualsense import passive_detection


@pytest.mark.parametrize(
    "device_id",
    [
        r"HID\VID_054C&PID_0CE6&MI_03\8&123&0&0000",
        r"USB\VID_054C&PID_0DF2\EDGE",
        r"HID\{00001124-0000-1000-8000-00805F9B34FB}_VID&0002054C_PID&0CE6\BT",
    ],
)
def test_dualsense_instance_id_recognizes_usb_edge_and_bluetooth(device_id):
    assert passive_detection.is_dualsense_device_instance_id(device_id) is True


@pytest.mark.parametrize(
    "device_id",
    [
        r"HID\VID_054C&PID_09CC\DUALSHOCK4",
        r"HID\VID_045E&PID_0CE6\NOT_SONY",
        r"HID\VID_054C&PID_0CE7\NOT_DUALSENSE",
        "",
    ],
)
def test_dualsense_instance_id_rejects_other_devices(device_id):
    assert passive_detection.is_dualsense_device_instance_id(device_id) is False


def test_windows_presence_uses_configuration_manager_multisz_without_hidapi(monkeypatch):
    ids = (
        r"HID\VID_054C&PID_0CE6\ONE",
        r"HID\VID_045E&PID_028E\TWO",
    )
    payload = "\0".join(ids) + "\0\0"
    calls = []

    class Function:
        argtypes = None
        restype = None

        def __init__(self, callback):
            self._callback = callback

        def __call__(self, *args):
            return self._callback(*args)

    def get_size(required, _filter, flags):
        calls.append(("size", flags))
        ctypes.cast(required, ctypes.POINTER(ctypes.c_ulong)).contents.value = len(payload)
        return 0

    def get_list(_filter, buffer, capacity, flags):
        calls.append(("list", flags))
        assert capacity >= len(payload)
        for index, character in enumerate(payload):
            buffer[index] = character
        return 0

    library = type(
        "CfgMgr32",
        (),
        {
            "CM_Get_Device_ID_List_SizeW": Function(get_size),
            "CM_Get_Device_ID_ListW": Function(get_list),
        },
    )()
    monkeypatch.setattr(passive_detection.sys, "platform", "win32")

    found = passive_detection.windows_present_dualsense_ids(
        library_loader=lambda *_args, **_kwargs: library
    )

    assert found == (ids[0],)
    assert calls == [
        ("size", passive_detection._CM_GETIDLIST_FILTER_PRESENT),
        ("list", passive_detection._CM_GETIDLIST_FILTER_PRESENT),
    ]


def test_non_windows_presence_uses_only_the_injected_handle_free_enumerator(monkeypatch):
    calls = []
    monkeypatch.setattr(passive_detection.sys, "platform", "linux")

    count = passive_detection.passive_dualsense_count(
        lambda: calls.append("enumerate") or [{"path": "/dev/hidraw0"}]
    )

    assert count == 1
    assert calls == ["enumerate"]


def test_windows_ui_records_never_expose_a_hidapi_path(monkeypatch):
    monkeypatch.setattr(passive_detection.sys, "platform", "win32")
    monkeypatch.setattr(
        passive_detection,
        "windows_present_dualsense_count",
        lambda: 1,
    )

    assert passive_detection.passive_dualsense_records(lambda: pytest.fail()) == [
        {"passive": True, "pnp_record_count": 1}
    ]


def test_windows_presence_collapses_multiple_collections_for_one_controller(monkeypatch):
    monkeypatch.setattr(
        passive_detection,
        "windows_present_dualsense_ids",
        lambda: (
            r"HID\VID_054C&PID_0CE6&MI_03&COL01\USB-ONE",
            r"HID\VID_054C&PID_0CE6&MI_03&COL02\USB-ONE",
            r"HID\{GUID}_VID&0002054C_PID&0CE6&COL01\8&ABC&0&001122334455_C00000000",
            r"HID\{GUID}_VID&0002054C_PID&0CE6&COL02\8&ABC&0&001122334455_C00000000",
        ),
    )
    monkeypatch.setattr(
        passive_detection,
        "_windows_connected_bluetooth_macs",
        lambda: frozenset({"001122334455"}),
    )

    assert passive_detection.windows_present_dualsense_count() == 1


def test_remembered_bluetooth_pnp_nodes_do_not_report_a_powered_off_controller(
    monkeypatch,
):
    monkeypatch.setattr(
        passive_detection,
        "windows_present_dualsense_ids",
        lambda: (
            r"HID\{GUID}_VID&0002054C_PID&0CE6&COL01\8&ABC&0&001122334455_C00000000",
            r"HID\{GUID}_VID&0002054C_PID&0CE6&COL02\8&ABC&0&001122334455_C00000000",
        ),
    )
    monkeypatch.setattr(
        passive_detection,
        "_windows_connected_bluetooth_macs",
        lambda: frozenset(),
    )

    assert passive_detection.windows_present_dualsense_count() == 0


def test_connected_bluetooth_api_result_keeps_a_live_controller_available(
    monkeypatch,
):
    monkeypatch.setattr(
        passive_detection,
        "windows_present_dualsense_ids",
        lambda: (
            r"HID\{GUID}_VID&0002054C_PID&0CE6&COL01\8&ABC&0&001122334455_C00000000",
        ),
    )
    monkeypatch.setattr(
        passive_detection,
        "_windows_connected_bluetooth_macs",
        lambda: frozenset({"001122334455"}),
    )

    assert passive_detection.windows_present_dualsense_count() == 1


def test_bluetooth_search_requests_only_connected_devices(monkeypatch):
    closed = []

    class Function:
        argtypes = None
        restype = None

        def __init__(self, callback):
            self._callback = callback

        def __call__(self, *args):
            return self._callback(*args)

    def find_first(search_pointer, info_pointer):
        search = ctypes.cast(
            search_pointer,
            ctypes.POINTER(passive_detection._BluetoothDeviceSearchParams),
        ).contents
        assert bool(search.return_connected) is True
        assert bool(search.return_remembered) is False
        info = ctypes.cast(
            info_pointer,
            ctypes.POINTER(passive_detection._BluetoothDeviceInfo),
        ).contents
        info.connected = True
        info.address.value = int("001122334455", 16)
        return 123

    library = type(
        "BluetoothApi",
        (),
        {
            "BluetoothFindFirstDevice": Function(find_first),
            "BluetoothFindNextDevice": Function(lambda *_args: False),
            "BluetoothFindDeviceClose": Function(
                lambda handle: closed.append(handle) or True
            ),
        },
    )()
    monkeypatch.setattr(passive_detection.sys, "platform", "win32")

    connected = passive_detection._windows_connected_bluetooth_macs(
        library_loader=lambda *_args, **_kwargs: library
    )

    assert connected == frozenset({"001122334455"})
    assert closed == [123]
