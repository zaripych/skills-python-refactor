from .protocol import MessageType


class RequestHandler:
    def process(self, msg_type: MessageType) -> str:
        return f"handled {msg_type.value}"

    def lazy_load(self):
        from ..config import get_settings

        return get_settings()
