import datetime
from pydantic import BaseModel
from enum import Enum
from meshmon.distrostore import (
    StoreManager,
    PingData,
    NodeInfo as StoreNodeInfo,
    NodeDataRetention,
)


class NodePingStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class NodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"


class NodePingData(BaseModel):
    status: NodePingStatus
    rtt: float
    date: datetime.datetime
    current_retry: int
    max_retries: int
    ping_rate: int


class NodeInfo(BaseModel):
    status: NodeStatus
    version: str
    data_retention: datetime.datetime


class NodeData(BaseModel):
    ping_data: dict[str, NodePingData]
    node_info: NodeInfo


class NetworkData(BaseModel):
    nodes: dict[str, NodeData]


class MeshmonData(BaseModel):
    networks: dict[str, NetworkData]


def get_network_data(store_manager: StoreManager) -> MeshmonData:
    """
    Extract and transform network data from the store manager into MeshmonData format.

    Args:
        store_manager: The StoreManager containing all network stores

    Returns:
        MeshmonData: Transformed data containing all networks and their node information
    """
    networks: dict[str, NetworkData] = {}

    # Iterate through all network stores
    for network_id, store in store_manager.stores.items():
        nodes: dict[str, NodeData] = {}

        # Get all nodes in the network store
        for node_id in store.nodes:
            # Extract ping data for this node
            ping_data: dict[str, NodePingData] = {}

            # Get ping context for this node (if it exists)
            ping_ctx = store.get_context("ping_data", PingData, node_id)
            if ping_ctx:
                # Iterate through all ping data entries for this node
                for target_node_id in ping_ctx:
                    ping_info = ping_ctx.get(target_node_id)
                    if ping_info:
                        # Convert store PingData to analysis NodePingData
                        ping_data[target_node_id] = NodePingData(
                            status=NodePingStatus(ping_info.status.value),
                            rtt=ping_info.req_time_rtt,
                            date=ping_info.date,
                            current_retry=ping_info.current_retry,
                            max_retries=ping_info.max_retrys,  # Note: typo in store model
                            ping_rate=ping_info.ping_rate,
                        )

            # Extract node info and data retention
            node_info_data = store.get_value("node_info", StoreNodeInfo, node_id)
            data_retention_data = store.get_value(
                "data_retention", NodeDataRetention, node_id
            )

            # Create NodeInfo if we have the required data
            if node_info_data:
                node_info = NodeInfo(
                    status=NodeStatus(node_info_data.status.value),
                    version=node_info_data.version,
                    data_retention=data_retention_data.date
                    if data_retention_data
                    else datetime.datetime.now(datetime.timezone.utc),
                )

                # Create NodeData for this node
                nodes[node_id] = NodeData(ping_data=ping_data, node_info=node_info)
            else:
                nodes[node_id] = NodeData(
                    ping_data=ping_data,
                    node_info=NodeInfo(
                        status=NodeStatus.OFFLINE,
                        version="unknown",
                        data_retention=datetime.datetime.now(datetime.timezone.utc),
                    ),
                )
        # Create NetworkData for this network
        networks[network_id] = NetworkData(nodes=nodes)

    return MeshmonData(networks=networks)
