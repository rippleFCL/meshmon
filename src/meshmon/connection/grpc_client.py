import os
import queue
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

import grpc
import structlog

from meshmon.config.bus import ConfigBus, ConfigPreprocessor

from ..config.config import Config
from ..connection.grpc_types import Validator
from ..connection.protocol_handler import (
    ConnectionConfigPreprocessor,
    PulseWaveProtocol,
)
from ..pulsewave.crypto import Signer, Verifier
from ..pulsewave.data import SignedBlockData
from .connection import ConnectionManager, RawConnection
from .proto import (
    ConnectionValidation,
    MeshMonServiceStub,
    ProtocolData,
)

if TYPE_CHECKING:
    from .grpc_server import GrpcUpdateHandlerContainer


@dataclass
class ClientTarget:
    verifier: Verifier
    signer: Signer
    network_id: str
    node_id: str
    self_node_id: str
    address: str
    secure: bool


class ClientTargetsPreprocessor(ConfigPreprocessor[list[ClientTarget]]):
    def preprocess(self, config: Config | None) -> list[ClientTarget]:
        client_targets = []
        if config is None:
            return client_targets
        for network_id, network in config.networks.items():
            for node in network.node_config:
                if node.node_id == network.node_id:
                    continue
                if not node.url:
                    continue
                if network.node_id in node.block or (
                    node.allow and network.node_id in node.allow
                ):
                    continue
                verifier = network.key_mapping.get_verifier(node.node_id)
                if verifier is None:
                    continue
                address = node.url
                if address.startswith("grpc://"):
                    address = address[7:]
                    secure = False
                elif address.startswith("grpcs://"):
                    address = address[8:]
                    secure = True
                else:
                    continue
                client_targets.append(
                    ClientTarget(
                        verifier=verifier,
                        signer=network.key_mapping.signer,
                        network_id=network_id,
                        node_id=node.node_id,
                        self_node_id=network.node_id,
                        address=address,
                        secure=secure,
                    )
                )
        return client_targets


class GrpcClientManager:
    """gRPC client that uses ConnectionManager and RawConnection to manage streams."""

    def __init__(
        self,
        connection_manager: ConnectionManager,
        update_handlers: "GrpcUpdateHandlerContainer",
        config_bus: ConfigBus,
    ):
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.connection.grpc_client", component="GrpcClientManager"
        )
        self.connection_manager = connection_manager
        self.config_bus = config_bus
        watcher = config_bus.get_watcher(ClientTargetsPreprocessor())
        if watcher is None:
            raise ValueError("No initial config available for gRPC client")
        self.config = watcher.current_config
        watcher.subscribe(self.reload)
        self.update_handlers = update_handlers
        self.channels: dict[str, grpc.Channel] = {}
        self.stubs: dict[str, MeshMonServiceStub] = {}
        self.stream_threads: dict[str, threading.Thread] = {}
        self.clients: dict[str, "GrpcClient"] = {}
        self.stop_event = threading.Event()
        self._manager_thread = threading.Thread(
            target=self._connection_manager,
            name="grpc-client-manager",
        )
        self._manager_thread.start()

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
                # Ensure connections to all configured peers
                for target in self.config:
                    key = f"{target.network_id}:{target.node_id}"
                    t = self.stream_threads.get(key)
                    if t is None or not t.is_alive():
                        self.connect_to_target(target)
            except Exception as e:
                self.logger.exception("Error in connection manager loop", error=str(e))
            finally:
                self.stop_event.wait(reconnect_interval)

    def connect_to_target(self, target: ClientTarget) -> bool:
        """Connect to a peer node using a ClientTarget, create a RawConnection, and register in ConnectionManager."""
        try:
            key = f"{target.network_id}:{target.node_id}"
            # Avoid duplicate connects
            existing = self.stream_threads.get(key)
            if existing and existing.is_alive():
                return True
            # Setup channel and stu
            options = [
                ("grpc.keepalive_time_ms", 10000),
                ("grpc.keepalive_timeout_ms", 5000),
                ("grpc.keepalive_permit_without_calls", True),
                ("grpc.http2.max_pings_without_data", 0),
                ("grpc.http2.min_time_between_pings_ms", 10000),
                ("grpc.http2.min_ping_interval_without_data_ms", 300000),
            ]
            if not target.secure:
                channel = grpc.insecure_channel(
                    target.address,
                    options=options,
                )
            else:
                creds = grpc.ssl_channel_credentials()
                channel = grpc.secure_channel(
                    target.address,
                    creds,
                    options=options,
                )
            stub = MeshMonServiceStub(channel)

            # Build per-peer client and start streaming thread
            handler = self.update_handlers.get_handler(target.network_id)

            # Create a config watcher for this client

            client = GrpcClient(
                channel=channel,
                connection_manager=self.connection_manager,
                handler=handler,
                network_id=target.network_id,
                peer_node_id=target.node_id,
                address=target.address,
                config_bus=self.config_bus,
                verifier=target.verifier,
                signer=target.signer,
                self_node_id=target.self_node_id,
            )

            t = threading.Thread(
                target=client.stream_worker,
                name=f"grpc-client-stream-{target.network_id}-{target.node_id}",
            )
            t.start()

            # Save references
            self.channels[key] = channel
            self.stubs[key] = stub
            self.stream_threads[key] = t
            self.clients[key] = client

            return True
        except grpc.RpcError as e:
            self.logger.debug(
                "gRPC connection failed",
                node_id=target.node_id,
                address=target.address,
                error=str(e),
            )
            return False
        except Exception as e:
            self.logger.error(
                "Failed to connect to node", node_id=target.node_id, error=e
            )
            return False

    def stop(self):
        self.stop_event.set()
        if self._manager_thread.is_alive():
            self._manager_thread.join(timeout=2.0)
        # Ask clients to cancel their RPCs first
        for client in list(self.clients.values()):
            try:
                client.stop_stream()
            except Exception:
                pass
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
        self.clients.clear()

    def reload(self, new_config: list[ClientTarget]) -> None:
        """Reload the client configuration and reconnect as needed."""
        self.logger.info(
            "Config reload triggered for GrpcClientManager",
            new_target_count=len(new_config),
            old_target_count=len(self.config),
        )
        self.config = new_config
        outbound_nodes = [node.node_id for node in new_config]
        for conn in self.connection_manager:
            if conn.dest_node_id in outbound_nodes:
                continue
            for raw_conn in list(conn.connections):
                if raw_conn.initiator == "local":
                    conn.remove_raw_connection(raw_conn)

        self.logger.debug("GrpcClientManager config updated successfully")


class GrpcClient:
    def __init__(
        self,
        channel: grpc.Channel,
        connection_manager: ConnectionManager,
        handler: object,
        network_id: str,
        self_node_id: str,
        verifier: Verifier,
        signer: Signer,
        peer_node_id: str,
        address: str,
        config_bus: ConfigBus,
    ):
        self.self_node_id = self_node_id
        self.verifier = verifier
        self.signer = signer
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.connection.grpc_client", component="GrpcClient"
        )
        self.channel = channel
        self.connection_manager = connection_manager
        # handler here is the concrete GrpcUpdateHandler for this network
        # typing: the container was used in manager; here we store the resolved handler
        self.handler = handler  # type: ignore[assignment]
        self.network_id = network_id
        self.peer_node_id = peer_node_id
        self.address = address
        self.config_bus = config_bus

        self.stub = MeshMonServiceStub(channel)
        self.stop_event = threading.Event()
        self.connection_active = threading.Event()
        self.raw_conn: RawConnection | None = None
        self._send_queue: "queue.Queue[ProtocolData]" = queue.Queue()
        self._client_nonce: str | None = None
        self._call: grpc.Call | None = None

    def stop_stream(self):
        """Cancel the active stream and signal shutdown."""
        self.stop_event.set()
        try:
            if self._call is not None:
                self._call.cancel()
            self.channel.close()
        except Exception:
            pass

    def request_generator(self) -> Iterator[ProtocolData]:
        # Yield queued control frames first (e.g., initial ConnectionValidation),
        # then PacketData coming from the RawConnection.
        while not self.connection_active.is_set() and not self.stop_event.is_set():
            try:
                item = self._send_queue.get(timeout=0.1)
                yield item
            except queue.Empty:
                pass
        while not self.stop_event.is_set():
            if (
                self.connection_active.is_set()
                and self.raw_conn is not None
                and not self.raw_conn.is_closed
            ):
                pkt = self.raw_conn.get_response(timeout=0.1)
                if pkt is not None:
                    yield ProtocolData(packet_data=pkt)

    def stream_worker(self):
        connection = None
        try:
            # Start the bidi stream with client nonce as metadata
            client_nonce = os.urandom(256).hex()
            self._client_nonce = client_nonce
            response_iterator = self.stub.StreamUpdates(
                self.request_generator(), metadata=(("client-nonce", client_nonce),)
            )
            # Track the underlying call to allow client-side abort/cancel
            try:
                self._call = response_iterator
            except Exception:
                self._call = None

            # Wait for server's initial metadata (server_nonce)
            # Ensure channel is READY before attempting to grab initial metadata
            try:
                grpc.channel_ready_future(self.channel).result(timeout=5)
            except Exception:
                self.logger.debug(
                    "Could not establish Connection",
                    dest_node_id=self.peer_node_id,
                    address=self.address,
                )
                self.stop_stream()
                return

            try:
                md = dict(response_iterator.initial_metadata())
            except Exception:
                md = {}
            server_nonce = md.get("server-nonce", md.get("server_nonce"))
            if isinstance(server_nonce, bytes):
                try:
                    server_nonce = server_nonce.decode("ascii", errors="ignore")
                except Exception:
                    server_nonce = None  # type: ignore[assignment]
            if not server_nonce:
                self.logger.warning(
                    "Missing server-nonce in initial metadata",
                    dest_node_id=self.peer_node_id,
                )
                self.stop_stream()
                return

            # Build and send our ConnectionValidation first packet
            client_validator = Validator(
                local_nonce=client_nonce,
                remote_nonce=server_nonce,
                network_id=self.network_id,
                node_id=self.self_node_id,
            )
            client_sbd = SignedBlockData.new(
                self.signer, client_validator, "validator", "validator"
            )
            self._send_queue.put(
                ProtocolData(
                    connection_validation=ConnectionValidation(
                        validator=client_sbd.model_dump_json()
                    )
                )
            )

            # Expect server's ConnectionValidation response
            first_resp = next(response_iterator, None)
            if first_resp is None or not first_resp.HasField("connection_validation"):
                self.logger.warning(
                    "Invalid first response from server; expected ConnectionValidation",
                    dest_node_id=self.peer_node_id,
                )
                self.stop_stream()
                return

            try:
                server_sbd = SignedBlockData.model_validate_json(
                    first_resp.connection_validation.validator
                )
                server_validator = Validator.model_validate(server_sbd.data)
            except Exception as e:
                self.logger.warning("Failed to parse server validator", error=str(e))
                self.stop_stream()
                return

            # Verify server's response
            if (
                not server_sbd.verify(self.verifier, "validator", "validator")
                or server_validator.local_nonce != server_nonce
                or server_validator.remote_nonce != client_nonce
                or server_validator.network_id != self.network_id
                or server_validator.node_id != self.peer_node_id
            ):
                self.logger.warning(
                    "Server failed client validation",
                    dest_node_id=self.peer_node_id,
                    network_id=self.network_id,
                )
                self.stop_stream()
                return
            config_watcher = self.config_bus.get_watcher(
                ConnectionConfigPreprocessor(self.network_id, self.peer_node_id)
            )
            if config_watcher is None:
                self.logger.warning(
                    "No config available for client; skipping connect",
                    node_id=self.peer_node_id,
                    network_id=self.network_id,
                )
                self.stop_stream()
                return

            # Wire protocol and register raw connection
            protocol_handler = PulseWaveProtocol(
                handler=self.handler,  # type: ignore[arg-type]
                remote_nonce=server_nonce,
                local_nonce=client_nonce,
                watcher=config_watcher,
                mr_sbd=server_sbd,
            )
            self.raw_conn = RawConnection(
                protocol=protocol_handler,
                network_id=self.network_id,
                dest_node_id=self.peer_node_id,
                initiator="local",
            )

            # Register raw connection with ConnectionManager
            connection = self.connection_manager.get_connection(
                self.peer_node_id, self.network_id
            )
            if connection is None:
                connection = self.connection_manager.add_connection(
                    self.peer_node_id, self.self_node_id, self.network_id
                )
            connection.add_raw_connection(self.raw_conn)

            self.logger.info(
                "gRPC Bidirectional stream to server established",
                dest_node_id=self.peer_node_id,
                network_id=self.network_id,
                address=self.address,
            )
            self.connection_active.set()

            # Main receive loop
            for resp in response_iterator:
                if self.raw_conn.is_closed:
                    break
                if resp is None:
                    break
                if resp.HasField("packet_data") and self.raw_conn is not None:
                    self.raw_conn.handle_request(resp.packet_data)

            self.logger.info(
                "gRPC Bidirectional stream to server closed",
                dest_node_id=self.peer_node_id,
            )
        except grpc.RpcError as e:
            # Connection errors are expected during startup/reconnect
            if e.code() == grpc.StatusCode.UNAVAILABLE:  # type: ignore
                self.logger.debug(
                    "Connection unavailable",
                    node_id=self.peer_node_id,
                    address=self.address,
                )
            else:
                self.logger.error(
                    "gRPC stream error",
                    node_id=self.peer_node_id,
                    error=e,
                    code=e.code(),  # type: ignore
                )
                self.logger.info(
                    "gRPC Bidirectional stream to server closed",
                    dest_node_id=self.peer_node_id,
                )
        except Exception as e:
            self.logger.error("Client stream error", node_id=self.peer_node_id, error=e)

        finally:
            # Ensure the RPC is cancelled to abort the connection cleanly
            try:
                self.stop_stream()
            except Exception:
                pass
            try:
                if connection is not None and self.raw_conn is not None:
                    connection.remove_raw_connection(self.raw_conn)
            except Exception:
                pass
