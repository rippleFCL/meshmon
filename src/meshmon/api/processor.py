import datetime

from meshmon.analysis.analysis import (
    AnalysisNodeStatus,
    get_monitor_status,
    get_node_ping_status,
)
from meshmon.api.structure.cluster_info import (
    ClusterClockTableEntry,
    ClusterInfo,
    ClusterInfoApi,
    ClusterNodeStatusEnum,
)
from meshmon.api.structure.notification_cluster import (
    NotificationCluster,
    NotificationClusterApi,
    NotificationClusters,
    NotificationClusterStatusEnum,
)
from meshmon.config.config import Config, NetworkConfig
from meshmon.pulsewave.data import StoreLeaderStatus, StoreNodeStatus

from ..distrostore import StoreManager
from ..dstypes import DSNodeInfo, DSNodeStatus, DSPingData
from ..pulsewave.store import SharedStore
from ..update_handlers import NodeStatusEntry
from .structure.status import (
    ConnectionInfo,
    ConnectionNodeInfo,
    ConnectionType,
    MeshMonApi,
    MonitorConnectionInfo,
    MonitorInfo,
    MonitorStatusEnum,
    NetworkInfo,
    NodeInfo,
    NodeStatusEnum,
)

NODE_STATUS_MAPPING = {
    AnalysisNodeStatus.ONLINE: NodeStatusEnum.ONLINE,
    AnalysisNodeStatus.OFFLINE: NodeStatusEnum.OFFLINE,
    AnalysisNodeStatus.UNKNOWN: NodeStatusEnum.UNKNOWN,
}

MONITOR_STATUS_MAPPING = {
    AnalysisNodeStatus.ONLINE: MonitorStatusEnum.UP,
    AnalysisNodeStatus.OFFLINE: MonitorStatusEnum.DOWN,
    AnalysisNodeStatus.UNKNOWN: MonitorStatusEnum.UNKNOWN,
}

CONNECTION_TYPE_MAPPING = {
    DSNodeStatus.ONLINE: ConnectionType.UP,
    DSNodeStatus.OFFLINE: ConnectionType.DOWN,
    DSNodeStatus.UNKNOWN: ConnectionType.UNKNOWN,
}

PING_TO_MONITOR_STATUS = {
    DSNodeStatus.ONLINE: MonitorStatusEnum.UP,
    DSNodeStatus.OFFLINE: MonitorStatusEnum.DOWN,
    DSNodeStatus.UNKNOWN: MonitorStatusEnum.UNKNOWN,
}

LEADER_STATUS_MAPPING = {
    StoreLeaderStatus.LEADER: NotificationClusterStatusEnum.LEADER,
    StoreLeaderStatus.FOLLOWER: NotificationClusterStatusEnum.FOLLOWER,
    StoreLeaderStatus.WAITING_FOR_CONSENSUS: NotificationClusterStatusEnum.WAITING_FOR_CONSENSUS,
    StoreLeaderStatus.NOT_PARTICIPATING: NotificationClusterStatusEnum.NOT_PARTICIPATING,
}


def get_node_infos(store: SharedStore) -> dict[str, NodeInfo]:
    nodes: dict[str, NodeInfo] = {}
    status = store.get_context("node_status", NodeStatusEntry)
    for node_id, entry in status:
        # uptime=...  # Placeholder for actual uptime
        value = store.get_value("node_info", DSNodeInfo, node_id)
        if value:
            version = value.version
        else:
            version = "unknown"
        node_info = NodeInfo(
            node_id=node_id,
            status=NODE_STATUS_MAPPING.get(entry.status, NodeStatusEnum.UNKNOWN),
            version=version,
        )
        nodes[node_id] = node_info
    return nodes


def get_connection_infos(store: SharedStore) -> list[ConnectionInfo]:
    connections: dict[tuple[str, str], ConnectionInfo] = {}
    current_node_statuses = get_node_ping_status(store)
    for current_node_id in store.nodes:
        ping_ctx = store.get_context("ping_data", DSPingData, current_node_id)
        if ping_ctx is None:
            continue
        for node_id, ping_data in ping_ctx:
            node_ping_ctx = store.get_context("ping_data", DSPingData, node_id)
            if node_id == current_node_id:
                continue
            if (current_node_id, node_id) in connections or (
                node_id,
                current_node_id,
            ) in connections:
                continue

            src_ping_data = ping_ctx.get(node_id)
            if not src_ping_data:
                src_ping_data = DSPingData(
                    status=DSNodeStatus.UNKNOWN,
                    req_time_rtt=-1,
                    date=datetime.datetime.now(datetime.timezone.utc),
                )

            if current_node_statuses.get(current_node_id) == AnalysisNodeStatus.OFFLINE:
                src_ping_data = DSPingData(
                    status=DSNodeStatus.OFFLINE,
                    req_time_rtt=-1,
                    date=datetime.datetime.now(datetime.timezone.utc),
                )

            dest_ping_data = (
                node_ping_ctx.get(current_node_id) if node_ping_ctx else None
            )
            if not dest_ping_data:
                dest_ping_data = DSPingData(
                    status=DSNodeStatus.UNKNOWN,
                    req_time_rtt=-1,
                    date=datetime.datetime.now(datetime.timezone.utc),
                )
            if current_node_statuses.get(node_id) == AnalysisNodeStatus.OFFLINE:
                dest_ping_data = DSPingData(
                    status=DSNodeStatus.OFFLINE,
                    req_time_rtt=-1,
                    date=datetime.datetime.now(datetime.timezone.utc),
                )

            src_rtt = (
                src_ping_data.req_time_rtt * 1000
                if src_ping_data.req_time_rtt >= 0
                else -1
            )
            dest_rtt = (
                dest_ping_data.req_time_rtt * 1000
                if dest_ping_data.req_time_rtt >= 0
                else -1
            )
            connections[(current_node_id, node_id)] = ConnectionInfo(
                src_node=ConnectionNodeInfo(
                    rtt=src_rtt,
                    name=current_node_id,
                    conn_type=CONNECTION_TYPE_MAPPING.get(
                        src_ping_data.status, ConnectionType.UNKNOWN
                    ),
                ),
                dest_node=ConnectionNodeInfo(
                    rtt=dest_rtt,
                    name=node_id,
                    conn_type=CONNECTION_TYPE_MAPPING.get(
                        dest_ping_data.status, ConnectionType.UNKNOWN
                    ),
                ),
            )
    return list(connections.values())


def get_monitor_infos(store: SharedStore, network: NetworkConfig) -> list[MonitorInfo]:
    monitors: list[MonitorInfo] = []
    for monitor_id, entry in get_monitor_status(store, network).items():
        monitors.append(
            MonitorInfo(
                monitor_id=monitor_id,
                status=MONITOR_STATUS_MAPPING.get(entry, MonitorStatusEnum.UNKNOWN),
            )
        )
    return monitors


def get_monitor_connection_infos(store: SharedStore) -> list[MonitorConnectionInfo]:
    monitors: dict[tuple[str, str], MonitorConnectionInfo] = {}
    for node_id in store.nodes:
        monitor_ctx = store.get_context("monitor_data", DSPingData, node_id)
        if monitor_ctx is None:
            continue
        for monitor_id, monitor_data in monitor_ctx:
            if (node_id, monitor_id) in monitors:
                continue
            rtt = (
                monitor_data.req_time_rtt * 1000
                if monitor_data.req_time_rtt >= 0
                else -1
            )
            monitors[(node_id, monitor_id)] = MonitorConnectionInfo(
                node_id=node_id,
                monitor_id=monitor_id,
                rtt=rtt,
                status=PING_TO_MONITOR_STATUS.get(
                    monitor_data.status, MonitorStatusEnum.UNKNOWN
                ),
            )
    return list(monitors.values())


def get_network_info(store: SharedStore, network: NetworkConfig) -> NetworkInfo:
    return NetworkInfo(
        nodes=get_node_infos(store),
        connections=get_connection_infos(store),
        monitors=get_monitor_infos(store, network),
        monitor_connections=get_monitor_connection_infos(store),
    )


def generate_api(stores: StoreManager, config: Config) -> MeshMonApi:
    api = MeshMonApi()
    for net_id, store in stores.stores.items():
        netconf = config.networks.get(net_id)
        if not netconf:
            continue
        net_info = get_network_info(store, netconf)
        api.networks[net_id] = net_info
    return api


def generate_cluster_api(stores: StoreManager) -> ClusterInfoApi:
    api = ClusterInfoApi()
    now = datetime.datetime.now(datetime.timezone.utc)
    for net_id, store in stores.stores.items():
        ctx = store.get_consistency()
        clock_table = ctx.clock_table
        node_status = ctx.node_status_table
        clock_table_data: dict[str, ClusterClockTableEntry] = {}
        for node_id, clock in clock_table:
            clock_table_data[node_id] = ClusterClockTableEntry(
                delta_ms=clock.delta.total_seconds() * 1000, node_time=now + clock.delta
            )
        node_status_data: dict[str, ClusterNodeStatusEnum] = {}
        for node_id, status in node_status:
            if status.status == StoreNodeStatus.ONLINE:
                node_status_data[node_id] = ClusterNodeStatusEnum.ONLINE
            elif status.status == StoreNodeStatus.OFFLINE:
                node_status_data[node_id] = ClusterNodeStatusEnum.OFFLINE
            else:
                node_status_data[node_id] = ClusterNodeStatusEnum.UNKNOWN
        api.networks[net_id] = ClusterInfo(
            clock_table=clock_table_data, node_statuses=node_status_data
        )
    return api


def name_from_cluster_id(cluster_id: str) -> str:
    if cluster_id.count(":") == 2:
        webhook_type, name, _ = cluster_id.split(":", 2)
        if webhook_type in ("discord"):
            return name
    return cluster_id


def generate_notification_cluster_info(stores: StoreManager) -> NotificationClusterApi:
    api = NotificationClusterApi()
    for network_id, store in stores.stores.items():
        clusters = NotificationClusters()
        ctx = store.get_consistency().node_status_table

        for node_context in store.all_consistency_contexts():
            for cluster_id, leader_status in node_context.node_statuses():
                node_status = ctx.get(node_context.node_id)
                name = name_from_cluster_id(cluster_id)
                if name not in clusters.clusters:
                    clusters.clusters[name] = NotificationCluster()
                if node_status is None or node_status.status == StoreNodeStatus.ONLINE:
                    clusters.clusters[name].node_statuses[node_context.node_id] = (
                        LEADER_STATUS_MAPPING[leader_status.status]
                    )
                else:
                    clusters.clusters[name].node_statuses[node_context.node_id] = (
                        NotificationClusterStatusEnum.OFFLINE
                    )
        api.networks[network_id] = clusters
    return api
