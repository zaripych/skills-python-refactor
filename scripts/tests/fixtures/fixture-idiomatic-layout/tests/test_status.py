from myapp.handlers.status import handle_status
from myapp.models import DeviceInfo


def test_handle_status():
    d = DeviceInfo(name="a", address="b")
    assert handle_status(d) == "a"
