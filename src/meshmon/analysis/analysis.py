import datetime
from enum import Enum

from ..config.config import LoadedNetworkMonitor, NetworkConfig
from ..dstypes import DSMonitorData, DSObjectStatus, DSPingData
from ..pulsewave.store import SharedStore


class AnalysisNodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


def get_node_ping_status(store: SharedStore) -> dict[str, DSObjectStatus]:
    """Get the status of all nodes in the store."""
    now = datetime.datetime.now(datetime.timezone.utc)
    statuses: dict[str, DSObjectStatus] = {}
    node_status_values: dict[DSObjectStatus, int] = {
        DSObjectStatus.ONLINE: 3,
        DSObjectStatus.OFFLINE: 2,
        DSObjectStatus.UNKNOWN: 1,
    }
    for node in store.config.nodes:
        ping_ctx = store.get_context("ping_data", DSPingData, node)
        if ping_ctx is None:
            continue
        for node_id, ping_data in ping_ctx:
            config = store.config.nodes.get(node_id)
            if config is None:
                statuses[node_id] = DSObjectStatus.UNKNOWN
                continue
            if node_id not in statuses:
                statuses[node_id] = DSObjectStatus.UNKNOWN
            if now - ping_data.date < datetime.timedelta(
                seconds=config.heartbeat_interval * (config.heartbeat_retry + 1)
            ):
                status = ping_data.status
            else:
                status = DSObjectStatus.OFFLINE

            if node_status_values[status] > node_status_values[statuses[node_id]]:
                statuses[node_id] = status
    statuses[store.config.key_mapping.signer.node_id] = DSObjectStatus.ONLINE
    return statuses


def get_monitor_config(config: NetworkConfig):
    """Get a dictionary of monitor configurations from the network configuration."""
    monitor_dict: dict[str, dict[str, LoadedNetworkMonitor]] = {}
    for node in config.node_config:
        local_monitor_dict: dict[str, LoadedNetworkMonitor] = {}
        for monitor in config.monitors:
            local_monitor_dict[monitor.name] = monitor
        monitor_dict[node.node_id] = local_monitor_dict
    return monitor_dict


def get_monitor_status(
    store: SharedStore, config: NetworkConfig
) -> dict[str, "AnalysisNodeStatus"]:
    """Get the status of all monitors in the store."""
    monitor_statuses: list[dict[str, AnalysisNodeStatus]] = []
    for node in config.node_config:
        monitor_ctx = store.get_context("monitor_data", DSMonitorData, node.node_id)
        if monitor_ctx is None:
            continue
        node_monitors: dict[str, AnalysisNodeStatus] = {}
        for monitor_id, monitor_data in monitor_ctx:
            now = datetime.datetime.now(datetime.timezone.utc)
            if (
                now - monitor_data.date
                < datetime.timedelta(
                    seconds=monitor_data.interval * (monitor_data.retry + 1)
                )
                and monitor_data.status == DSObjectStatus.ONLINE
            ):
                node_monitors[monitor_id] = AnalysisNodeStatus.ONLINE
            elif monitor_data.status == DSObjectStatus.OFFLINE:
                node_monitors[monitor_id] = AnalysisNodeStatus.OFFLINE
            else:
                node_monitors[monitor_id] = AnalysisNodeStatus.UNKNOWN
        monitor_statuses.append(node_monitors)
    distilled_statuses: dict[str, AnalysisNodeStatus] = {}
    for monitors in monitor_statuses:
        for monitor_id, monitor_status in monitors.items():
            current_status = distilled_statuses.get(monitor_id)
            if current_status == AnalysisNodeStatus.ONLINE:
                continue

            if monitor_status == AnalysisNodeStatus.ONLINE:
                distilled_statuses[monitor_id] = AnalysisNodeStatus.ONLINE

            if current_status == AnalysisNodeStatus.OFFLINE:
                continue

            if monitor_status == AnalysisNodeStatus.OFFLINE:
                distilled_statuses[monitor_id] = AnalysisNodeStatus.OFFLINE

            if current_status == AnalysisNodeStatus.UNKNOWN:
                continue

            if monitor_status == AnalysisNodeStatus.UNKNOWN:
                distilled_statuses[monitor_id] = AnalysisNodeStatus.UNKNOWN

    return distilled_statuses
