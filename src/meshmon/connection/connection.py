import queue
import threading
from typing import Callable, Protocol

from .proto import PacketData
from .grpc_types import Heartbeat, HeartbeatResponse, StoreUpdate


class ProtocolHandler(Protocol):
    def build_packet(self, data: StoreUpdate | Heartbeat | HeartbeatResponse) -> PacketData | None: ...

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


class ConnectionManager:
    def __init__(self):
        self.connections: dict[tuple[str, str], Connection] = {}
        self.lock = threading.Lock()

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
                self.connections[(dest_node_id, network_id)] = Connection(dest_node_id, src_node_id, network_id)
            return self.connections[(dest_node_id, network_id)]

    def __iter__(self):
        with self.lock:
            return iter(self.connections.values())
