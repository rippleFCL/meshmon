import datetime
import time

import structlog

from ..distrostore import NodeStatus, PingData
from ..pulsewave.store import SharedStore
from ..pulsewave.update.update import UpdateHandler, UpdateManager
from .connection import ConnectionManager
from .proto import ProtocolData, StoreHeartbeatAck, StoreUpdate


class GrpcUpdateHandler(UpdateHandler):
    """Handles incoming updates via gRPC."""

    def __init__(self, network_id: str, connection_manager: "ConnectionManager"):
        super().__init__()
        self.logger = structlog.stdlib.get_logger().bind(
            module="connection.update_handler",
            component="grpc_update_handler",
            network_id=network_id,
        )
        self.network_id = network_id
        self.connection_manager = connection_manager

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        """Process an incoming update request."""
        msg = self.store.dump()
        for node in self.store.nodes:
            if node == self.store.key_mapping.signer.node_id:
                continue
            conn = self.connection_manager.get_connection(node, self.network_id)
            if conn:
                conn.send_response(
                    ProtocolData(
                        store_update=StoreUpdate(
                            data=msg,
                            network_id=self.network_id,
                            node_id=self.store.key_mapping.signer.node_id,
                        )
                    )
                )
                ping_ctx = self.store.get_context("ping_data", PingData)
                if ping_ctx.get(node) is None:
                    ping_ctx.set(
                        node,
                        PingData(
                            status=NodeStatus.UNKNOWN,
                            req_time_rtt=-1,
                            date=datetime.datetime.now(datetime.timezone.utc),
                        ),
                    )

    def handle_incoming_update(self, update: StoreUpdate) -> None:
        """Handle an incoming StoreUpdate message."""
        if update.network_id != self.network_id:
            return  # Ignore updates for other networks
        if not hasattr(self, "store"):
            self.logger.info("Store not bound, cannot handle incoming update")
            return
        self.store.update_from_dump(update.data)

    def handle_heartbeat(self, heartbeat_ack: StoreHeartbeatAck) -> None:
        node_ctx = self.store.get_context("ping_data", PingData)
        if not heartbeat_ack.success:
            self.logger.warning(
                "Heartbeat ack indicates failure",
                from_node=heartbeat_ack.node_id,
                network_id=heartbeat_ack.network_id,
            )
            return

        node_ctx.set(
            heartbeat_ack.node_id,
            PingData(
                status=NodeStatus.ONLINE,
                req_time_rtt=(time.time_ns() - (heartbeat_ack.timestamp))
                / 1_000_000_000,  # Convert ns to s
                date=datetime.datetime.now(tz=datetime.timezone.utc),
            ),
        )
        self.logger.info(
            "Received heartbeat ack",
            from_node=heartbeat_ack.node_id,
            network_id=heartbeat_ack.network_id,
            ts=heartbeat_ack.timestamp,
            success=heartbeat_ack.success,
        )
