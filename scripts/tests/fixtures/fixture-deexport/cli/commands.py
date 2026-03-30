from pendant.daemon import ProtocolHandler, RequestHandler, MessageType


def execute():
    handler = ProtocolHandler()
    handler.handle(MessageType.REQUEST)
    req = RequestHandler()
    return req.process(MessageType.RESPONSE)
