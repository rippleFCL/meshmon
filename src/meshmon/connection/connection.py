import queue
import threading
from typing import Protocol

import structlog

from ..config.bus import ConfigBus, ConfigPreprocessor
from ..config.config import Config
from .grpc_types import Heartbeat, HeartbeatResponse, StoreUpdate
from .proto import PacketData


class ConnManConfigPreprocessor(ConfigPreprocessor[list[tuple[str, str]]]):
    def preprocess(self, config: Config | None) -> list[tuple[str, str]]:
        connections = []
        if config is None:
            return connections
        for network in config.networks.values():
            for node in network.node_config:
                connections.append((node.node_id, network.network_id))
        return connections


class ProtocolHandler(Protocol):
    def build_packet(
        self, data: StoreUpdate | Heartbeat | HeartbeatResponse
    ) -> PacketData | None: ...

    def handle_packet(self, request: PacketData, conn: "RawConnection") -> None: ...


class RawConnection:
    def __init__(self, protocol: ProtocolHandler):
        self.stream_writer: queue.Queue[PacketData] = queue.Queue()
        self.protocol = protocol
        self._closed = threading.Event()

    def handle_request(self, request: PacketData):
        if self._closed.is_set():
            return
        if self.protocol:
            self.protocol.handle_packet(request, self)

    def send_response(self, response: Heartbeat | HeartbeatResponse | StoreUpdate):
        if self._closed.is_set():
            return
        packet = self.protocol.build_packet(response)
        if packet:
            self.stream_writer.put(packet)

    def get_response(self, timeout: float | None = None) -> PacketData | None:
        try:
            return self.stream_writer.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self):
        self._closed.set()

    @property
    def is_closed(self):
        return self._closed.is_set()


class Connection:
    def __init__(
        self,
        dest_node_id: str,
        src_node_id: str,
        network: str,
    ):
        self.dest_node_id = dest_node_id
        self.src_node_id = src_node_id
        self.network = network
        self.connections: list[RawConnection] = []
        self.conn_selector = 0
        self.conn_lock = threading.Lock()

    def close(self):
        with self.conn_lock:
            for conn in self.connections:
                conn.close()
            self.connections = []

    @property
    def is_active(self) -> bool:
        return any(not conn.is_closed for conn in self.connections)

    def send_response(self, response: Heartbeat | HeartbeatResponse | StoreUpdate):
        with self.conn_lock:
            if len(self.connections) == 0:
                return
            self.conn_selector += 1
            self.conn_selector %= len(self.connections)
            self.connections[self.conn_selector].send_response(response)

    def add_raw_connection(self, raw_conn: RawConnection) -> None:
        with self.conn_lock:
            self.connections.append(raw_conn)

    def remove_raw_connection(self, raw_conn: RawConnection) -> None:
        if raw_conn in self.connections:
            with self.conn_lock:
                self.connections.remove(raw_conn)
                raw_conn.close()


class ConnectionManagerConfigPreprocessor(ConfigPreprocessor[set[tuple[str, str]]]):
    def preprocess(self, config: Config | None) -> set[tuple[str, str]]:
        connections = set()
        if config is None:
            return connections
        for network in config.networks.values():
            for node in network.node_config:
                if node.node_id == network.node_id:
                    continue
                connections.add((node.node_id, network.network_id))
        return connections


class ConnectionManager:
    def __init__(self, config_bus: ConfigBus):
        self.config_bus = config_bus
        watcher = config_bus.get_watcher(ConnectionManagerConfigPreprocessor())
        if watcher is None:
            raise ValueError("No initial config available for connection manager")
        watcher.subscribe(self.reload)
        self.watcher = watcher
        self.connections: dict[tuple[str, str], Connection] = {}
        self.logger = structlog.get_logger().bind(
            module="meshmon.connection.connection", component="ConnectionManager"
        )
        self.lock = threading.RLock()

    def get_connection(self, node_id: str, network_id: str) -> Connection | None:
        with self.lock:
            if (node_id, network_id) not in self.connections:
                return None
            return self.connections[(node_id, network_id)]

    def add_connection(
        self,
        dest_node_id: str,
        src_node_id: str,
        network_id: str,
    ) -> Connection:
        with self.lock:
            if (dest_node_id, network_id) not in self.connections:
                self.connections[(dest_node_id, network_id)] = Connection(
                    dest_node_id, src_node_id, network_id
                )
            return self.connections[(dest_node_id, network_id)]

    def remove_connection(self, node_id: str, network_id: str) -> None:
        with self.lock:
            if (node_id, network_id) in self.connections:
                conn = self.connections[(node_id, network_id)]
                conn.close()
                del self.connections[(node_id, network_id)]

    def __iter__(self):
        with self.lock:
            return iter(self.connections.values())

    def reload(self, config: set[tuple[str, str]]) -> None:
        self.logger.info(
            "Config reload triggered for ConnectionManager",
            new_connection_count=len(config),
            current_connection_count=len(self.connections),
        )
        with self.lock:
            to_remove = []
            for (node_id, network_id), conn in self.connections.items():
                if (node_id, network_id) not in config:
                    to_remove.append((node_id, network_id))
            for node_id, network_id in to_remove:
                self.logger.info(
                    "Removing obsolete connection",
                    node_id=node_id,
                    network_id=network_id,
                )
                self.remove_connection(node_id, network_id)
