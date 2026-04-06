from myapp.models import DeviceInfo, DeviceStatus


def handle_status(device: DeviceInfo) -> DeviceStatus:
    return DeviceStatus(online=True, battery=100)
