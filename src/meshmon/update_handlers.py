import datetime

from pydantic import BaseModel

from meshmon.config import NetworkConfig

from .analysis.analysis import (
    AnalysisNodeStatus,
    get_monitor_status,
    get_node_ping_status,
)
from .pulsewave.store import SharedStore
from .pulsewave.update.update import RegexPathMatcher, UpdateHandler, UpdateManager


class NodeStatusEntry(BaseModel):
    status: AnalysisNodeStatus
    last_updated: datetime.datetime


class NodeStatusTable(UpdateHandler):
    """Handles node status updates."""

    def __init__(self): ...

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


def get_node_status_handler() -> tuple[RegexPathMatcher, NodeStatusTable]:
    matches = [
        "nodes\\.(\\w|-)+\\.contexts.ping_data\\.(\\w|-)+$",
    ]
    return RegexPathMatcher(matches), NodeStatusTable()


# hello future ripple :3 impliment the monitor version of this here!
class MonitorStatusTable(UpdateHandler):
    """Handles monitor status updates."""

    def __init__(self, config: NetworkConfig):
        self.config = config

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.store = store
        self.update_manager = update_manager

    def handle_update(self) -> None:
        """Process an incoming update request."""
        # Implementation for handling updates and updating the status table
        status = get_monitor_status(self.store, self.config)
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


def get_monitor_status_handler(
    config: NetworkConfig,
) -> tuple[RegexPathMatcher, MonitorStatusTable]:
    matches = [
        "nodes\\.(\\w|-)+\\.contexts.monitor_data\\.(\\w|-)+$",
    ]
    return RegexPathMatcher(matches), MonitorStatusTable(config)
