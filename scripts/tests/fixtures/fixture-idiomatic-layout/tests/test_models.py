from myapp.models import DeviceInfo


def test_device_info():
    d = DeviceInfo(name="a", address="b")
    assert d.name == "a"
