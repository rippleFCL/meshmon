import datetime
from enum import Enum

from ..config.config import LoadedNetworkMonitor, NetworkConfig
from ..dstypes import DSMonitorData, DSNodeStatus, DSPingData
from ..pulsewave.store import SharedStore


class AnalysisNodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


def get_node_ping_status(store: SharedStore) -> dict[str, "AnalysisNodeStatus"]:
    """Get the status of all nodes in the store."""
    statuses: dict[str, list[AnalysisNodeStatus]] = {}
    for node in store.config.nodes:
        ping_ctx = store.get_context("ping_data", DSPingData, node)
        if ping_ctx is None:
            continue
        for node_id, ping_data in ping_ctx:
            config = store.config.nodes.get(node_id)
            status_list = statuses.setdefault(node_id, [])
            if config is None:
                status_list.append(AnalysisNodeStatus.UNKNOWN)
                continue
            now = datetime.datetime.now(datetime.timezone.utc)
            if (
                now - ping_data.date
                < datetime.timedelta(
                    seconds=config.heartbeat_interval * (config.heartbeat_retry + 1)
                )
                and ping_data.status == DSNodeStatus.ONLINE
            ):
                status_list.append(AnalysisNodeStatus.ONLINE)
            elif ping_data.status == DSNodeStatus.OFFLINE:
                status_list.append(AnalysisNodeStatus.OFFLINE)
            else:
                status_list.append(AnalysisNodeStatus.UNKNOWN)

    node_statuses: dict[str, AnalysisNodeStatus] = {}
    for node_id in store.config.nodes:
        status_list = statuses.get(node_id, [])
        if AnalysisNodeStatus.ONLINE in status_list:
            node_statuses[node_id] = AnalysisNodeStatus.ONLINE
        elif AnalysisNodeStatus.OFFLINE in status_list:
            node_statuses[node_id] = AnalysisNodeStatus.OFFLINE
        else:
            node_statuses[node_id] = AnalysisNodeStatus.UNKNOWN
    if store.config.current_node.node_id not in node_statuses:
        node_statuses[store.config.current_node.node_id] = AnalysisNodeStatus.ONLINE
    return node_statuses


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
                and monitor_data.status == DSNodeStatus.ONLINE
            ):
                node_monitors[monitor_id] = AnalysisNodeStatus.ONLINE
            elif monitor_data.status == DSNodeStatus.OFFLINE:
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
