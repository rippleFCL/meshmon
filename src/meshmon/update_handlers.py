import datetime

import structlog

from meshmon.config.bus import ConfigPreprocessor
from meshmon.dstypes import DSMonitorData, DSMonitorStatus, DSNodeStatus, DSObjectStatus
from meshmon.event_log import EventLog, EventType

from .analysis.analysis import (
    AnalysisNodeStatus,
    get_node_ping_status,
)
from .config.config import Config, EventID, NetworkConfig
from .pulsewave.store import SharedStore
from .pulsewave.update.update import RegexPathMatcher, UpdateHandler, UpdateManager


class NodeStatusTableHandler(UpdateHandler):
    """Handles node status updates."""

    def __init__(self, event_log: EventLog):
        self._matcher = RegexPathMatcher(
            [
                "nodes\\..+\\.contexts.ping_data\\..+$",
                "nodes\\..+\\.contexts.ping_data$",
            ]
        )
        self.event_log = event_log

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        """Process an incoming update request."""
        # Implementation for handling updates and updating the status table
        status = get_node_ping_status(self.store)
        status_ctx = self.store.get_context("node_status", DSNodeStatus)
        for node_id, status_data in status.items():
            current_status = status_ctx.get(node_id)
            if current_status is None or current_status.status != status_data:
                status_ctx.set(
                    node_id,
                    DSNodeStatus(
                        status=status_data,
                        last_updated=datetime.datetime.now(datetime.timezone.utc),
                    ),
                )
                if status_data == AnalysisNodeStatus.OFFLINE:
                    self.event_log.log_event(
                        EventType.WARNING,
                        EventID(
                            mid="node_offline",
                            src="NodeStatusTableHandler",
                            network_id=self.store.network_id,
                            uid=node_id,
                        ),
                        f"Node {node_id} has not responded to heartbeats.",
                        f"Node {node_id} is offline",
                    )
                elif status_data == AnalysisNodeStatus.ONLINE:
                    self.event_log.clear_event(
                        mid="node_offline",
                        network_id=self.store.network_id,
                        uid=node_id,
                    )
                self.update_manager.trigger_event("update")
        for node_id, _ in list(status_ctx):
            if node_id not in status:
                status_ctx.delete(node_id)
                self.event_log.clear_event(
                    mid="node_offline",
                    network_id=self.store.network_id,
                    uid=node_id,
                )
                self.update_manager.trigger_event("update")

    def stop(self) -> None:
        """Stop any background tasks."""
        pass

    def matcher(self) -> RegexPathMatcher:
        return self._matcher


class MonitorStatusTablePreprocessor(ConfigPreprocessor[NetworkConfig]):
    def __init__(self, network_id: str):
        self.network_id = network_id

    def preprocess(self, config: Config | None) -> NetworkConfig | None:
        if config is None:
            return None
        return config.networks.get(self.network_id)


class MonitorStatusTableHandler(UpdateHandler):
    """Handles monitor status updates."""

    def __init__(self, event_log: EventLog):
        self.event_log = event_log
        self._matcher = RegexPathMatcher(
            [
                "nodes\\..+\\.contexts.monitor_data\\..+$",
                "nodes\\..+\\.contexts.monitor_data$",
            ]
        )
        self.logger = structlog.get_logger().bind(
            module="meshmon.update_handlers", component="MonitorStatusTableHandler"
        )

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.store = store
        self.update_manager = update_manager

    def get_monitor_status(self) -> dict[str, DSMonitorStatus]:
        status_value_mapping = {
            DSObjectStatus.ONLINE: 3,
            DSObjectStatus.OFFLINE: 2,
            DSObjectStatus.UNKNOWN: 1,
        }
        now = datetime.datetime.now(datetime.timezone.utc)
        statuses: dict[str, DSMonitorStatus] = {}
        for node in self.store.nodes:
            monitor_ctx = self.store.get_context("monitor_data", DSMonitorData, node)
            if monitor_ctx is None:
                continue
            for _, monitor_data in monitor_ctx:
                mon_id = monitor_data.get_uid()
                if mon_id not in statuses:
                    statuses[mon_id] = DSMonitorStatus(
                        group=monitor_data.group,
                        name=monitor_data.name,
                        status=DSObjectStatus.UNKNOWN,
                        last_updated=monitor_data.date,
                    )

                if now - monitor_data.date < datetime.timedelta(
                    seconds=monitor_data.retry * monitor_data.interval
                ):
                    status = monitor_data.status
                else:
                    status = DSObjectStatus.OFFLINE
                if (
                    status_value_mapping[status]
                    > status_value_mapping[statuses[mon_id].status]
                ):
                    statuses[mon_id].status = status

        return statuses

    def handle_update(self) -> None:
        """Process an incoming update request."""
        # Implementation for handling updates and updating the status table
        target_statuses = self.get_monitor_status()
        status_ctx = self.store.get_context("monitor_status", DSMonitorStatus)
        for node_id, status_data in target_statuses.items():
            current_status = status_ctx.get(node_id)
            if current_status is None or current_status.status != status_data.status:
                status_ctx.set(
                    node_id,
                    status_data,
                )
                if status_data.status == DSObjectStatus.OFFLINE:
                    self.event_log.log_event(
                        EventType.WARNING,
                        EventID(
                            mid="monitor_offline",
                            src="MonitorStatusTableHandler",
                            network_id=self.store.network_id,
                            uid=node_id,
                        ),
                        f"Monitor {node_id} is not reporting status.",
                        f"Monitor {node_id} is offline",
                    )
                elif status_data.status == DSObjectStatus.ONLINE:
                    self.event_log.clear_event(
                        mid="monitor_offline",
                        network_id=self.store.network_id,
                        uid=node_id,
                    )
                self.update_manager.trigger_event("update")
        for node_id, _ in list(status_ctx):
            if node_id not in target_statuses:
                status_ctx.delete(node_id)
                self.event_log.clear_event(
                    mid="monitor_offline",
                    network_id=self.store.network_id,
                    uid=node_id,
                )
                self.update_manager.trigger_event("update")

    def stop(self) -> None:
        pass

    def matcher(self) -> RegexPathMatcher:
        return self._matcher

    def reload(self, new_config: NetworkConfig) -> None:
        self.logger.info(
            "Config reload triggered for MonitorStatusTableHandler",
            network_id=new_config.network_id,
            monitor_count=len(new_config.monitors),
        )
        self.network_config = new_config
        self.logger.debug(
            "MonitorStatusTableHandler config updated successfully",
            network_id=new_config.network_id,
        )
