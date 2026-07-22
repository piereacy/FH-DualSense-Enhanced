import pytest

from modules.haptics.windows_endpoint import (
    DEVICE_DESCRIPTION_PROPERTY,
    DEVICE_INSTANCE_PROPERTY,
    RENDER_ENDPOINTS_KEY,
    is_dualsense_usb_audio_endpoint_ready,
)


class _Key:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        return False


class _Registry:
    HKEY_LOCAL_MACHINE = object()
    KEY_READ = 0x20019

    def __init__(self, *, state=1, instance=None, description=None, root_error=None):
        self.root_error = root_error
        endpoint = RENDER_ENDPOINTS_KEY + r"\{controller}"
        properties = endpoint + r"\Properties"
        self.tree = {
            RENDER_ENDPOINTS_KEY: {
                "children": ["{controller}"],
                "values": {},
            },
            endpoint: {
                "children": ["Properties"],
                "values": {"DeviceState": state},
            },
            properties: {
                "children": [],
                "values": {
                    DEVICE_INSTANCE_PROPERTY: (
                        instance
                        if instance is not None
                        else r"{1}.USB\VID_054C&PID_0CE6&MI_00\TEST"
                    ),
                    DEVICE_DESCRIPTION_PROPERTY: (
                        description
                        if description is not None
                        else "DualSense Wireless Controller"
                    ),
                },
            },
        }

    def OpenKey(self, root, subkey, _reserved=0, _access=0):
        if root is self.HKEY_LOCAL_MACHINE:
            if self.root_error is not None:
                raise self.root_error
            path = subkey
        else:
            path = root.path + "\\" + subkey
        if path not in self.tree:
            raise FileNotFoundError(path)
        return _Key(path)

    def EnumKey(self, key, index):
        children = self.tree[key.path]["children"]
        if index >= len(children):
            raise OSError("end")
        return children[index]

    def QueryValueEx(self, key, name):
        values = self.tree[key.path]["values"]
        if name not in values:
            raise FileNotFoundError(name)
        return values[name], 1


def test_active_dualsense_usb_render_endpoint_is_ready():
    assert is_dualsense_usb_audio_endpoint_ready(
        platform="win32",
        registry_module=_Registry(),
    ) is True


def test_dualsense_edge_usb_render_endpoint_is_ready():
    registry = _Registry(
        instance=r"{1}.USB\VID_054C&PID_0DF2&MI_00\TEST",
        description="DualSense Edge Wireless Controller",
    )

    assert is_dualsense_usb_audio_endpoint_ready(
        platform="win32",
        registry_module=registry,
    ) is True


@pytest.mark.parametrize(
    ("state", "instance", "description"),
    [
        (4, None, None),
        (1, r"USB\VID_1234&PID_0CE6&MI_00\TEST", None),
        (1, r"USB\VID_054C&PID_9999&MI_00\TEST", None),
        (1, r"USB\VID_054C&PID_0CE6&MI_03\TEST", None),
        (1, None, "Unrelated Audio Device"),
    ],
)
def test_nonmatching_or_inactive_endpoint_is_not_ready(state, instance, description):
    assert is_dualsense_usb_audio_endpoint_ready(
        platform="win32",
        registry_module=_Registry(
            state=state,
            instance=instance,
            description=description,
        ),
    ) is False


def test_registry_failure_retains_bluetooth_by_reporting_not_ready():
    assert is_dualsense_usb_audio_endpoint_ready(
        platform="win32",
        registry_module=_Registry(root_error=PermissionError("denied")),
    ) is False


def test_non_windows_does_not_apply_windows_endpoint_gate():
    assert is_dualsense_usb_audio_endpoint_ready(
        platform="linux",
        registry_module=_Registry(root_error=AssertionError("must not access registry")),
    ) is True
