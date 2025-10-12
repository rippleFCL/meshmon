import os
import threading
from concurrent import futures
from typing import TYPE_CHECKING, Iterator

import grpc
import structlog
from pydantic import ValidationError

from meshmon.config import NetworkConfigLoader
from meshmon.connection.protocol_handler import PulseWaveProtocol
from meshmon.connection.update_handler import GrpcUpdateHandler
from meshmon.pulsewave.crypto import Verifier
from meshmon.pulsewave.data import SignedBlockData

from .connection import ConnectionManager, RawConnection
from .grpc_client import GrpcClientManager
from .grpc_types import Validator
from .proto import (
    ConnectionValidation,
    MeshMonServiceServicer,
    ProtocolData,
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
        verifier: Verifier,
    ):
        """Handle incoming requests in a separate thread."""
        try:
            for request in request_iterator:
                if request is None:
                    break
                if raw_conn.is_closed:
                    break
                if request.HasField("packet_data"):
                    raw_conn.handle_request(request.packet_data)
                else:
                    self.logger.warning(
                        "Received unknown request type, ignoring",
                        node_id=verifier.node_id,
                    )

        except Exception as e:
            self.logger.error(
                "Request handler error for", node_id=verifier.node_id, error=str(e)
            )
        finally:
            raw_conn.close()

    def StreamUpdates(
        self, request_iterator: Iterator[ProtocolData], context: grpc.ServicerContext
    ) -> Iterator[ProtocolData]:
        """Handle truly bidirectional streaming for mesh updates."""
        nonce = os.urandom(256).hex()
        context.send_initial_metadata((("server_nonce", nonce),))
        client_nonce = dict(context.invocation_metadata()).get("client_nonce", "")
        if not client_nonce:
            context.abort(
                grpc.StatusCode.UNAUTHENTICATED, "Missing client_nonce in metadata"
            )
            return

        initial_packet = next(request_iterator, None)
        if initial_packet is None or not initial_packet.HasField(
            "connection_validation"
        ):
            self.logger.warning(
                "Invalid first packet during GRPC stream initialization"
            )
            context.abort(
                grpc.StatusCode.UNAUTHENTICATED,
                "Invalid first packet, expected ConnectionValidation",
            )
            return
        try:
            conn_init_sbd = SignedBlockData.model_validate_json(
                initial_packet.connection_validation.validator
            )
            client_validator = Validator.model_validate(conn_init_sbd.data)
        except ValidationError as e:
            self.logger.warning(
                "Failed to parse ConnectionValidation during gRPC stream initialization",
                error=str(e),
            )
            context.abort(
                grpc.StatusCode.UNAUTHENTICATED, "Invalid ConnectionValidation format"
            )
            return
        try:
            verifier = self.config.networks[client_validator.network_id].get_verifier(
                client_validator.node_id
            )
            if not verifier:
                self.logger.warning(
                    "No verifier found for node during gRPC connection",
                    node_id=client_validator.node_id,
                    network_id=client_validator.network_id,
                    peer=context.peer(),
                )
                context.abort(
                    grpc.StatusCode.UNAUTHENTICATED, "Unknown node_id or network_id"
                )
                return
            if (
                not conn_init_sbd.verify(verifier, "validator", "validator")
                or client_validator.server_nonce != nonce
                or client_validator.client_nonce != client_nonce
            ):
                self.logger.warning(
                    "Client failed server challenge",
                    node_id=client_validator.node_id,
                    network_id=client_validator.network_id,
                    peer=context.peer(),
                )
                context.abort(
                    grpc.StatusCode.UNAUTHENTICATED, "Client failed server challenge"
                )
                return
            server_node_id = self.config.networks[client_validator.network_id].node_id
            signer = self.config.networks[
                client_validator.network_id
            ].key_mapping.signer
            server_validator = Validator(
                server_nonce=nonce,
                client_nonce=client_validator.client_nonce,
                node_id=server_node_id,
                network_id=client_validator.network_id,
            )
            validator = SignedBlockData.new(
                signer, server_validator, "validator", "validator"
            )
            yield ProtocolData(
                connection_validation=ConnectionValidation(
                    validator=validator.model_dump_json()
                )
            )
        except Exception as e:
            self.logger.error(
                "Error during gRPC stream initialization",
                node_id=client_validator.node_id,
                network_id=client_validator.network_id,
                peer=context.peer(),
                error=str(e),
            )
            context.abort(
                grpc.StatusCode.UNAUTHENTICATED, "Error during authentication"
            )
            return
        network_id = client_validator.network_id
        client_node_id = client_validator.node_id
        # If we reach here, the connection is authenticated
        with self.conn_lock:
            connection = self.connection_manager.get_connection(
                client_node_id, network_id
            )
            if connection is None:
                self.logger.info(
                    "Creating new connection for peer",
                    server_node_id=server_node_id,
                    client_node_id=client_node_id,
                    network_id=network_id,
                    peer=context.peer(),
                )
                connection = self.connection_manager.add_connection(
                    client_node_id,
                    server_node_id,
                    network_id,
                )
            handler = self.update_handlers.get_handler(network_id)
            protocol_handler = PulseWaveProtocol(
                handler,
                client_validator,
                server_validator,
                signer,
                verifier,
                conn_init_sbd,
            )
            raw_conn = RawConnection(protocol_handler)
            connection.add_raw_connection(raw_conn)

        request_thread = threading.Thread(
            target=self.request_handler,
            args=(
                request_iterator,
                raw_conn,
                verifier,
            ),
            daemon=True,
        )
        request_thread.start()

        self.logger.info(
            "gRPC Bidirectional stream connection from client established",
            client_node_id=connection.dest_node_id,
            peer=context.peer(),
            server_node_id=server_node_id,
            network_id=network_id,
        )

        try:
            # Response  loop - yields responses as they become available
            while not raw_conn.is_closed:
                try:
                    # Wait for responses with timeout to check stop_event periodically
                    response = raw_conn.get_response(0.5)

                    if response is None:
                        continue
                    yield ProtocolData(packet_data=response)

                except Exception as e:
                    self.logger.error(
                        "Error sending response ",
                        node_id=client_node_id,
                        network_id=network_id,
                        peer=context.peer(),
                        error=str(e),
                    )
                    break

        except Exception as e:
            self.logger.error(
                "Stream error for ",
                node_id=client_node_id,
                network_id=network_id,
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
                node_id=client_node_id,
                network_id=network_id,
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
                self._client = GrpcClientManager(
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
