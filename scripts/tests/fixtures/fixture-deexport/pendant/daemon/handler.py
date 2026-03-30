from .protocol import MessageType


class RequestHandler:
    def process(self, msg_type: MessageType) -> str:
        return f"handled {msg_type.value}"
