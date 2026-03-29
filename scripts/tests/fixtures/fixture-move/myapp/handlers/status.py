from myapp.models import DeviceInfo
from myapp.utils import format_device


def handle_status(device: DeviceInfo) -> str:
    return format_device(device)
