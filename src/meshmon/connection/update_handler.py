import datetime
import time

import structlog

# Import metrics
from meshmon.prom_export import record_heartbeat_latency
from meshmon.pulsewave.update.events import ExactPathMatcher

from ..dstypes import DSNodeStatus, DSPingData
from ..pulsewave.crypto import KeyMapping
from ..pulsewave.data import StoreData
from ..pulsewave.store import SharedStore
from ..pulsewave.update.update import UpdateHandler, UpdateManager
from .connection import ConnectionManager
from .grpc_types import HeartbeatResponse, StoreUpdate


class IncrementalUpdater:
    def __init__(self):
        self.end_data = StoreData()

    def diff(self, other: StoreData, exclude_node_id: str) -> StoreData:
        diff = self.end_data.diff(other)
        if exclude_node_id in diff.nodes:
            del diff.nodes[exclude_node_id]
        return diff

    def update(self, other: StoreData, key_mapping: KeyMapping):
        self.end_data.update(other, key_mapping)

    def clear(self):
        self.end_data = StoreData()


class GrpcUpdateHandler(UpdateHandler):
    """Handles incoming updates via gRPC."""

    def __init__(self, network_id: str, connection_manager: "ConnectionManager"):
        super().__init__()
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.connection.update_handler",
            component="GrpcUpdateHandler",
            network_id=network_id,
        )
        self._matcher = ExactPathMatcher("instant_update")
        self.network_id = network_id
        self.connection_manager = connection_manager

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        """Process an incoming update request."""
        msg = self.store.dump()
        ping_ctx = self.store.get_context("ping_data", DSPingData)
        for node in self.store.nodes:
            if node == self.store.config.key_mapping.signer.node_id:
                continue
            conn = self.connection_manager.get_connection(node, self.network_id)
            if conn:
                conn.send_response(StoreUpdate(data=msg))
                if ping_ctx.get(node) is None:
                    ping_ctx.set(
                        node,
                        DSPingData(
                            status=DSNodeStatus.UNKNOWN,
                            req_time_rtt=-1,
                            date=datetime.datetime.now(datetime.timezone.utc),
                        ),
                    )

    def handle_incoming_update(self, update: StoreUpdate) -> None:
        """Handle an incoming StoreUpdate message."""
        if not hasattr(self, "store"):
            self.logger.info("Store not bound, cannot handle incoming update")
            return
        self.store.update_from_dump(update.data)

    def handle_heartbeat(self, heartbeat_ack: HeartbeatResponse, node_id: str) -> None:
        node_ctx = self.store.get_context("ping_data", DSPingData)

        current_status = node_ctx.get(node_id)
        if current_status and current_status.status == DSNodeStatus.OFFLINE:
            self.logger.info(
                "Node is now online",
                node_id=node_id,
            )

        # Calculate RTT
        rtt_seconds = (time.time_ns() - (heartbeat_ack.node_time)) / 1_000_000_000

        node_ctx.set(
            node_id,
            DSPingData(
                status=DSNodeStatus.ONLINE,
                req_time_rtt=rtt_seconds,
                date=datetime.datetime.now(tz=datetime.timezone.utc),
            ),
        )

        # Record heartbeat latency metric
        record_heartbeat_latency(
            network_id=self.network_id,
            node_id=node_id,
            latency_seconds=rtt_seconds,
        )

    def stop(self) -> None:
        """Stop any background tasks."""
        pass

    def matcher(self) -> ExactPathMatcher:
        return self._matcher
