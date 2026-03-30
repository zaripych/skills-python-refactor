from .protocol import ProtocolHandler, MessageType
from .handler import RequestHandler


def build_registry() -> dict[str, ProtocolHandler | RequestHandler]:
    """Uses re-exported names locally."""
    return {
        MessageType.REQUEST.value: ProtocolHandler(),
        "handle": RequestHandler(),
    }
