from pendant.daemon import MessageType, ProtocolHandler


def test_protocol():
    handler = ProtocolHandler()
    handler.handle(MessageType.REQUEST)
