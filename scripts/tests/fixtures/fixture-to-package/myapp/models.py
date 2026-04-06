from dataclasses import dataclass
from enum import Enum


class DeviceType(Enum):
    SENSOR = "sensor"
    ACTUATOR = "actuator"


@dataclass
class DeviceInfo:
    name: str
    address: str
    device_type: DeviceType


@dataclass
class DeviceStatus:
    online: bool
    battery: int
