import ctypes

import pytest

from modules.xinput.report import XUSBReport
from modules.xinput.vigem_client import ViGEmClient, ViGEmError, ViGEmErrorCode


class _Function:
    def __init__(self, name, calls, result=None):
        self.name = name
        self.calls = calls
        self.result = result
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        self.calls.append((self.name, args))
        return self.result


class _DLL:
    def __init__(self, **results):
        self.calls = []
        defaults = {
            "vigem_alloc": 0xCAFE,
            "vigem_free": None,
            "vigem_connect": ViGEmErrorCode.NONE,
            "vigem_disconnect": None,
            "vigem_target_x360_alloc": 0xBEEF,
            "vigem_target_free": None,
            "vigem_target_add": ViGEmErrorCode.NONE,
            "vigem_target_remove": ViGEmErrorCode.NONE,
            "vigem_target_x360_update": ViGEmErrorCode.NONE,
        }
        defaults.update(results)
        for name, result in defaults.items():
            setattr(self, name, _Function(name, self.calls, result))


def _names(dll):
    return [name for name, _args in dll.calls]


def test_binds_exact_minimum_abi_and_runs_ordered_lifecycle():
    dll = _DLL()
    client = ViGEmClient(dll=dll)
    client.connect()
    target = client.create_x360_target()
    target.update(XUSBReport(wButtons=0x1000))
    target.close()
    client.close()

    assert _names(dll) == [
        "vigem_alloc",
        "vigem_connect",
        "vigem_target_x360_alloc",
        "vigem_target_add",
        "vigem_target_x360_update",
        "vigem_target_remove",
        "vigem_target_free",
        "vigem_disconnect",
        "vigem_free",
    ]
    assert dll.vigem_target_x360_update.argtypes == (
        ctypes.c_void_p,
        ctypes.c_void_p,
        XUSBReport,
    )


def test_connect_failure_frees_client_handle():
    dll = _DLL(vigem_connect=ViGEmErrorCode.BUS_NOT_FOUND)
    client = ViGEmClient(dll=dll)

    with pytest.raises(ViGEmError, match="BUS_NOT_FOUND") as error:
        client.connect()

    assert error.value.code == ViGEmErrorCode.BUS_NOT_FOUND
    assert client.connected is False
    assert _names(dll) == ["vigem_alloc", "vigem_connect", "vigem_free"]


def test_target_add_failure_frees_target_without_remove():
    dll = _DLL(vigem_target_add=ViGEmErrorCode.NO_FREE_SLOT)
    client = ViGEmClient(dll=dll)
    client.connect()

    with pytest.raises(ViGEmError, match="NO_FREE_SLOT"):
        client.create_x360_target()

    client.close()
    assert _names(dll) == [
        "vigem_alloc",
        "vigem_connect",
        "vigem_target_x360_alloc",
        "vigem_target_add",
        "vigem_target_free",
        "vigem_disconnect",
        "vigem_free",
    ]


def test_remove_failure_still_frees_target_and_cleanup_is_idempotent():
    dll = _DLL(vigem_target_remove=ViGEmErrorCode.REMOVAL_FAILED)
    client = ViGEmClient(dll=dll)
    client.connect()
    target = client.create_x360_target()

    with pytest.raises(ViGEmError, match="REMOVAL_FAILED"):
        target.close()
    target.close()
    client.close()
    client.close()

    assert _names(dll).count("vigem_target_remove") == 1
    assert _names(dll).count("vigem_target_free") == 1
    assert _names(dll).count("vigem_free") == 1


def test_client_close_cleans_owned_targets_before_disconnect():
    dll = _DLL()
    client = ViGEmClient(dll=dll)
    client.connect()
    client.create_x360_target()

    client.close()

    assert _names(dll)[-4:] == [
        "vigem_target_remove",
        "vigem_target_free",
        "vigem_disconnect",
        "vigem_free",
    ]


def test_missing_required_export_is_rejected_during_binding():
    dll = _DLL()
    del dll.vigem_target_x360_update

    with pytest.raises(ViGEmError, match="missing ViGEmClient export"):
        ViGEmClient(dll=dll)
