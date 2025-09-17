import datetime
from pydantic import BaseModel
from enum import Enum
from .store import NodePingStatus, get_network_data, NetworkData, NodeStatus
from meshmon.distrostore import StoreManager
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


class NetworkAnalysis(BaseModel):
    """Analysis of the entire network"""

    total_nodes: int
    online_nodes: int
    offline_nodes: int
    node_analyses: dict[str, NodeAnalysis]


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
            logger.info(
                f"Node {node_id} last ping to {ping_node_id} was {time_since_last_ping} seconds ago. Max allowed: {ping.ping_rate * 2} seconds."
            )
            if time_since_last_ping > ping.ping_rate * ping.max_retries:
                node_statuses[node_id] = NodeStatus.OFFLINE
                break
        else:
            node_statuses[node_id] = NodeStatus.ONLINE
    return node_statuses


def get_aggregate_status(online: int, offline: int) -> AggregateStatus:
    if offline == 0:
        return AggregateStatus.ONLINE
    elif online > 0:
        return AggregateStatus.DEGRADED
    else:
        return AggregateStatus.OFFLINE


def analyze_network(network_data: NetworkData) -> NetworkAnalysis:
    node_statuses = get_node_statuses(network_data)
    node_analyses: dict[str, NodeAnalysis] = {}
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

    return NetworkAnalysis(
        total_nodes=len(network_data.nodes),
        online_nodes=sum(
            1 for status in node_statuses.values() if status == NodeStatus.ONLINE
        ),
        offline_nodes=sum(
            1 for status in node_statuses.values() if status == NodeStatus.OFFLINE
        ),
        node_analyses=node_analyses,
    )


def analyze_all_networks(store_manager: StoreManager) -> MultiNetworkAnalysis:
    network_data = get_network_data(store_manager)
    network_analyses = {
        network_id: analyze_network(network)
        for network_id, network in network_data.networks.items()
    }
    return MultiNetworkAnalysis(networks=network_analyses)
