from myapp.models import DeviceInfo


def handle_status(device: DeviceInfo) -> str:
    return device.name
