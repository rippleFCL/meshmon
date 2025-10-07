import queue
import threading
from typing import TYPE_CHECKING, Iterator

import grpc
import structlog

from meshmon.config import NetworkConfigLoader
from meshmon.connection.protocol_handler import PulseWaveProtocol

from .connection import ConnectionManager, RawConnection
from .proto import ConnectionInit, Error, MeshMonServiceStub, ProtocolData

if TYPE_CHECKING:
    from .grpc_server import GrpcUpdateHandlerContainer


class GrpcClient:
    """gRPC client that uses ConnectionManager and RawConnection to manage streams."""

    def __init__(
        self,
        connection_manager: ConnectionManager,
        update_handlers: "GrpcUpdateHandlerContainer",
        config: NetworkConfigLoader,
    ):
        self.logger = structlog.stdlib.get_logger().bind(
            module="connection.grpc_client"
        )
        self.connection_manager = connection_manager
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
        if url.startswith("http://"):
            return url[7:]
        if url.startswith("https://"):
            url = url[8:]
        return url

    def _connection_manager(self):
        reconnect_interval = 10
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

                for network in self.config.networks.values():
                    # Ensure connections to all configured peers
                    for node in network.node_config:
                        if node.node_id == network.node_id:
                            continue
                        address = self._normalize_address(node.url)
                        if not address:
                            continue
                        key = f"{network.network_id}:{node.node_id}"
                        t = self.stream_threads.get(key)
                        if t is None or not t.is_alive():
                            self.connect_to(network.network_id, node.node_id, address)
            except Exception as e:
                self.logger.exception("Error in connection manager loop", error=str(e))
            finally:
                self.stop_event.wait(reconnect_interval)

    def connect_to(self, network_id: str, node_id: str, address: str) -> bool:
        """Connect to a peer node, create a RawConnection, and register in ConnectionManager."""
        try:
            current_node_id = self.config.networks[network_id].node_id

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
                    ("grpc.http2.max_pings_without_data", 10),
                    ("grpc.http2.min_time_between_pings_ms", 10000),
                    ("grpc.http2.min_ping_interval_without_data_ms", 300000),
                ],
            )
            stub = MeshMonServiceStub(channel)

            # Per-peer request queue (for outgoing messages) and raw connection (for incoming)
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
                        node_id=current_node_id, network_id=network_id
                    )
                )
                while not self.stop_event.is_set():
                    try:
                        # Read from the request queue (where write() puts messages)
                        item = raw_conn.get_response(timeout=0.5)
                        if item is not None:
                            yield item
                    except queue.Empty:
                        pass

            def stream_worker():
                print("wehha")
                try:
                    self.logger.info(
                        "Starting gRPC stream", node_id=node_id, address=address
                    )
                    response_iterator = stub.StreamUpdates(request_generator())
                    initial_packet = next(response_iterator, None)
                    if initial_packet is None or not initial_packet.HasField(
                        "connection_ack"
                    ):
                        self.logger.warning(
                            "Invalid first packet during GRPC stream initialization"
                        )
                        raw_conn.send_response(
                            ProtocolData(
                                error=Error(
                                    code="INVALID_INITIAL_PACKET",
                                    message="First packet must be connection_ack",
                                    details="",
                                )
                            )
                        )
                    else:
                        self.logger.info(
                            "gRPC Bidirectional stream established",
                            node_id=node_id,
                            address=address,
                        )
                        for resp in response_iterator:
                            if resp is None:
                                break
                            # Forward responses into the RawConnection's response queue
                            raw_conn.handle_request(resp)
                except grpc.RpcError as e:
                    # Connection errors are expected during startup/reconnect
                    if e.code() == grpc.StatusCode.UNAVAILABLE:  # type: ignore
                        self.logger.debug(
                            "Connection unavailable", node_id=node_id, address=address
                        )
                    else:
                        self.logger.error(
                            "gRPC stream error",
                            node_id=node_id,
                            error=str(e),
                            code=e.code(),  # type: ignore
                        )
                except Exception as e:
                    self.logger.error(
                        "Client stream error", node_id=node_id, error=str(e)
                    )
                finally:
                    self.logger.info("gRPC stream ending", node_id=node_id)
                    connection.remove_raw_connection(raw_conn)

            t = threading.Thread(target=stream_worker, daemon=True)
            t.start()

            # Save references
            self.channels[key] = channel
            self.stubs[key] = stub
            self.stream_threads[key] = t
            self.request_queues[key] = response_q

            return True
        except grpc.RpcError as e:
            self.logger.debug(
                "gRPC connection failed", node_id=node_id, address=address, error=str(e)
            )
            return False
        except Exception as e:
            self.logger.error(
                "Failed to connect to node", node_id=node_id, error=str(e)
            )
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
