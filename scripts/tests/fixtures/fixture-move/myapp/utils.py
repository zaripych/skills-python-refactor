from myapp.models import DeviceInfo


def format_device(device: DeviceInfo) -> str:
    return f"{device.name} ({device.address})"
