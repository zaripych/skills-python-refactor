from .utils import format_name


class StatusCommand:
    def __init__(self, target: str):
        self.target = target

    def label(self) -> str:
        return format_name(self.target)


class DeviceInfo:
    def __init__(self, name: str, address: str):
        self.name = name
        self.address = address
