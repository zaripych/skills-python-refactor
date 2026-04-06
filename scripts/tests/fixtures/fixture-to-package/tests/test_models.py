from myapp.models import DeviceInfo, DeviceType


def test_device_info():
    device = DeviceInfo(
        name="sensor1", address="00:11:22", device_type=DeviceType.SENSOR
    )
    assert device.name == "sensor1"
