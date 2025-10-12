from structlog import get_logger

from meshmon.pulsewave.crypto import Signer, Verifier

from ..pulsewave.data import SignedBlockData
from .connection import ProtocolHandler, RawConnection
from .grpc_types import Heartbeat, HeartbeatResponse, StoreUpdate, Validator
from .proto import PacketData
from .update_handler import GrpcUpdateHandler


class PulseWaveProtocol(ProtocolHandler):
    def __init__(
        self,
        handler: GrpcUpdateHandler,
        recv_nonce: Validator,
        send_nonce: Validator,
        signer: Signer,
        verifier: Verifier,
        mr_sbd: SignedBlockData,
    ):
        self.recv_nonce = recv_nonce
        self.send_nonce = send_nonce
        self.handler = handler
        self.signer = signer
        self.verifier = verifier
        self.mr_sbd = mr_sbd
        self.logger = get_logger().bind(
            module="connection.protocol_handler", component="pulse_wave_protocol"
        )

    def build_packet(
        self, data: StoreUpdate | Heartbeat | HeartbeatResponse
    ) -> PacketData | None:
        verifier = SignedBlockData.new(
            self.signer, self.send_nonce, "validator", "validator"
        )
        if isinstance(data, StoreUpdate):
            return PacketData(
                packet_id="store_update",
                data=data.model_dump_json(),
                validator=verifier.model_dump_json(),
            )
        if isinstance(data, Heartbeat):
            return PacketData(
                packet_id="heartbeat",
                data=data.model_dump_json(),
                validator=verifier.model_dump_json(),
            )
        if isinstance(data, HeartbeatResponse):
            return PacketData(
                packet_id="heartbeat_response",
                data=data.model_dump_json(),
                validator=verifier.model_dump_json(),
            )

    def handle_packet(self, request: PacketData, conn: "RawConnection") -> None:
        sbd = SignedBlockData.model_validate_json(request.validator)
        validator = Validator.model_validate(sbd.data)
        if sbd.date <= self.mr_sbd.date:
            self.logger.warning(
                "Received out-of-date packet_data, ignoring",
                node_id=self.verifier.node_id,
            )
            return

        if validator != self.recv_nonce:
            self.logger.warning(
                "Received packet_data with invalid nonce, ignoring",
                node_id=self.verifier.node_id,
            )
            return

        if not sbd.verify(self.verifier, "validator", "validator"):
            self.logger.warning(
                "Received packet_data with invalid validator signature, ignoring",
                node_id=self.verifier.node_id,
            )
            return
        self.mr_sbd = sbd  # Update most recent signed block data
        if request.packet_id == "store_update":
            try:
                store_data = StoreUpdate.model_validate_json(request.data)
                self.handler.handle_incoming_update(store_data)
            except Exception as e:
                self.logger.error("Failed to handle StoreUpdate", error=str(e))
        elif request.packet_id == "heartbeat":
            try:
                heartbeat = Heartbeat.model_validate_json(request.data)
                response = HeartbeatResponse(node_time=heartbeat.node_time)
                conn.send_response(response)
            except Exception as e:
                self.logger.error("Failed to handle Heartbeat", error=str(e))
        elif request.packet_id == "heartbeat_response":
            try:
                heartbeat_ack = HeartbeatResponse.model_validate_json(request.data)
                self.handler.handle_heartbeat(heartbeat_ack, self.verifier.node_id)
            except Exception as e:
                self.logger.error("Failed to handle HeartbeatResponse", error=str(e))
