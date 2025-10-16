from typing import TYPE_CHECKING

import structlog

from .config.bus import ConfigBus, ConfigPreprocessor
from .config.config import Config
from .pulsewave.config import CurrentNode, NodeConfig, PulseWaveConfig
from .pulsewave.store import SharedStore
from .update_handlers import (
    MonitorStatusTableHandler,
    MonitorStatusTablePreprocessor,
    NodeStatusTableHandler,
)

if TYPE_CHECKING:
    from .connection.grpc_server import GrpcServer


class StoreManagerConfigPreprocessor(ConfigPreprocessor[set[str]]):
    def preprocess(self, config: Config | None) -> set[str]:
        if config is None:
            return set()
        return set(config.networks.keys())


class PulseWaveConfigPreprocessor(ConfigPreprocessor[PulseWaveConfig]):
    def __init__(self, network_id: str):
        self.network_id = network_id

    def preprocess(self, config: Config | None) -> PulseWaveConfig | None:
        if config is None:
            return None
        network = config.networks.get(self.network_id)
        if network is None:
            return None
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


class StoreManager:
    def __init__(
        self,
        config_bus: ConfigBus,
        grpc_server: "GrpcServer",
    ):
        watcher = config_bus.get_watcher(StoreManagerConfigPreprocessor())
        if watcher is None:
            raise ValueError("No initial config available for store manager")
        self.config_watcher = watcher
        self.config_watcher.subscribe(self.load_config)
        self.config_bus = config_bus
        self.stores: dict[str, SharedStore] = {}
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.distrostore", component="StoreManager"
        )
        # gRPC components for each network
        self.grpc_server = grpc_server

    def create_store(self, network_id: str) -> None:
        self.logger.info("Creating store for network", network_id=network_id)
        config_watcher = self.config_bus.get_watcher(
            PulseWaveConfigPreprocessor(network_id)
        )
        if config_watcher is None:
            self.logger.warning(
                "Could not create config watcher for network", network_id=network_id
            )
            return
            # Create LocalStores instance for this StoreManager

            # Create gRPC handler for this network
        grpc_handler = self.grpc_server.get_handler(network_id)

        # Create the store with local handler
        watcher = self.config_bus.get_watcher(
            MonitorStatusTablePreprocessor(network_id)
        )
        if watcher is None:
            self.logger.warning(
                "Could not create monitor config watcher for network",
                network_id=network_id,
            )
            return
        new_store = SharedStore(config_watcher, grpc_handler)
        new_store.start()
        new_store.add_handler(MonitorStatusTableHandler(watcher))
        new_store.add_handler(NodeStatusTableHandler())

        self.stores[network_id] = new_store

        self.logger.debug("Loaded store", network_id=network_id)

    def get_store(self, network_id: str):
        return self.stores[network_id]

    def load_config(self, networks: set[str]):
        self.logger.info(
            "Config reload triggered for StoreManager",
            new_network_count=len(networks),
            current_network_count=len(self.stores),
        )
        current_networks = set(self.stores.keys())
        to_add = networks - current_networks
        to_remove = current_networks - networks

        self.logger.debug(
            "Store changes to apply",
            networks_to_add=list(to_add),
            networks_to_remove=list(to_remove),
        )

        for network_id in to_add:
            self.logger.debug("Creating store for new network", network_id=network_id)
            self.create_store(network_id)
        for network_id in to_remove:
            self.logger.info("Removing store for network", network_id=network_id)
            store = self.stores[network_id]
            store.stop()
            del self.stores[network_id]

        self.logger.info(
            "StoreManager config updated successfully",
            total_stores=len(self.stores),
        )
