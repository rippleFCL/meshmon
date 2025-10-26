import queue
import threading
import time
from typing import Literal, Protocol

import structlog

# Import metrics
from meshmon.prom_export import (
    cleanup_connection_metrics,
    cleanup_raw_connection_metrics,
    record_connection_closed,
    record_connection_established,
    record_queue_depth,
)

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
    def __init__(
        self,
        protocol: ProtocolHandler,
        network_id: str,
        dest_node_id: str,
        initiator: Literal["local", "remote"],
    ):
        self.stream_writer: queue.Queue[PacketData] = queue.Queue()
        self.stream_reader: queue.Queue[PacketData] = queue.Queue()
        self.protocol = protocol
        self._closed = threading.Event()
        self.network_id = network_id
        self.dest_node_id = dest_node_id
        self.initiator = initiator

        # Timing metrics for link utilization
        self.start_time = time.perf_counter_ns()
        self.total_wait_time = 0.0  # Time spent waiting for data
        self.total_processing_time = 0.0  # Time spent processing data
        self.processing_start = time.perf_counter_ns()
        self.processing_end = time.perf_counter_ns()
        self.wait_start = time.perf_counter_ns()
        self.wait_end = time.perf_counter_ns()
        self.last_scrape = time.perf_counter_ns()
        self._timing_lock = threading.Lock()
        self._handler_thread = threading.Thread(target=self.handle_loop)
        self._handler_thread.start()
        record_connection_established(
            network_id=self.network_id,
            node_id=self.dest_node_id,
            initiator=self.initiator,
        )

    def handle_loop(self):
        while not self._closed.is_set():
            self.processing_start = time.perf_counter_ns()
            try:
                packet = self.stream_reader.get(timeout=1.0)
            except queue.Empty:
                continue
            finally:
                self.processing_end = time.perf_counter_ns()
                # Record processing time
                with self._timing_lock:
                    if self.last_scrape > self.processing_start:
                        self.processing_start = self.last_scrape
                    self.total_processing_time += (
                        self.processing_end - self.processing_start
                    )

            if self.protocol:
                self.protocol.handle_packet(packet, self)

    def handle_request(self, request: PacketData):
        if self._closed.is_set():
            return
        if self.protocol:
            record_queue_depth(
                network_id=self.network_id,
                node_id=self.dest_node_id,
                depth=self.stream_reader.qsize(),
                direction="inbound",
                initiator=self.initiator,
            )
            self.stream_reader.put(request)

    def send_response(self, response: Heartbeat | HeartbeatResponse | StoreUpdate):
        if self._closed.is_set():
            return
        packet = self.protocol.build_packet(response)
        if packet:
            # Update queue depth metric
            record_queue_depth(
                network_id=self.network_id,
                node_id=self.dest_node_id,
                depth=self.stream_writer.qsize(),
                direction="outbound",
                initiator=self.initiator,
            )
            self.stream_writer.put(packet)

    def get_response(self, timeout: float | None = None) -> PacketData | None:
        self.wait_start = time.perf_counter_ns()
        try:
            result = self.stream_writer.get(timeout=timeout)
            self.wait_end = time.perf_counter_ns()
            return result
        except queue.Empty:
            return None
        finally:
            self.wait_end = time.perf_counter_ns()
            # Still count timeout as wait time
            with self._timing_lock:
                if self.last_scrape > self.wait_start:
                    self.wait_start = self.last_scrape
                self.total_wait_time += self.wait_end - self.wait_start

    def close(self):
        if not self._closed.is_set():
            self._closed.set()
            record_connection_closed(
                network_id=self.network_id,
                node_id=self.dest_node_id,
                initiator=self.initiator,
                duration_seconds=(time.perf_counter_ns() - self.start_time)
                / 1_000_000_000,
            )
            # Clean up metrics for this raw connection
            cleanup_raw_connection_metrics(
                network_id=self.network_id,
                node_id=self.dest_node_id,
                initiator=self.initiator,
            )

    @property
    def is_closed(self):
        return self._closed.is_set()

    def get_timing_stats(self) -> tuple[float, float, float]:
        """Returns (total_wait_time, total_processing_time) in seconds."""
        with self._timing_lock:
            # Update wait time up to now if we're currently idle
            current_time = time.perf_counter_ns()

            if self.wait_start > self.wait_end:  # Currently waiting
                self.total_wait_time += current_time - self.wait_start
            if self.processing_start > self.processing_end:  # Currently processing
                self.total_processing_time += current_time - self.processing_start
            elapsed_time = current_time - self.last_scrape
            self.last_scrape = current_time

            data = (self.total_wait_time, self.total_processing_time, elapsed_time)
            self.total_wait_time = 0.0
            self.total_processing_time = 0.0
            return data


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


class ConnectionManagerConfigPreprocessor(
    ConfigPreprocessor[set[tuple[str, str, str]]]
):
    def preprocess(self, config: Config | None) -> set[tuple[str, str, str]]:
        connections: set[tuple[str, str, str]] = set()
        if config is None:
            return connections
        for network_id, network in config.networks.items():
            # Build an index for peer lookup
            peers = {n.node_id: n for n in network.node_config}
            self_id = network.node_id
            for dest_id, dest in peers.items():
                if dest_id == self_id:
                    continue
                src = peers.get(self_id)
                if src is None:
                    continue
                # Check if src can dial dest
                src_can_dial_dest = False
                if dest.url:
                    if self_id not in dest.block and (
                        not dest.allow or self_id in dest.allow
                    ):
                        src_can_dial_dest = True

                # Check if dest can dial src (i.e., reverse direction permitted)
                dest_can_dial_src = False
                if src.url:
                    if dest_id not in src.block and (
                        not src.allow or dest_id in src.allow
                    ):
                        dest_can_dial_src = True

                if src_can_dial_dest or dest_can_dial_src:
                    connections.add((dest_id, network_id, self_id))
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
        # Initialize connections based on current config
        self.reload(self.watcher.current_config)

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
                # Clean up all connection metrics for this node
                cleanup_connection_metrics(network_id, node_id)
                del self.connections[(node_id, network_id)]

    def __iter__(self):
        with self.lock:
            return iter(self.connections.values())

    def reload(self, config: set[tuple[str, str, str]]) -> None:
        self.logger.info(
            "Config reload triggered for ConnectionManager",
            new_connection_count=len(config),
            current_connection_count=len(self.connections),
        )
        with self.lock:
            # Remove connections no longer in config
            to_remove: list[tuple[str, str]] = []
            desired_pairs = {(dest, net) for (dest, net, _src) in config}
            for (node_id, network_id), conn in self.connections.items():
                if (node_id, network_id) not in desired_pairs:
                    to_remove.append((node_id, network_id))
            for node_id, network_id in to_remove:
                self.logger.info(
                    "Removing obsolete connection",
                    node_id=node_id,
                    network_id=network_id,
                )
                self.remove_connection(node_id, network_id)
            # Add any new connections
            for dest_node_id, network_id, src_node_id in config:
                if (dest_node_id, network_id) not in self.connections:
                    self.logger.info(
                        "Adding new connection",
                        node_id=dest_node_id,
                        network_id=network_id,
                        initiator=src_node_id,
                    )
                    self.add_connection(dest_node_id, src_node_id, network_id)
