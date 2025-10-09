import datetime
import threading
import time

from meshmon.config import NetworkConfigLoader

from ..distrostore import StoreManager
from ..dstypes import DSNodeStatus, DSPingData
from .connection import ConnectionManager
from .proto import ProtocolData, StoreHeartbeat


class HeartbeatController:
    def __init__(
        self,
        connection_manager: ConnectionManager,
        config: NetworkConfigLoader,
        store: StoreManager,
    ):
        self.connection_manager = connection_manager
        self.config = config
        self.store_manager = store
        self.stop_event = threading.Event()
        self.last_sent: dict[tuple[str, str], float] = {}

    def get_node_config(self, network: str, node_id: str):
        if network not in self.config.networks:
            return None
        for node in self.config.networks[network].node_config:
            if node.node_id == node_id:
                return node
        return None

    def needs_heartbeat(self, network: str, dest_node_id: str) -> bool:
        last_sent = self.last_sent.get((network, dest_node_id), 0)
        if network not in self.config.networks:
            return False
        nodes_config = self.get_node_config(network, dest_node_id)
        if not nodes_config:
            return False
        return time.time() - last_sent > nodes_config.poll_rate

    def set_ping_status(self):
        for network_id, store in self.store_manager.stores.items():
            node_ctx = store.get_context("ping_data", DSPingData)
            for node_id, ping_data in node_ctx:
                nodes_config = self.get_node_config(network_id, node_id)
                if not nodes_config:
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
                            status=DSNodeStatus.OFFLINE, req_time_rtt=-1, date=now
                        ),
                    )

    def heartbeat_loop(self) -> None:
        while True:
            for connection in self.connection_manager:
                if self.needs_heartbeat(connection.network, connection.dest_node_id):
                    connection.send_response(
                        ProtocolData(
                            heartbeat=StoreHeartbeat(
                                node_id=connection.src_node_id,
                                network_id=connection.network,
                                timestamp=int(time.time_ns()),
                            )
                        )
                    )
                    self.last_sent[(connection.network, connection.dest_node_id)] = (
                        time.time()
                    )
            self.set_ping_status()
            if self.stop_event.wait(2):
                break

    def start(self) -> None:
        self.thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join()
