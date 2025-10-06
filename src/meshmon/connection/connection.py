import queue
import threading
from typing import Callable, Protocol

from .proto.meshmon_pb2 import ProtocolData


class RawConnection:
    def __init__(self, stream_writer: queue.Queue):
        self.stream_writer = stream_writer
        self.handler = None
        self._closed = threading.Event()

    def set_handler(self, handler: Callable[[ProtocolData], None]):
        self.handler = handler

    def handle_request(self, request: ProtocolData):
        if self._closed.is_set():
            return
        if self.handler:
            self.handler(request)

    def send_response(self, response: ProtocolData):
        if self._closed.is_set():
            return
        self.stream_writer.put(response)

    def get_response(self, timeout: float | None = None) -> ProtocolData | None:
        try:
            return self.stream_writer.get(timeout=timeout)
        except queue.Empty:
            return None

    def close(self):
        self._closed.set()

    @property
    def is_closed(self):
        return self._closed.is_set()


class ProtocolHandler(Protocol):
    def bind_connection(self, connection: "Connection") -> None: ...

    def handle_packet(self, request: ProtocolData) -> None: ...


class Connection:
    def __init__(self, node_id: str, handler: ProtocolHandler):
        self.node_id = node_id
        self.connections = []
        self.protocol = handler
        self.protocol.bind_connection(self)

    @property
    def is_active(self) -> bool:
        return any(not conn.is_closed for conn in self.connections)

    def send_response(self, response: ProtocolData):
        for conn in self.connections:
            if not conn.is_closed:
                conn.send_response(response)

    def add_raw_connection(self, raw_conn: RawConnection) -> None:
        raw_conn.set_handler(self.connection_handler)
        self.connections.append(raw_conn)

    def remove_raw_connection(self, raw_conn: RawConnection) -> None:
        if raw_conn in self.connections:
            self.connections.remove(raw_conn)
            raw_conn.close()

    def connection_handler(self, request: ProtocolData):
        # Process the request and prepare a response
        self.protocol.handle_packet(request)


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
        self, node_id: str, network_id: str, handler: ProtocolHandler
    ) -> Connection:
        with self.lock:
            if (node_id, network_id) not in self.connections:
                self.connections[(node_id, network_id)] = Connection(node_id, handler)
            return self.connections[(node_id, network_id)]
