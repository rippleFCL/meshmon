"""
Prometheus metrics exporter for MeshMon.

This module provides comprehensive Prometheus metrics for monitoring:
- Node statuses (online, offline, unknown)
- Monitor statuses and health
- gRPC transport metrics (packets, bytes, RPS by type)
- Connection health and link utilization
"""

from typing import TYPE_CHECKING

import structlog
from prometheus_client import Counter, Gauge, Histogram, Info

if TYPE_CHECKING:
    from meshmon.connection.connection import ConnectionManager
    from meshmon.distrostore import StoreManager

logger = structlog.get_logger(__name__)

# =============================================================================
# NODE STATUS METRICS
# =============================================================================

# Node status gauge - tracks current node status by network and node_id
node_status = Gauge(
    "meshmon_node_status",
    "Current status of nodes in the mesh network (1=online, 0.5=unknown, 0=offline)",
    ["network_id", "node_id"],
)

# Node info - static information about nodes
node_info = Info(
    "meshmon_node",
    "Static information about mesh nodes",
    ["network_id", "node_id"],
)

# Node round-trip time
node_rtt_seconds = Gauge(
    "meshmon_node_rtt_seconds",
    "Round-trip time to node in seconds",
    ["network_id", "node_id"],
)

# Node last seen timestamp
node_last_seen_timestamp = Gauge(
    "meshmon_node_last_seen_timestamp_seconds",
    "Unix timestamp when node was last seen",
    ["network_id", "node_id"],
)

# =============================================================================
# MONITOR STATUS METRICS
# =============================================================================

# Monitor status gauge - tracks current monitor status
monitor_status = Gauge(
    "meshmon_monitor_status",
    "Current status of monitors (1=online, 0.5=unknown, 0=offline)",
    ["network_id", "monitor_name", "monitor_type"],
)

# Monitor round-trip time
monitor_rtt_seconds = Gauge(
    "meshmon_monitor_rtt_seconds",
    "Round-trip time to monitor target in seconds",
    ["network_id", "monitor_name", "monitor_type"],
)

# Monitor error count
monitor_error_count = Counter(
    "meshmon_monitor_errors_total",
    "Total number of monitor check errors",
    ["network_id", "monitor_name", "monitor_type"],
)

# Monitor last check timestamp
monitor_last_check_timestamp = Gauge(
    "meshmon_monitor_last_check_timestamp_seconds",
    "Unix timestamp when monitor last performed a check",
    ["network_id", "monitor_name", "monitor_type"],
)

# =============================================================================
# gRPC TRANSPORT METRICS - PACKETS
# =============================================================================

# Inbound packet counters by type
grpc_packets_received_total = Counter(
    "meshmon_grpc_packets_received_total",
    "Total number of gRPC packets received",
    ["network_id", "source_node_id", "packet_type"],
)

# Outbound packet counters by type
grpc_packets_sent_total = Counter(
    "meshmon_grpc_packets_sent_total",
    "Total number of gRPC packets sent",
    ["network_id", "dest_node_id", "packet_type"],
)

# Packet processing duration
grpc_packet_processing_duration_seconds = Histogram(
    "meshmon_grpc_packet_processing_duration_seconds",
    "Time spent processing gRPC packets",
    ["network_id", "packet_type"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
)

# =============================================================================
# gRPC TRANSPORT METRICS - BYTES
# =============================================================================

# Inbound bytes by packet type
grpc_bytes_received_total = Counter(
    "meshmon_grpc_bytes_received_total",
    "Total bytes received via gRPC",
    ["network_id", "source_node_id", "packet_type"],
)

# Outbound bytes by packet type
grpc_bytes_sent_total = Counter(
    "meshmon_grpc_bytes_sent_total",
    "Total bytes sent via gRPC",
    ["network_id", "dest_node_id", "packet_type"],
)

# =============================================================================
# gRPC CONNECTION METRICS
# =============================================================================

# Active connections gauge
grpc_connections_active = Gauge(
    "meshmon_grpc_connections_active",
    "Number of active gRPC connections",
    ["network_id", "node_id", "direction"],  # direction: inbound or outbound
)

# Connection establishment counter
grpc_connections_established_total = Counter(
    "meshmon_grpc_connections_established_total",
    "Total number of gRPC connections established",
    ["network_id", "node_id", "initiator"],
)

# Connection closure counter
grpc_connections_closed_total = Counter(
    "meshmon_grpc_connections_closed_total",
    "Total number of gRPC connections closed",
    ["network_id", "node_id", "initiator"],
)

# Connection errors
grpc_connection_errors_total = Counter(
    "meshmon_grpc_connection_errors_total",
    "Total number of gRPC connection errors",
    ["network_id", "node_id", "error_type"],
)

# Connection duration histogram
grpc_connection_duration_seconds = Histogram(
    "meshmon_grpc_connection_duration_seconds",
    "Duration of gRPC connections",
    ["network_id", "node_id"],
    buckets=[1, 10, 60, 300, 600, 1800, 3600, 7200, 14400, 28800, 86400],
)

# =============================================================================
# LINK UTILIZATION METRICS
# =============================================================================

# Link utilization (0-1 scale representing percentage)
grpc_link_utilization = Gauge(
    "meshmon_grpc_link_utilization_ratio",
    "Estimated link utilization ratio (0-1) based on packet rate and size",
    ["network_id", "node_id", "direction", "initiator"],
)

# Queue depth
grpc_queue_depth = Gauge(
    "meshmon_grpc_queue_depth",
    "Current depth of outbound message queue",
    ["network_id", "node_id", "direction", "initiator"],
)

# =============================================================================
# HEARTBEAT SPECIFIC METRICS
# =============================================================================


# Heartbeat latency
heartbeat_latency_seconds = Histogram(
    "meshmon_heartbeat_latency_seconds",
    "Heartbeat round-trip latency",
    ["network_id", "node_id"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# =============================================================================
# STORE UPDATE SPECIFIC METRICS
# =============================================================================

# Store update size
store_update_size_bytes = Histogram(
    "meshmon_store_update_size_bytes",
    "Size of store update payloads in bytes",
    ["network_id", "direction"],
    buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000],
)

# =============================================================================
# SYSTEM METRICS
# =============================================================================

# MeshMon version info
meshmon_info = Info(
    "meshmon",
    "MeshMon version and build information",
)

# Active networks
meshmon_networks_active = Gauge(
    "meshmon_networks_active",
    "Number of active networks being monitored",
)

# Active monitors
meshmon_monitors_active = Gauge(
    "meshmon_monitors_active",
    "Number of active monitors",
    ["network_id"],
)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def update_node_metrics(store_manager: "StoreManager") -> None:
    """
    Update node status metrics from the store manager.

    This function reads the current node statuses from all stores and
    updates the corresponding Prometheus metrics.
    """
    from meshmon.dstypes import DSPingData

    try:
        for network_id, store in store_manager.stores.items():
            # Get node status data
            node_ctx = store.get_context("ping_data", DSPingData)

            for node_id in store.config.nodes.keys():
                try:
                    node_data = node_ctx.get(node_id)
                    if node_data:
                        # Convert node status to numeric value
                        if hasattr(node_data, "status"):
                            status_value = _status_to_value(node_data.status)
                            node_status.labels(
                                network_id=network_id,
                                node_id=node_id,
                            ).set(status_value)

                        # Update RTT if available
                        if (
                            hasattr(node_data, "req_time_rtt")
                            and node_data.req_time_rtt >= 0
                        ):
                            node_rtt_seconds.labels(
                                network_id=network_id,
                                node_id=node_id,
                            ).set(node_data.req_time_rtt)

                        # Update last seen timestamp
                        if hasattr(node_data, "date"):
                            node_last_seen_timestamp.labels(
                                network_id=network_id,
                                node_id=node_id,
                            ).set(node_data.date.timestamp())
                except Exception as e:
                    logger.debug(
                        "Error updating node metrics",
                        network_id=network_id,
                        node_id=node_id,
                        error=str(e),
                    )
    except Exception as e:
        logger.error("Error in update_node_metrics", error=e)


def update_monitor_metrics(store_manager: "StoreManager") -> None:
    """
    Update monitor status metrics from the store manager.

    This function reads the current monitor statuses from all stores and
    updates the corresponding Prometheus metrics.
    """
    from meshmon.dstypes import DSMonitorData

    try:
        for network_id, store in store_manager.stores.items():
            # Get monitor data
            monitor_ctx = store.get_context("monitor_data", DSMonitorData)

            # Iterate through all monitors
            monitor_count = 0
            for monitor_name, monitor_data in monitor_ctx:
                try:
                    if monitor_data:
                        monitor_count += 1
                        # Determine monitor type (you may need to adjust this)
                        monitor_type = "http"  # Default, could be extracted from config

                        # Convert status to numeric value
                        status_value = _status_to_value(monitor_data.status)
                        monitor_status.labels(
                            network_id=network_id,
                            monitor_name=monitor_name,
                            monitor_type=monitor_type,
                        ).set(status_value)

                        # Update RTT if available
                        if monitor_data.req_time_rtt >= 0:
                            monitor_rtt_seconds.labels(
                                network_id=network_id,
                                monitor_name=monitor_name,
                                monitor_type=monitor_type,
                            ).set(monitor_data.req_time_rtt)

                        # Update last check timestamp
                        monitor_last_check_timestamp.labels(
                            network_id=network_id,
                            monitor_name=monitor_name,
                            monitor_type=monitor_type,
                        ).set(monitor_data.date.timestamp())
                except Exception as e:
                    logger.debug(
                        "Error updating monitor metrics",
                        network_id=network_id,
                        monitor_name=monitor_name,
                        error=str(e),
                    )

            # Update active monitor count
            meshmon_monitors_active.labels(network_id=network_id).set(monitor_count)
    except Exception as e:
        logger.error("Error in update_monitor_metrics", error=e)


def update_connection_metrics(connection_manager: "ConnectionManager") -> None:
    """
    Update connection metrics from the connection manager.

    This function reads the current connection states and updates
    the corresponding Prometheus metrics.
    """
    try:
        # Count active connections per network/node
        connection_counts: dict[tuple[str, str, str], int] = {}

        for connection in connection_manager:
            network_id = connection.network
            node_id = connection.dest_node_id

            # Count active raw connections
            active_count = sum(
                1 for conn in connection.connections if not conn.is_closed
            )

            key = (network_id, node_id, "outbound")
            connection_counts[key] = active_count

            # Calculate link utilization based on time spent waiting vs processing
            for raw_conn in connection.connections:
                if not raw_conn.is_closed:
                    try:
                        wait_time, processing_time, elapsed_time = (
                            raw_conn.get_timing_stats()
                        )

                        # Utilization is the ratio of time spent waiting for data
                        # Higher wait time = lower utilization (link is idle)
                        # Higher processing time = higher utilization (link is busy)
                        if elapsed_time > 0:
                            inbound_utilization = 1 - (processing_time / elapsed_time)
                            outbound_utilization = 1 - (wait_time / elapsed_time)
                        else:
                            inbound_utilization = 0.0
                            outbound_utilization = 0.0

                        update_link_utilization(
                            network_id=network_id,
                            node_id=node_id,
                            direction="inbound",
                            initiator=raw_conn.initiator,
                            utilization=inbound_utilization,
                        )
                        update_link_utilization(
                            network_id=network_id,
                            node_id=node_id,
                            direction="outbound",
                            initiator=raw_conn.initiator,
                            utilization=outbound_utilization,
                        )
                    except Exception:
                        pass

        # Update gauges
        for (network_id, node_id, direction), count in connection_counts.items():
            grpc_connections_active.labels(
                network_id=network_id,
                node_id=node_id,
                direction=direction,
            ).set(count)

    except Exception as e:
        logger.error("Error in update_connection_metrics", error=e)


def update_system_metrics(store_manager: "StoreManager") -> None:
    """
    Update system-level metrics including node info.
    """
    try:
        # Update active network count
        meshmon_networks_active.set(len(store_manager.stores))

        # Set version info
        from meshmon.version import VERSION

        meshmon_info.info(
            {
                "version": VERSION,
            }
        )

        # Update node info for all nodes in all networks
        for network_id, store in store_manager.stores.items():
            for node_id in store.config.nodes.keys():
                try:
                    # Set node info with version
                    set_node_info(
                        network_id=network_id,
                        node_id=node_id,
                        version=VERSION,
                    )
                except Exception as e:
                    logger.debug(
                        "Error setting node info",
                        network_id=network_id,
                        node_id=node_id,
                        error=str(e),
                    )
    except Exception as e:
        logger.error("Error in update_system_metrics", error=e)


def _status_to_value(status) -> float:
    """
    Convert DSNodeStatus enum to numeric value for Prometheus.

    Returns:
        1.0 for ONLINE
        0.5 for UNKNOWN
        0.0 for OFFLINE
    """
    from meshmon.dstypes import DSObjectStatus

    if status == DSObjectStatus.ONLINE:
        return 1.0
    elif status == DSObjectStatus.UNKNOWN:
        return 0.5
    else:  # OFFLINE
        return 0.0


# =============================================================================
# METRIC RECORDING FUNCTIONS (to be called from other modules)
# =============================================================================


def record_packet_received(
    network_id: str,
    source_node_id: str,
    packet_type: str,
    size_bytes: int,
) -> None:
    """
    Record a received packet.

    Args:
        network_id: Network identifier
        source_node_id: Source node identifier
        packet_type: Type of packet (heartbeat, heartbeat_response, store_update)
        size_bytes: Size of packet payload in bytes
    """
    grpc_packets_received_total.labels(
        network_id=network_id,
        source_node_id=source_node_id,
        packet_type=packet_type,
    ).inc()

    grpc_bytes_received_total.labels(
        network_id=network_id,
        source_node_id=source_node_id,
        packet_type=packet_type,
    ).inc(size_bytes)

    if packet_type == "store_update":
        store_update_size_bytes.labels(
            network_id=network_id,
            direction="inbound",
        ).observe(size_bytes)


def record_packet_sent(
    network_id: str,
    dest_node_id: str,
    packet_type: str,
    size_bytes: int,
) -> None:
    """
    Record a sent packet.

    Args:
        network_id: Network identifier
        dest_node_id: Destination node identifier
        packet_type: Type of packet (heartbeat, heartbeat_response, store_update)
        size_bytes: Size of packet payload in bytes
    """
    grpc_packets_sent_total.labels(
        network_id=network_id,
        dest_node_id=dest_node_id,
        packet_type=packet_type,
    ).inc()

    grpc_bytes_sent_total.labels(
        network_id=network_id,
        dest_node_id=dest_node_id,
        packet_type=packet_type,
    ).inc(size_bytes)

    if packet_type == "store_update":
        store_update_size_bytes.labels(
            network_id=network_id,
            direction="outbound",
        ).observe(size_bytes)


def record_connection_established(
    network_id: str,
    node_id: str,
    initiator: str,
) -> None:
    """
    Record a new connection establishment.

    Args:
        network_id: Network identifier
        node_id: Remote node identifier
        direction: Connection direction (inbound or outbound)
    """
    grpc_connections_established_total.labels(
        network_id=network_id,
        node_id=node_id,
        initiator=initiator,
    ).inc()


def record_connection_closed(
    network_id: str,
    node_id: str,
    initiator: str,
    duration_seconds: float,
) -> None:
    """
    Record a connection closure.

    Args:
        network_id: Network identifier
        node_id: Remote node identifier
        direction: Connection direction (inbound or outbound)
        duration_seconds: How long the connection was active
    """
    grpc_connections_closed_total.labels(
        network_id=network_id,
        node_id=node_id,
        initiator=initiator,
    ).inc()

    grpc_connection_duration_seconds.labels(
        network_id=network_id,
        node_id=node_id,
    ).observe(duration_seconds)


def record_connection_error(
    network_id: str,
    node_id: str,
    error_type: str,
) -> None:
    """
    Record a connection error.

    Args:
        network_id: Network identifier
        node_id: Remote node identifier
        error_type: Type of error (auth_failed, timeout, etc.)
    """
    grpc_connection_errors_total.labels(
        network_id=network_id,
        node_id=node_id,
        error_type=error_type,
    ).inc()


def record_queue_depth(
    network_id: str, node_id: str, depth: int, direction: str, initiator: str
) -> None:
    """
    Record the current queue depth for a connection.

    Args:
        network_id: Network identifier
        node_id: Remote node identifier
        depth: Current queue depth
    """
    grpc_queue_depth.labels(
        network_id=network_id,
        node_id=node_id,
        direction=direction,
        initiator=initiator,
    ).set(depth)


def record_monitor_error(
    network_id: str,
    monitor_name: str,
    monitor_type: str,
) -> None:
    """
    Record a monitor check error.

    Args:
        network_id: Network identifier
        monitor_name: Monitor name
        monitor_type: Type of monitor (http, etc.)
    """
    monitor_error_count.labels(
        network_id=network_id,
        monitor_name=monitor_name,
        monitor_type=monitor_type,
    ).inc()


def record_packet_processing_duration(
    network_id: str,
    packet_type: str,
    duration_seconds: float,
) -> None:
    """
    Record the time spent processing a packet.

    Args:
        network_id: Network identifier
        packet_type: Type of packet (heartbeat, heartbeat_response, store_update)
        duration_seconds: Processing duration in seconds
    """
    grpc_packet_processing_duration_seconds.labels(
        network_id=network_id,
        packet_type=packet_type,
    ).observe(duration_seconds)


def record_heartbeat_latency(
    network_id: str,
    node_id: str,
    latency_seconds: float,
) -> None:
    """
    Record heartbeat round-trip latency.

    Args:
        network_id: Network identifier
        node_id: Remote node identifier
        latency_seconds: Round-trip latency in seconds
    """
    heartbeat_latency_seconds.labels(
        network_id=network_id,
        node_id=node_id,
    ).observe(latency_seconds)


def update_link_utilization(
    network_id: str, node_id: str, direction: str, utilization: float, initiator: str
) -> None:
    """
    Update the link utilization estimate.

    Args:
        network_id: Network identifier
        node_id: Remote node identifier
        direction: Direction (inbound or outbound)
        utilization: Utilization ratio between 0.0 and 1.0
    """
    grpc_link_utilization.labels(
        network_id=network_id,
        node_id=node_id,
        direction=direction,
        initiator=initiator,
    ).set(max(0.0, min(1.0, utilization)))  # Clamp between 0 and 1


def set_node_info(
    network_id: str,
    node_id: str,
    version: str = "",
    **extra_labels: str,
) -> None:
    """
    Set static information about a node.

    Args:
        network_id: Network identifier
        node_id: Node identifier
        version: Node software version
        **extra_labels: Additional labels to include
    """
    info_dict = {"version": version}
    info_dict.update(extra_labels)
    node_info.labels(
        network_id=network_id,
        node_id=node_id,
    ).info(info_dict)


# =============================================================================
# CLEANUP FUNCTIONS
# =============================================================================


def cleanup_raw_connection_metrics(
    network_id: str,
    node_id: str,
    direction: str | None = None,
    initiator: str | None = None,
) -> None:
    """
    Remove all metrics for a specific raw connection.

    This should be called when a raw connection is closed to prevent
    metric cardinality explosion from accumulating stale connections.

    Args:
        network_id: Network identifier
        node_id: Remote node identifier
        direction: Connection direction (inbound or outbound), if known
        initiator: Which side initiated (local or remote), if known
    """
    # If both direction and initiator are provided, clean up specific metrics
    if direction is not None and initiator is not None:
        try:
            grpc_link_utilization.remove(network_id, node_id, direction, initiator)
        except KeyError:
            pass

        try:
            grpc_queue_depth.remove(network_id, node_id, direction, initiator)
        except KeyError:
            pass
    else:
        # Otherwise, try to clean up all possible combinations
        for dir in ["inbound", "outbound"]:
            for init in ["local", "remote"]:
                try:
                    grpc_link_utilization.remove(network_id, node_id, dir, init)
                except KeyError:
                    pass

                try:
                    grpc_queue_depth.remove(network_id, node_id, dir, init)
                except KeyError:
                    pass

    logger.debug(
        "Cleaned up raw connection metrics",
        network_id=network_id,
        node_id=node_id,
        direction=direction,
        initiator=initiator,
    )


def cleanup_connection_metrics(network_id: str, node_id: str) -> None:
    """
    Remove all metrics for a connection (all raw connections to a node).

    This should be called when a connection manager's connection to a node
    is fully closed.

    Args:
        network_id: Network identifier
        node_id: Remote node identifier
    """
    packet_types = ["heartbeat", "heartbeat_response", "store_update"]
    directions = ["inbound", "outbound"]
    initiators = ["local", "remote"]

    # Clean up packet metrics
    for packet_type in packet_types:
        try:
            grpc_packets_sent_total.remove(network_id, node_id, packet_type)
        except KeyError:
            pass

        try:
            grpc_packets_received_total.remove(network_id, node_id, packet_type)
        except KeyError:
            pass

        try:
            grpc_bytes_sent_total.remove(network_id, node_id, packet_type)
        except KeyError:
            pass

        try:
            grpc_bytes_received_total.remove(network_id, node_id, packet_type)
        except KeyError:
            pass

    # Clean up heartbeat latency (not per-packet-type)
    try:
        heartbeat_latency_seconds.remove(network_id, node_id)
    except KeyError:
        pass

    # Clean up connection metrics
    for direction in directions:
        try:
            grpc_connections_active.remove(network_id, node_id, direction)
        except KeyError:
            pass

        try:
            grpc_connections_established_total.remove(network_id, node_id, direction)
        except KeyError:
            pass

        try:
            grpc_connections_closed_total.remove(network_id, node_id, direction)
        except KeyError:
            pass

        # Clean up raw connections for this direction
        for initiator in initiators:
            cleanup_raw_connection_metrics(network_id, node_id, direction, initiator)

    # Clean up connection duration histogram
    try:
        grpc_connection_duration_seconds.remove(network_id, node_id)
    except KeyError:
        pass

    # Clean up connection errors
    error_types = ["timeout", "refused", "unavailable", "unknown"]
    for error_type in error_types:
        try:
            grpc_connection_errors_total.remove(network_id, node_id, error_type)
        except KeyError:
            pass

    logger.info(
        "Cleaned up connection metrics",
        network_id=network_id,
        node_id=node_id,
    )


def cleanup_node_metrics(network_id: str, node_id: str) -> None:
    """
    Remove all metrics for a specific node.

    This should be called when a node is removed from the configuration
    to prevent accumulating stale metrics.

    Args:
        network_id: Network identifier
        node_id: Node identifier to clean up
    """
    # Clean up node status metrics
    try:
        node_status.remove(network_id, node_id)
    except KeyError:
        pass

    try:
        node_info.remove(network_id, node_id)
    except KeyError:
        pass

    try:
        node_rtt_seconds.remove(network_id, node_id)
    except KeyError:
        pass

    try:
        node_last_seen_timestamp.remove(network_id, node_id)
    except KeyError:
        pass

    # Clean up all connection-related metrics for this node
    cleanup_connection_metrics(network_id, node_id)

    # Clean up packet processing metrics
    packet_types = ["heartbeat", "heartbeat_response", "store_update"]
    for packet_type in packet_types:
        try:
            grpc_packet_processing_duration_seconds.remove(network_id, packet_type)
        except KeyError:
            pass

    logger.info(
        "Cleaned up node metrics",
        network_id=network_id,
        node_id=node_id,
    )


def cleanup_monitor_metrics(
    network_id: str, monitor_name: str, monitor_type: str = "http"
) -> None:
    """
    Remove all metrics for a specific monitor.

    This should be called when a monitor is removed from the configuration.

    Args:
        network_id: Network identifier
        monitor_name: Monitor name
        monitor_type: Type of monitor (http, tcp, etc.)
    """
    try:
        monitor_status.remove(network_id, monitor_name, monitor_type)
    except KeyError:
        pass

    try:
        monitor_rtt_seconds.remove(network_id, monitor_name, monitor_type)
    except KeyError:
        pass

    try:
        monitor_error_count.remove(network_id, monitor_name, monitor_type)
    except KeyError:
        pass

    try:
        monitor_last_check_timestamp.remove(network_id, monitor_name, monitor_type)
    except KeyError:
        pass

    logger.info(
        "Cleaned up monitor metrics",
        network_id=network_id,
        monitor_name=monitor_name,
        monitor_type=monitor_type,
    )


def cleanup_network_metrics(
    network_id: str,
    node_ids: list[str] | None = None,
    monitor_names: list[str] | None = None,
) -> None:
    """
    Remove all metrics for an entire network.

    This should be called when a network is removed from the configuration.

    Args:
        network_id: Network identifier to clean up
        node_ids: Optional list of node IDs in this network (if known)
        monitor_names: Optional list of monitor names in this network (if known)
    """
    # If node_ids provided, clean up each node
    if node_ids:
        for node_id in node_ids:
            cleanup_node_metrics(network_id, node_id)

    # If monitor_names provided, clean up each monitor
    if monitor_names:
        for monitor_name in monitor_names:
            # Try common monitor types
            for monitor_type in ["http", "tcp", "icmp", "dns"]:
                cleanup_monitor_metrics(network_id, monitor_name, monitor_type)

    # Clean up network-level metrics
    try:
        meshmon_monitors_active.remove(network_id)
    except KeyError:
        pass

    # Clean up store update size metrics
    for direction in ["inbound", "outbound"]:
        try:
            store_update_size_bytes.remove(network_id, direction)
        except KeyError:
            pass

    logger.info(
        "Cleaned up network metrics",
        network_id=network_id,
        node_count=len(node_ids) if node_ids else "unknown",
        monitor_count=len(monitor_names) if monitor_names else "unknown",
    )
