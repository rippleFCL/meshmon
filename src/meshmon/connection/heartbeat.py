import datetime
import threading
import time
from dataclasses import dataclass

import structlog

from ..config.bus import ConfigBus, ConfigPreprocessor
from ..config.config import Config, LoadedNetworkNodeInfo
from ..distrostore import StoreManager
from ..dstypes import DSNodeStatus, DSPingData
from .connection import ConnectionManager
from .grpc_types import Heartbeat


@dataclass
class HeartbeatConfig:
    """Configuration for heartbeat controller"""

    node_configs: dict[
        tuple[str, str], LoadedNetworkNodeInfo
    ]  # (network_id, node_id) -> NetworkNodeInfo


class HeartbeatConfigPreprocessor(ConfigPreprocessor[HeartbeatConfig]):
    def preprocess(self, config: Config | None) -> HeartbeatConfig:
        node_configs = {}
        if config is None:
            return HeartbeatConfig(node_configs=node_configs)
        for network_id, network in config.networks.items():
            for node in network.node_config:
                if node.node_id == network.node_id:
                    continue
                if network.node_id in node.block or (
                    node.allow and network.node_id in node.allow
                ):
                    continue
                node_configs[(network_id, node.node_id)] = node

        return HeartbeatConfig(node_configs=node_configs)


class HeartbeatController:
    def __init__(
        self,
        connection_manager: ConnectionManager,
        config_bus: ConfigBus,
        store: StoreManager,
    ):
        self.logger = structlog.get_logger().bind(
            module="meshmon.connection.heartbeat",
            component="HeartbeatController",
        )
        self.connection_manager = connection_manager
        watcher = config_bus.get_watcher(HeartbeatConfigPreprocessor())
        if watcher is None:
            raise ValueError("No initial config available for heartbeat controller")
        self.config_watcher = watcher
        self.config = watcher.current_config
        watcher.subscribe(self.reload)
        self.store_manager = store
        self.stop_event = threading.Event()
        self.last_sent: dict[tuple[str, str], float] = {}

    def get_node_config(self, network: str, node_id: str):
        return self.config.node_configs.get((network, node_id))

    def needs_heartbeat(self, network: str, dest_node_id: str) -> bool:
        last_sent = self.last_sent.get((network, dest_node_id), 0)
        nodes_config = self.get_node_config(network, dest_node_id)
        if not nodes_config:
            return False
        return time.time() - last_sent > nodes_config.poll_rate

    def filter_config(self, network_id: str) -> list[str]:
        filtered_configs = [
            value
            for net_id, value in self.config.node_configs.keys()
            if net_id == network_id
        ]
        return filtered_configs

    def set_ping_status(self):
        for network_id, store in self.store_manager.stores.items():
            node_ctx = store.get_context("ping_data", DSPingData)
            alive_connections = [conn.dest_node_id for conn in self.connection_manager]
            for node_id in alive_connections:
                if node_id not in node_ctx:
                    now = datetime.datetime.now(tz=datetime.timezone.utc)
                    node_ctx.set(
                        node_id,
                        DSPingData(
                            status=DSNodeStatus.UNKNOWN, req_time_rtt=-1, date=now
                        ),
                    )
            for node_id, ping_data in node_ctx:
                nodes_config = self.get_node_config(network_id, node_id)
                if not nodes_config or node_id not in alive_connections:
                    uid = (network_id, node_id)
                    if uid in self.last_sent:
                        del self.last_sent[uid]
                    node_ctx.delete(node_id)
                    continue

                now = datetime.datetime.now(tz=datetime.timezone.utc)
                if (
                    (
                        datetime.datetime.now(tz=datetime.timezone.utc) - ping_data.date
                    ).total_seconds()
                    > nodes_config.poll_rate * nodes_config.retry
                    and ping_data.status != DSNodeStatus.OFFLINE
                ):
                    node_ctx.set(
                        node_id,
                        DSPingData(
                            status=DSNodeStatus.OFFLINE,
                            req_time_rtt=-1,
                            date=now,
                        ),
                    )

    def heartbeat_loop(self) -> None:
        while True:
            for connection in self.connection_manager:
                if self.needs_heartbeat(connection.network, connection.dest_node_id):
                    connection.send_response(Heartbeat(node_time=time.time_ns()))
                    self.last_sent[(connection.network, connection.dest_node_id)] = (
                        time.time()
                    )
            self.set_ping_status()
            if self.stop_event.wait(2):
                break

    def start(self) -> None:
        self.thread = threading.Thread(
            target=self.heartbeat_loop, name="heartbeat-controller"
        )
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join()

    def reload(self, new_config: HeartbeatConfig) -> None:
        self.logger.info(
            "Config reload triggered for HeartbeatController",
            new_node_count=len(new_config.node_configs),
            old_node_count=len(self.config.node_configs),
        )
        nodes = len(self.config.node_configs)
        self.config = new_config
        removed_count = nodes - len(self.config.node_configs)

        self.logger.debug(
            "HeartbeatController config updated successfully",
            removed_entries=removed_count,
        )
