import time
from dataclasses import dataclass

from structlog import get_logger

from ..config.bus import ConfigPreprocessor, ConfigWatcher
from ..config.config import Config

# Import metrics recording functions
from ..prom_export import (
    record_packet_processing_duration,
    record_packet_received,
    record_packet_sent,
)
from ..pulsewave.crypto import Signer, Verifier
from ..pulsewave.data import SignedBlockData
from .connection import ProtocolHandler, RawConnection
from .grpc_types import Heartbeat, HeartbeatResponse, StoreUpdate, Validator
from .proto import PacketData
from .update_handler import GrpcUpdateHandler


@dataclass
class ConnectionConfig:
    """Config for a specific GrpcClient instance"""

    verifier: Verifier
    signer: Signer
    remote_node_id: str
    local_node_id: str
    network_id: str


class ConnectionConfigPreprocessor(ConfigPreprocessor[ConnectionConfig]):
    """Preprocessor for a specific client's config based on network_id and peer_node_id"""

    def __init__(self, network_id: str, peer_node_id: str):
        self.network_id = network_id
        self.peer_node_id = peer_node_id

    def preprocess(self, config: Config | None) -> ConnectionConfig | None:
        if config is None:
            return None

        network = config.networks.get(self.network_id)
        if network is None:
            return None

        verifier = network.key_mapping.get_verifier(self.peer_node_id)
        if verifier is None:
            return None
        signer = network.key_mapping.signer
        return ConnectionConfig(
            verifier=verifier,
            signer=signer,
            remote_node_id=verifier.node_id,
            local_node_id=signer.node_id,
            network_id=self.network_id,
        )


class PulseWaveProtocol(ProtocolHandler):
    def __init__(
        self,
        handler: GrpcUpdateHandler,
        remote_nonce: str,
        local_nonce: str,
        watcher: ConfigWatcher[ConnectionConfig],
        mr_sbd: SignedBlockData,
    ):
        self.watcher = watcher
        self.watcher.subscribe(self.load)
        self.remote_nonce = remote_nonce
        self.local_nonce = local_nonce
        self.handler = handler
        self.mr_sbd = mr_sbd
        self.logger = get_logger().bind(
            module="meshmon.connection.protocol_handler", component="PulseWaveProtocol"
        )

        self.load(self.watcher.current_config)

    def load(self, config: ConnectionConfig):
        self.logger.info(
            "Config reload triggered for PulseWaveProtocol",
            network_id=config.network_id,
            local_node_id=config.local_node_id,
            remote_node_id=config.remote_node_id,
        )
        self.signer = config.signer
        self.verifier = config.verifier

        self.send_nonce = Validator(
            local_nonce=self.local_nonce,
            remote_nonce=self.remote_nonce,
            network_id=config.network_id,
            node_id=config.signer.node_id,
        )

        self.recv_nonce = Validator(
            local_nonce=self.remote_nonce,
            remote_nonce=self.local_nonce,
            network_id=config.network_id,
            node_id=config.verifier.node_id,
        )
        self.logger.debug(
            "PulseWaveProtocol config updated successfully",
            network_id=config.network_id,
        )

    def build_packet(
        self, data: StoreUpdate | Heartbeat | HeartbeatResponse
    ) -> PacketData | None:
        verifier = SignedBlockData.new(
            self.signer, self.send_nonce, "validator", "validator"
        )
        packet = None
        packet_type = ""

        if isinstance(data, StoreUpdate):
            packet_type = "store_update"
            packet = PacketData(
                packet_id="store_update",
                data=data.model_dump_json(),
                validator=verifier.model_dump_json(),
            )
        elif isinstance(data, Heartbeat):
            packet_type = "heartbeat"
            packet = PacketData(
                packet_id="heartbeat",
                data=data.model_dump_json(),
                validator=verifier.model_dump_json(),
            )
        elif isinstance(data, HeartbeatResponse):
            packet_type = "heartbeat_response"
            packet = PacketData(
                packet_id="heartbeat_response",
                data=data.model_dump_json(),
                validator=verifier.model_dump_json(),
            )

        # Record metrics for sent packet
        size_bytes = len(packet.data.encode("utf-8"))
        record_packet_sent(
            network_id=self.send_nonce.network_id,
            dest_node_id=self.verifier.node_id,
            packet_type=packet_type,
            size_bytes=size_bytes,
        )

        return packet

    def handle_packet(self, request: PacketData, conn: "RawConnection") -> None:
        start_time = time.time()

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

        # Record metrics for received packet
        size_bytes = len(request.data.encode("utf-8"))
        record_packet_received(
            network_id=self.recv_nonce.network_id,
            source_node_id=self.verifier.node_id,
            packet_type=request.packet_id,
            size_bytes=size_bytes,
        )

        # Process the packet based on type
        if request.packet_id == "store_update":
            try:
                store_data = StoreUpdate.model_validate_json(request.data)
                self.handler.handle_incoming_update(store_data)
            except Exception as e:
                self.logger.error("Failed to handle StoreUpdate", error=e)
        elif request.packet_id == "heartbeat":
            try:
                heartbeat = Heartbeat.model_validate_json(request.data)
                response = HeartbeatResponse(node_time=heartbeat.node_time)
                conn.send_response(response)
            except Exception as e:
                self.logger.error("Failed to handle Heartbeat", error=e)
        elif request.packet_id == "heartbeat_response":
            try:
                heartbeat_ack = HeartbeatResponse.model_validate_json(request.data)
                self.handler.handle_heartbeat(heartbeat_ack, self.verifier.node_id)
            except Exception as e:
                self.logger.error("Failed to handle HeartbeatResponse", error=e)

        # Record packet processing duration
        duration = time.time() - start_time
        record_packet_processing_duration(
            network_id=self.recv_nonce.network_id,
            packet_type=request.packet_id,
            duration_seconds=duration,
        )
