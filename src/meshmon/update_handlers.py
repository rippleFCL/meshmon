import datetime

from pydantic import BaseModel

from meshmon.config.bus import ConfigPreprocessor, ConfigWatcher

from .analysis.analysis import (
    AnalysisNodeStatus,
    get_monitor_status,
    get_node_ping_status,
)
from .config.config import Config, NetworkConfig
from .pulsewave.store import SharedStore
from .pulsewave.update.update import RegexPathMatcher, UpdateHandler, UpdateManager


class NodeStatusEntry(BaseModel):
    status: AnalysisNodeStatus
    last_updated: datetime.datetime


class NodeStatusTableHandler(UpdateHandler):
    """Handles node status updates."""

    def __init__(self):
        self._matcher = RegexPathMatcher(
            [
                "nodes\\.(\\w|-)+\\.contexts.ping_data\\.(\\w|-)+$",
            ]
        )

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        """Process an incoming update request."""
        # Implementation for handling updates and updating the status table
        status = get_node_ping_status(self.store)
        status_ctx = self.store.get_context("node_status", NodeStatusEntry)
        for node_id, status in status.items():
            current_status = status_ctx.get(node_id)
            if current_status is None or current_status.status != status:
                status_ctx.set(
                    node_id,
                    NodeStatusEntry(
                        status=status,
                        last_updated=datetime.datetime.now(datetime.timezone.utc),
                    ),
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

    def __init__(self, config_watcher: ConfigWatcher[NetworkConfig]):
        self.config_watcher = config_watcher
        self._matcher = RegexPathMatcher(
            [
                "nodes\\.(\\w|-)+\\.contexts.monitor_data\\.(\\w|-)+$",
            ]
        )
        self.network_config = self.config_watcher.current_config
        self.config_watcher.subscribe(self.reload)

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        """Process an incoming update request."""
        if not self.network_config:
            return
        # Implementation for handling updates and updating the status table
        status = get_monitor_status(self.store, self.network_config)
        status_ctx = self.store.get_context("monitor_status", NodeStatusEntry)
        for node_id, status in status.items():
            current_status = status_ctx.get(node_id)
            if current_status is None or current_status.status != status:
                status_ctx.set(
                    node_id,
                    NodeStatusEntry(
                        status=status,
                        last_updated=datetime.datetime.now(datetime.timezone.utc),
                    ),
                )
                self.update_manager.trigger_event("update")

    def stop(self) -> None:
        pass

    def matcher(self) -> RegexPathMatcher:
        return self._matcher

    def reload(self, new_config: NetworkConfig) -> None:
        self.network_config = new_config
