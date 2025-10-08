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
        if request.HasField("store_update"):
            self.handler.handle_incoming_update(request.store_update)
        elif request.HasField("heartbeat_ack"):
            self.logger.debug(
                "Received heartbeat ack",
                from_node=request.heartbeat_ack.node_id,
                network_id=request.heartbeat_ack.network_id,
            )
            self.handler.handle_heartbeat(request.heartbeat_ack)

        else:
            self.logger.warning(
                "Unknown ProtocolData message received", request=request
            )
