import datetime
from enum import Enum
from typing import TYPE_CHECKING

import structlog
from pydantic import BaseModel

from .config import NetworkConfig, NetworkConfigLoader
from .pulsewave.config import CurrentNode, NodeConfig, PulseWaveConfig
from .pulsewave.store import SharedStore

if TYPE_CHECKING:
    from .connection.grpc_server import GrpcServer


class NodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class PingData(BaseModel):
    status: NodeStatus
    req_time_rtt: float
    date: datetime.datetime


class NodeInfo(BaseModel):
    status: NodeStatus
    version: str


class NodeDataRetention(BaseModel):
    date: datetime.datetime


class StoreManager:
    def __init__(
        self,
        config: NetworkConfigLoader,
        grpc_server: "GrpcServer",
    ):
        self.config = config
        self.stores: dict[str, SharedStore] = {}
        self.logger = structlog.stdlib.get_logger().bind(
            module="pulsewave.distrostore", component="StoreManager"
        )

        # gRPC components for each network
        self.grpc_server = grpc_server

        self.load_stores()

    def _pulse_wave_config(self, network: NetworkConfig) -> PulseWaveConfig:
        """Create PulseWaveConfig from NetworkConfig."""
        # Create CurrentNode from network configuration
        current_node = CurrentNode(
            node_id=network.node_id,
            signer=network.key_mapping.signer,
            verifier=network.key_mapping.signer.get_verifier(),
        )

        # Create nodes dict from network node configuration
        nodes = {}
        for node_info in network.node_config:
            verifier = network.get_verifier(node_info.node_id)
            if verifier:
                nodes[node_info.node_id] = NodeConfig(
                    node_id=node_info.node_id,
                    uri=node_info.url or "",
                    verifier=verifier,
                    heartbeat_interval=node_info.poll_rate,
                    heartbeat_retry=node_info.retry,
                )

        return PulseWaveConfig(
            current_node=current_node,
            nodes=nodes,
            update_rate_limit=1,  # Default rate limit
            clock_pulse_interval=1,  # Default clock pulse interval
        )

    def load_stores(self):
        for network in self.config.networks.values():
            db_config = self._pulse_wave_config(network)

            # Create LocalStores instance for this StoreManager

            # Create gRPC handler for this network
            grpc_handler = self.grpc_server.get_handler(network.network_id)

            # Create the store with local handler
            new_store = SharedStore(db_config, grpc_handler)

            # Bind the gRPC handler to the store
            grpc_handler.bind(new_store, new_store.update_manager)

            if network.network_id in self.stores:
                self.logger.info(
                    "Store already exists; loading data from existing store",
                    network_id=network.network_id,
                )
                new_store.update_from_dump(self.stores[network.network_id].dump())
            else:
                self.logger.info(
                    "Creating new store",
                    network_id=network.network_id,
                )

            self.stores[network.network_id] = new_store

            self.logger.debug("Loaded store", network_id=network.network_id)

        for network_id in list(self.stores.keys()):
            if network_id not in self.config.networks:
                self.logger.info(
                    "Removing obsolete store",
                    network_id=network_id,
                )
                self.grpc_server.stop(5)
                del self.stores[network_id]

    def reload(self):
        self.load_stores()

    def get_store(self, network_id: str):
        return self.stores[network_id]

    def stop(self): ...
