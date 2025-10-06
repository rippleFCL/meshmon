import structlog

from ..pulsewave.store import SharedStore
from ..pulsewave.update.update import UpdateHandler, UpdateManager
from .connection import ConnectionManager
from .proto import ProtocolData, StoreUpdate


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

    def handle_incoming_update(self, update: StoreUpdate) -> None:
        """Handle an incoming StoreUpdate message."""
        if update.network_id != self.network_id:
            return  # Ignore updates for other networks
        if not hasattr(self, "store"):
            self.logger.info("Store not bound, cannot handle incoming update")
            return
        self.logger.debug("Handling incoming update", src_id=update.node_id)
        self.store.update_from_dump(update.data)
