from pendant import StatusCommand, DeviceInfo
from pendant import format_name


def run():
    cmd = StatusCommand("device1")
    info = DeviceInfo(name=format_name("raw name"), address="localhost:8080")
    return cmd, info
