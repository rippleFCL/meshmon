from structlog import get_logger

from .connection import Connection, ProtocolHandler
from .proto import ProtocolData
from .update_handler import GrpcUpdateHandler


class PulseWaveProtocol(ProtocolHandler):
    def __init__(self, handler: GrpcUpdateHandler):
        self.connection: Connection | None = None
        self.handler = handler
        self.logger = get_logger().bind(
            module="connection.protocol_handler", component="pulse_wave_protocol"
        )

    def bind_connection(self, connection: "Connection") -> None:
        self.connection = connection

    def handle_packet(self, request: ProtocolData) -> None:
        if not self.connection:
            return
        if request.store_update:
            self.handler.handle_incoming_update(request.store_update)
