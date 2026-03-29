from dataclasses import dataclass


@dataclass
class DeviceInfo:
    name: str
    address: str


@dataclass
class DeviceStatus:
    online: bool
    battery: int
