import queue
import threading
from typing import TYPE_CHECKING, Iterator

import grpc
import structlog

from meshmon.config import NetworkConfig
from meshmon.connection.protocol_handler import PulseWaveProtocol

from .connection import ConnectionManager, RawConnection
from .proto import ConnectionInit, MeshMonServiceStub, ProtocolData

if TYPE_CHECKING:
    from .grpc_server import GrpcUpdateHandlerContainer

logger = structlog.stdlib.get_logger().bind(module="connection.grpc_client")


class GrpcClient:
    """gRPC client that uses ConnectionManager and RawConnection to manage streams."""

    def __init__(
        self,
        connection_manager: ConnectionManager,
        update_handlers: "GrpcUpdateHandlerContainer",
        config: dict[str, NetworkConfig],
        node_id: str,
    ):
        self.connection_manager = connection_manager
        self.node_id = node_id
        self.config = config
        self.update_handlers = update_handlers
        self.channels: dict[str, grpc.Channel] = {}
        self.stubs: dict[str, MeshMonServiceStub] = {}
        self.stream_threads: dict[str, threading.Thread] = {}
        self.request_queues: dict[str, queue.Queue] = {}
        self.stop_event = threading.Event()
        self._manager_thread = threading.Thread(
            target=self._connection_manager, daemon=True
        )
        self._manager_thread.start()

    def _normalize_address(self, url: str | None) -> str | None:
        if not url:
            return None
        if url.startswith("grpc://"):
            return url[7:]
        return url

    def _connection_manager(self):
        reconnect_interval = 5.0
        while not self.stop_event.is_set():
            try:
                # Remove dead threads to allow reconnect
                dead_keys = [
                    k for k, t in self.stream_threads.items() if not t.is_alive()
                ]
                for k in dead_keys:
                    self.stream_threads.pop(k, None)
                    self.channels.pop(k, None)
                    self.stubs.pop(k, None)
                    self.request_queues.pop(k, None)

                for network_id, network in self.config.items():
                    # Ensure connections to all configured peers
                    for node in network.node_config:
                        if node.node_id:
                            continue
                        address = self._normalize_address(node.url)
                        if not address:
                            continue
                        key = f"{network.network_id}:{node.node_id}"
                        t = self.stream_threads.get(key)
                        if t and not t.is_alive():
                            self.connect_to(network.network_id, node.node_id, address)
            except Exception:
                # swallow and retry later
                pass
            finally:
                self.stop_event.wait(reconnect_interval)

    def connect_to(self, network_id: str, node_id: str, address: str) -> bool:
        """Connect to a peer node, create a RawConnection, and register in ConnectionManager."""
        try:
            key = f"{network_id}:{node_id}"
            # Avoid duplicate connects
            existing = self.stream_threads.get(key)
            if existing and existing.is_alive():
                return True
            # Setup channel and stub
            channel = grpc.insecure_channel(
                address,
                options=[
                    ("grpc.keepalive_time_ms", 10000),
                    ("grpc.keepalive_timeout_ms", 5000),
                    ("grpc.keepalive_permit_without_calls", True),
                    ("grpc.http2.max_pings_without_data", 0),
                    ("grpc.http2.min_time_between_pings_ms", 10000),
                    ("grpc.http2.min_ping_interval_without_data_ms", 300000),
                ],
            )
            stub = MeshMonServiceStub(channel)

            # Per-peer request queue and raw connection
            response_q: "queue.Queue" = queue.Queue()
            raw_conn = RawConnection(response_q)

            # Register raw connection with manager's Connection
            connection = self.connection_manager.get_connection(node_id, network_id)
            if connection is None:
                handler = self.update_handlers.get_handler(network_id)
                protocol_handler = PulseWaveProtocol(handler)
                connection = self.connection_manager.add_connection(
                    node_id, network_id, protocol_handler
                )
            connection.add_raw_connection(raw_conn)

            # Start streaming thread
            def request_generator() -> Iterator[ProtocolData]:
                # Initial ConnectionInit
                yield ProtocolData(
                    connection_init=ConnectionInit(
                        node_id=node_id, network_id=network_id
                    )
                )
                while not self.stop_event.is_set():
                    try:
                        item = raw_conn.get_response(0.5)
                        if item is not None:
                            yield item
                        else:
                            connection.remove_raw_connection(raw_conn)
                    except queue.Empty:
                        pass

            def stream_worker():
                try:
                    response_iterator = stub.StreamUpdates(request_generator())
                    for resp in response_iterator:
                        if resp is None:
                            break
                        # Forward responses into the RawConnection's response queue
                        raw_conn.handle_request(resp)
                except Exception as e:
                    logger.error("Client stream error", node_id=node_id, error=str(e))
                finally:
                    # Cleanup
                    connection.remove_raw_connection(raw_conn)

            t = threading.Thread(target=stream_worker, daemon=True)
            t.start()

            # Save references
            self.channels[key] = channel
            self.stubs[key] = stub
            self.stream_threads[key] = t

            return True
        except Exception as e:
            logger.error("Failed to connect to node", node_id=node_id, error=str(e))
            return False

    def write(self, network_id: str, node_id: str, request: ProtocolData) -> bool:
        """Queue a request to a specific peer stream."""
        key = f"{network_id}:{node_id}"
        q = self.request_queues.get(key)
        if not q:
            return False
        try:
            q.put_nowait(request)
            return True
        except queue.Full:
            return False

    def stop(self):
        self.stop_event.set()
        if self._manager_thread.is_alive():
            self._manager_thread.join(timeout=2.0)
        # Stop threads
        for t in self.stream_threads.values():
            if t.is_alive():
                t.join(timeout=2.0)
        # Close channels
        for ch in self.channels.values():
            try:
                ch.close()
            except Exception:
                pass
        self.channels.clear()
        self.stubs.clear()
        self.stream_threads.clear()
        self.request_queues.clear()
