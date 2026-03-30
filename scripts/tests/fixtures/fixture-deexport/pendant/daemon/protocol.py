from enum import Enum


class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"


class ProtocolHandler:
    def handle(self, msg_type: MessageType) -> None:
        pass
