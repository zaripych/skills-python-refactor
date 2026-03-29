import pytest
from myapp.models import DeviceInfo


@pytest.mark.parametrize("name", ["alpha", "beta"])
def test_device_info(name):
    device = DeviceInfo(name=name, address="00:11:22")
    assert device.name == name


def test_device_info_str(capsys):
    device = DeviceInfo(name="test", address="AA:BB:CC")
    print(device)
    captured = capsys.readouterr()
    assert "test" in captured.out
