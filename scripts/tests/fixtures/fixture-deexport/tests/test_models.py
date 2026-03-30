from pendant import StatusCommand, DeviceInfo


def test_status_command():
    cmd = StatusCommand("test")
    assert cmd.target == "test"


def test_device_info():
    info = DeviceInfo(name="dev", address="localhost:80")
    assert info.name == "dev"
