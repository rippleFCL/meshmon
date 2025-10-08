import threading
from concurrent import futures
from typing import TYPE_CHECKING, Iterator

import grpc
import structlog

from meshmon.config import NetworkConfigLoader
from meshmon.connection.protocol_handler import PulseWaveProtocol
from meshmon.connection.update_handler import GrpcUpdateHandler

from .connection import ConnectionManager, RawConnection
from .grpc_client import GrpcClient
from .proto import (
    ConnectionAck,
    Error,
    MeshMonServiceServicer,
    ProtocolData,
    StoreHeartbeatAck,
    add_MeshMonServiceServicer_to_server,
)

if TYPE_CHECKING:
    pass


class GrpcUpdateHandlerContainer:
    def __init__(self, connection_manager: ConnectionManager):
        self.handlers: dict[str, GrpcUpdateHandler] = {}
        self.lock = threading.Lock()
        self.connection_manager = connection_manager

    def get_handler(self, network_id: str) -> GrpcUpdateHandler:
        with self.lock:
            if network_id not in self.handlers:
                self.handlers[network_id] = GrpcUpdateHandler(
                    network_id, self.connection_manager
                )
            return self.handlers[network_id]


class MeshMonServicer(MeshMonServiceServicer):
    """gRPC service implementation for MeshMon."""

    def __init__(
        self,
        connection_manager: ConnectionManager,
        update_handlers: GrpcUpdateHandlerContainer,
        config: NetworkConfigLoader,
    ):
        self.config = config
        self.logger = structlog.stdlib.get_logger().bind(
            module="connection.grpc_server", component="MeshMonServicer"
        )
        self.connection_manager = connection_manager
        self.conn_lock = threading.Lock()
        self.update_handlers = update_handlers

    def request_handler(
        self,
        request_iterator: Iterator[ProtocolData],
        raw_conn: RawConnection,
        src_node_id: str,
        network_id: str,
    ):
        """Handle incoming requests in a separate thread."""
        try:
            for request in request_iterator:
                if request is None:
                    break
                if raw_conn.is_closed:
                    break
                if request.HasField("heartbeat"):
                    self.logger.debug(
                        "Received heartbeat",
                        from_node=request.heartbeat.node_id,
                        network_id=request.heartbeat.network_id,
                    )
                    raw_conn.send_response(
                        ProtocolData(
                            heartbeat_ack=StoreHeartbeatAck(
                                node_id=src_node_id,
                                network_id=network_id,
                                timestamp=request.heartbeat.timestamp,
                                success=True,
                            )
                        )
                    )
                else:
                    raw_conn.handle_request(request)

        except Exception as e:
            self.logger.error(
                "Request handler error for", node_id=src_node_id, error=str(e)
            )
        finally:
            raw_conn.close()

    def StreamUpdates(
        self, request_iterator: Iterator[ProtocolData], context: grpc.ServicerContext
    ) -> Iterator[ProtocolData]:
        """Handle truly bidirectional streaming for mesh updates."""
        import queue

        initial_packet = next(request_iterator, None)
        if initial_packet is None or not initial_packet.HasField("connection_init"):
            self.logger.warning(
                "Invalid first packet during GRPC stream initialization"
            )
            yield ProtocolData(
                error=Error(
                    code="INVALID_INITIAL_PACKET",
                    message="First packet must be connection_init",
                    details="",
                )
            )
            return
        yield ProtocolData(
            connection_ack=ConnectionAck(message="Connection established")
        )
        connection_init = initial_packet.connection_init
        current_node_id = self.config.networks[connection_init.network_id].node_id
        response_queue: "queue.Queue[ProtocolData]" = queue.Queue()
        raw_conn = RawConnection(response_queue)
        with self.conn_lock:
            connection = self.connection_manager.get_connection(
                connection_init.node_id, connection_init.network_id
            )
            if connection is None:
                self.logger.info(
                    "Creating new connection for peer",
                    server_node_id=current_node_id,
                    client_node_id=connection_init.node_id,
                    network_id=connection_init.network_id,
                    peer=context.peer(),
                )
                handler = self.update_handlers.get_handler(connection_init.network_id)
                protocol_handler = PulseWaveProtocol(handler)
                connection = self.connection_manager.add_connection(
                    connection_init.node_id,
                    current_node_id,
                    connection_init.network_id,
                    protocol_handler,
                )
            connection.add_raw_connection(raw_conn)

        request_thread = threading.Thread(
            target=self.request_handler,
            args=(
                request_iterator,
                raw_conn,
                current_node_id,
                connection_init.network_id,
            ),
            daemon=True,
        )
        request_thread.start()

        self.logger.info(
            "gRPC Bidirectional stream connection from client established",
            client_node_id=connection.dest_node_id,
            peer=context.peer(),
            server_node_id=current_node_id,
            network_id=connection_init.network_id,
        )

        try:
            # Response  loop - yields responses as they become available
            while not raw_conn.is_closed:
                try:
                    # Wait for responses with timeout to check stop_event periodically
                    response = raw_conn.get_response(0.5)
                    if response is None:
                        continue
                    yield response

                except Exception as e:
                    self.logger.error(
                        "Error sending response ",
                        node_id=connection_init.node_id,
                        network_id=connection_init.network_id,
                        peer=context.peer(),
                        error=str(e),
                    )
                    break

        except Exception as e:
            self.logger.error(
                "Stream error for ",
                node_id=connection_init.node_id,
                network_id=connection_init.network_id,
                peer=context.peer(),
                error=str(e),
            )
        finally:
            connection.remove_raw_connection(raw_conn)
            # Wait for request thread to finish
            if request_thread.is_alive():
                request_thread.join(timeout=2.0)

            self.logger.info(
                "gRPC Bidirectional stream connection closed",
                node_id=connection.dest_node_id,
                network_id=connection_init.network_id,
                peer=context.peer(),
            )


class GrpcServer:
    """gRPC server for handling mesh connections."""

    def __init__(self, netconfig: NetworkConfigLoader):
        self.config = netconfig
        self.logger = structlog.stdlib.get_logger().bind(
            module="connection.grpc_server", component="server"
        )
        self.server = None
        self.connection_manager = ConnectionManager()
        self.update_handlers = GrpcUpdateHandlerContainer(self.connection_manager)
        self._client = None  # Embedded client instance

    def get_handler(self, network_id: str) -> GrpcUpdateHandler:
        return self.update_handlers.get_handler(network_id)

    def start(self, port: int = 42069) -> bool:
        """Start the gRPC server."""
        try:
            # Create server with thread pool
            self.server = grpc.server(
                futures.ThreadPoolExecutor(max_workers=20),
                options=[
                    ("grpc.keepalive_time_ms", 10000),
                    ("grpc.keepalive_timeout_ms", 5000),
                    ("grpc.keepalive_permit_without_calls", True),
                    ("grpc.http2.max_pings_without_data", 0),
                    ("grpc.http2.min_time_between_pings_ms", 10000),
                    ("grpc.http2.min_ping_interval_without_data_ms", 300000),
                ],
            )

            # Add the servicer
            servicer = MeshMonServicer(
                self.connection_manager, self.update_handlers, self.config
            )
            add_MeshMonServiceServicer_to_server(servicer, self.server)

            # Add insecure port (TODO: add TLS support)
            listen_ip6addr = f"[::]:{port}"
            self.server.add_insecure_port(listen_ip6addr)
            listen_ip4addr = f"0.0.0.0:{port}"
            self.server.add_insecure_port(listen_ip4addr)

            # Start server
            self.server.start()
            self.logger.info(
                "gRPC server started",
                listen_addr_v4=listen_ip4addr,
                listen_addr_v6=listen_ip6addr,
            )

            # Start an outgoing client to connect to peers
            try:
                self._client = GrpcClient(
                    self.connection_manager,
                    self.update_handlers,
                    self.config,
                )
            except Exception as e:
                self.logger.error("Failed to start embedded gRPC client", error=str(e))

            return True

        except Exception as e:
            self.logger.error("Failed to start gRPC server", error=str(e))
            return False

    def stop(self, grace_period: float = 5.0) -> None:
        """Stop the gRPC server."""
        if self.server:
            self.logger.info("Stopping gRPC server...")

            # Stop server gracefully
            self.server.stop(grace_period)

            # Stop embedded client
            try:
                if self._client:
                    self._client.stop()
            except Exception as e:
                self.logger.debug("Error stopping embedded client", error=str(e))
            finally:
                self._client = None

            self.logger.info("gRPC server stopped")

    def wait_for_termination(self) -> None:
        """Wait for the server to terminate."""
        if self.server:
            self.server.wait_for_termination()
