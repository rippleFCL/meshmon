import datetime
from pydantic import BaseModel
from enum import Enum

from meshmon.config import NetworkConfigLoader
from .store import NodePingStatus, get_network_data, NetworkData, NodeStatus
from meshmon.pulsewave.distrostore import StoreManager
import logging

logger = logging.getLogger("meshmon.analysis")


class PingStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"
    NODE_DOWN = "node_down"


class AggregateStatus(Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class Status(Enum):
    ONLINE = "online"
    OFFLINE = "offline"


class NodeConnectionDetail(BaseModel):
    """Detailed information about a connection to/from a specific node"""

    status: PingStatus
    rtt: float


class AggregatedConnectionDetail(BaseModel):
    """Aggregated information about connections to/from a specific node"""

    total_connections: int
    online_connections: int
    offline_connections: int
    average_rtt: float
    status: AggregateStatus


class NodeInfo(BaseModel):
    version: str
    data_retention: datetime.datetime


class NodeAnalysis(BaseModel):
    """Complete analysis of a node's connectivity status"""

    node_status: Status
    inbound_info: dict[str, NodeConnectionDetail]
    outbound_info: dict[str, NodeConnectionDetail]
    inbound_status: AggregatedConnectionDetail
    outbound_status: AggregatedConnectionDetail
    node_info: NodeInfo


class MonitorDetail(BaseModel):
    status: PingStatus
    rtt: float


class MonitorAnalysis(BaseModel):
    monitor_status: NodePingStatus
    inbound_info: dict[str, MonitorDetail]
    inbound_status: AggregatedConnectionDetail


class NetworkAnalysis(BaseModel):
    """Analysis of the entire network"""

    total_nodes: int
    online_nodes: int
    offline_nodes: int
    node_analyses: dict[str, NodeAnalysis]
    monitor_analyses: dict[str, MonitorAnalysis]


class MultiNetworkAnalysis(BaseModel):
    """Analysis of all networks in the store manager"""

    networks: dict[str, NetworkAnalysis]


def get_node_statuses(network_data: NetworkData) -> dict[str, NodeStatus]:
    """Get the status of all nodes in a specific network"""
    node_statuses: dict[str, NodeStatus] = {}
    for node_id, node_data in network_data.nodes.items():
        if node_data.node_info.status == NodeStatus.OFFLINE:
            node_statuses[node_id] = NodeStatus.OFFLINE
            continue
        for ping_node_id, ping in node_data.ping_data.items():
            last_ping = ping.date
            time_since_last_ping = (
                datetime.datetime.now(datetime.timezone.utc) - last_ping
            ).total_seconds()
            max_ping_interval = ping.ping_rate * (ping.max_retries + 2)
            # logger.debug(
            #     f"Node {node_id} last ping to {ping_node_id} was {time_since_last_ping} seconds ago. Max allowed: {max_ping_interval} seconds."
            # )
            if time_since_last_ping < max_ping_interval:  # account for timeout
                node_statuses[node_id] = NodeStatus.ONLINE
                break
        else:
            if node_data.ping_data:
                node_statuses[node_id] = NodeStatus.OFFLINE
                continue
            # If no pings exist, assume online if node_info is online
        node_statuses[node_id] = NodeStatus.ONLINE
    return node_statuses


def get_monitor_statuses(network_data: NetworkData) -> dict[str, NodePingStatus]:
    """Get the monitor status of all nodes in a specific network"""
    node_status = get_node_statuses(network_data)
    monitor_statuses: dict[str, NodePingStatus] = {}
    for node_id, node_data in network_data.nodes.items():
        for ping_node_id, ping in node_data.monitor_data.items():
            if monitor_statuses.get(ping_node_id) == NodePingStatus.ONLINE:
                continue
            if (
                monitor_statuses.get(ping_node_id) == NodePingStatus.OFFLINE
                and ping.status == NodePingStatus.UNKNOWN
            ):
                continue
            last_ping = ping.date
            time_since_last_ping = (
                datetime.datetime.now(datetime.timezone.utc) - last_ping
            ).total_seconds()
            max_ping_interval = ping.ping_rate * (ping.max_retries + 2)
            # logger.debug(
            #     f"Node {node_id} last ping to {ping_node_id} was {time_since_last_ping} seconds ago. Max allowed: {max_ping_interval} seconds."
            # )
            if node_status.get(node_id) == NodePingStatus.OFFLINE:
                monitor_statuses[ping_node_id] = NodePingStatus.OFFLINE
                continue
            if time_since_last_ping > max_ping_interval:
                monitor_statuses[ping_node_id] = NodePingStatus.OFFLINE
                continue
            # account for timeout
            monitor_statuses[ping_node_id] = ping.status
    return monitor_statuses


def get_aggregate_status(online: int, offline: int) -> AggregateStatus:
    if online == offline == 0:
        return AggregateStatus.OFFLINE
    if offline == 0:
        return AggregateStatus.ONLINE
    elif online > 0:
        return AggregateStatus.DEGRADED
    else:
        return AggregateStatus.OFFLINE


def analyze_network(network_data: NetworkData) -> NetworkAnalysis:
    node_statuses = get_node_statuses(network_data)
    node_analyses: dict[str, NodeAnalysis] = {}
    node_monitor_info: dict[str, dict[str, MonitorDetail]] = {}
    status_map = {
        NodePingStatus.ONLINE: PingStatus.ONLINE,
        NodePingStatus.OFFLINE: PingStatus.OFFLINE,
        NodePingStatus.UNKNOWN: PingStatus.UNKNOWN,
    }

    for node_id, node_data in network_data.nodes.items():
        if node_id not in node_statuses:
            continue
        node_status = node_statuses[node_id]

        inbound_info: dict[str, NodeConnectionDetail] = {}
        outbound_info: dict[str, NodeConnectionDetail] = {}
        # Analyze inbound connections
        if node_status == NodeStatus.ONLINE:
            for other_node_id, other_node_data in network_data.nodes.items():
                if other_node_id == node_id:
                    continue

                if ping := other_node_data.ping_data.get(node_id):
                    status = status_map[ping.status]
                    if node_statuses[other_node_id] == NodeStatus.OFFLINE:
                        status = PingStatus.NODE_DOWN
                    inbound_info[other_node_id] = NodeConnectionDetail(
                        status=status, rtt=ping.rtt
                    )

            # Analyze outbound connections
            for other_node_id, ping in node_data.ping_data.items():
                status = status_map[ping.status]
                if node_statuses.get(other_node_id) == NodeStatus.OFFLINE:
                    status = PingStatus.NODE_DOWN
                outbound_info[other_node_id] = NodeConnectionDetail(
                    status=status, rtt=ping.rtt
                )
            for monitor_id, ping in node_data.monitor_data.items():
                status = status_map[ping.status]
                if ping.status == NodePingStatus.OFFLINE:
                    status = PingStatus.OFFLINE
                elif ping.status == NodePingStatus.UNKNOWN:
                    status = PingStatus.UNKNOWN
                else:
                    status = PingStatus.ONLINE

                monitor_info = node_monitor_info.setdefault(monitor_id, {})
                monitor_info[node_id] = MonitorDetail(status=status, rtt=ping.rtt)

        online_inbound = sum(
            1 for info in inbound_info.values() if info.status == PingStatus.ONLINE
        )
        offline_inbound = sum(
            1 for info in inbound_info.values() if info.status == PingStatus.OFFLINE
        )
        total_inbound = online_inbound + offline_inbound

        online_outbound = sum(
            1 for info in outbound_info.values() if info.status == PingStatus.ONLINE
        )
        offline_outbound = sum(
            1 for info in outbound_info.values() if info.status == PingStatus.OFFLINE
        )
        total_outbound = online_outbound + offline_outbound

        inbound_status = get_aggregate_status(online_inbound, offline_inbound)
        outbound_status = get_aggregate_status(online_outbound, offline_outbound)

        node_analysis = NodeAnalysis(
            node_status=Status.ONLINE
            if node_status == NodeStatus.ONLINE
            else Status.OFFLINE,
            inbound_info=inbound_info,
            outbound_info=outbound_info,
            inbound_status=AggregatedConnectionDetail(
                total_connections=total_inbound,
                online_connections=online_inbound,
                offline_connections=offline_inbound,
                average_rtt=sum(
                    info.rtt
                    for info in inbound_info.values()
                    if info.status == PingStatus.ONLINE
                )
                / (online_inbound or 1),
                status=inbound_status,
            ),
            outbound_status=AggregatedConnectionDetail(
                total_connections=total_outbound,
                online_connections=online_outbound,
                offline_connections=offline_outbound,
                average_rtt=sum(
                    info.rtt
                    for info in outbound_info.values()
                    if info.status == PingStatus.ONLINE
                )
                / (online_outbound or 1),
                status=outbound_status,
            ),
            node_info=NodeInfo(
                version=node_data.node_info.version,
                data_retention=node_data.node_info.data_retention,
            ),
        )
        node_analyses[node_id] = node_analysis
    monitor_analyses: dict[str, MonitorAnalysis] = {}
    for monitor_id, monitor_info in node_monitor_info.items():
        if not monitor_info:
            continue
        online_inbound = sum(
            1 for info in monitor_info.values() if info.status == PingStatus.ONLINE
        )
        offline_inbound = sum(
            1 for info in monitor_info.values() if info.status == PingStatus.OFFLINE
        )
        total_inbound = online_inbound + offline_inbound

        inbound_status = get_aggregate_status(online_inbound, offline_inbound)

        monitor_status = NodePingStatus.OFFLINE
        if any(info.status == PingStatus.ONLINE for info in monitor_info.values()):
            monitor_status = NodePingStatus.ONLINE
        elif all(info.status == PingStatus.UNKNOWN for info in monitor_info.values()):
            monitor_status = NodePingStatus.UNKNOWN

        monitor_analysis = MonitorAnalysis(
            monitor_status=monitor_status,
            inbound_info=monitor_info,
            inbound_status=AggregatedConnectionDetail(
                total_connections=total_inbound,
                online_connections=online_inbound,
                offline_connections=offline_inbound,
                average_rtt=sum(
                    info.rtt
                    for info in monitor_info.values()
                    if info.status == PingStatus.ONLINE
                )
                / (online_inbound or 1),
                status=inbound_status,
            ),
        )
        monitor_analyses[monitor_id] = monitor_analysis

    return NetworkAnalysis(
        total_nodes=len(network_data.nodes),
        online_nodes=sum(
            1 for status in node_statuses.values() if status == NodeStatus.ONLINE
        ),
        offline_nodes=sum(
            1 for status in node_statuses.values() if status == NodeStatus.OFFLINE
        ),
        node_analyses=node_analyses,
        monitor_analyses=monitor_analyses,
    )


def analyze_node_status(
    store_manager: StoreManager, config: NetworkConfigLoader, network_id: str
) -> dict[str, NodeStatus] | None:
    network_data = get_network_data(store_manager, config)
    if network_id not in network_data.networks:
        return None
    return get_node_statuses(network_data.networks[network_id])


def analyze_monitor_status(
    store_manager: StoreManager, config: NetworkConfigLoader, network_id: str
) -> dict[str, NodePingStatus] | None:
    network_data = get_network_data(store_manager, config)
    if network_id not in network_data.networks:
        return None
    return get_monitor_statuses(network_data.networks[network_id])


def analyze_all_networks(
    store_manager: StoreManager, config: NetworkConfigLoader
) -> MultiNetworkAnalysis:
    network_data = get_network_data(store_manager, config)
    network_analyses = {
        network_id: analyze_network(network)
        for network_id, network in network_data.networks.items()
    }
    return MultiNetworkAnalysis(networks=network_analyses)
