import datetime
import hashlib
import threading
from enum import Enum

import requests
from pydantic import BaseModel
from structlog.stdlib import get_logger

from meshmon.analysis.analysis import AnalysisNodeStatus
from meshmon.pulsewave.data import StoreNodeStatus
from meshmon.pulsewave.store import SharedStore

from .config import NetworkConfigLoader
from .distrostore import StoreManager
from .update_handlers import NodeStatusEntry


class WebhookType(Enum):
    NODE = "node"
    MONITOR = "monitor"


class HashedWebhook(BaseModel):
    hashed_webhook: str

    @classmethod
    def from_webhook(cls, webhook: str) -> "HashedWebhook":
        hashed = hashlib.sha256(webhook.encode()).hexdigest()
        return cls(hashed_webhook=hashed)


class WebhookHandler:
    def __init__(
        self,
        store_manager: StoreManager,
        config: NetworkConfigLoader,
    ):
        self.store_manager = store_manager
        self.config = config
        self.logger = get_logger()
        self.flag = threading.Event()
        self.thread = threading.Thread(target=self.webhook_thread, daemon=True)
        self.thread.start()
        self.session = requests.Session()

    def _get_webhook(self, network_id: str) -> str | None:
        return self.config.networks[network_id].node_cfg.discord_webhook

    def node_status_consistent(self, store: SharedStore) -> bool:
        node_status_ctx = store.get_context("node_status", NodeStatusEntry)
        node_status_table = store.get_consistency().node_status_table
        node_statuses = {}
        for node_id, ping_data in node_status_ctx:
            node_statuses[node_id] = ping_data.status
        for node_id in store.nodes:
            node_status = node_status_table.get(node_id)
            if node_status is None or node_status.status != StoreNodeStatus.ONLINE:
                continue
            ctx = store.get_context("node_status", NodeStatusEntry, node_id)
            if ctx is None:
                return False
            for other_node_id, other_status in ctx:
                current_node_status = node_statuses.get(other_node_id)
                if current_node_status is None:
                    return False
                if other_status.status != current_node_status:
                    return False
        return True

    def monitor_status_consistent(self, store: SharedStore) -> bool:
        monitor_status_ctx = store.get_context("monitor_status", NodeStatusEntry)
        node_status_table = store.get_consistency().node_status_table
        monitor_statuses = {}
        for node_id, monitor_data in monitor_status_ctx:
            monitor_statuses[node_id] = monitor_data.status
        for node_id in store.nodes:
            node_status = node_status_table.get(node_id)
            if node_status is None or node_status.status != StoreNodeStatus.ONLINE:
                continue
            ctx = store.get_context("monitor_status", NodeStatusEntry, node_id)
            if ctx is None:
                return False
            for other_monitor_id, other_status in ctx:
                current_node_status = monitor_statuses.get(other_monitor_id)
                if current_node_status is None:
                    return False
                if other_status.status != current_node_status:
                    return False
        return True

    def _notify_for_network(self, network_id: str, webhook: str):
        hashed_webhook = HashedWebhook.from_webhook(webhook)
        store = self.store_manager.get_store(network_id)
        notified_node_analysis = store.get_consistency_context(
            hashed_webhook.hashed_webhook, NodeStatusEntry, webhook
        )
        if notified_node_analysis.is_leader():
            if self.node_status_consistent(store):
                node_status = store.get_context("node_status", NodeStatusEntry)
                for node_id, status in node_status:
                    current_notified_status = notified_node_analysis.get(
                        f"node-{node_id}"
                    )
                    if status.status == AnalysisNodeStatus.UNKNOWN:
                        continue
                    if current_notified_status is None:
                        notified_node_analysis.set(f"node-{node_id}", status)
                    elif (
                        current_notified_status is not None
                        and current_notified_status.status != status.status
                    ):
                        notified_node_analysis.set(f"node-{node_id}", status)
                        self.handle_webhook(
                            network_id,
                            node_id,
                            status.status,
                            WebhookType.NODE,
                        )

            if self.monitor_status_consistent(store):
                monitor_status = store.get_context("monitor_status", NodeStatusEntry)
                for monitor_id, status in monitor_status:
                    current_notified_status: NodeStatusEntry | None = (
                        notified_node_analysis.get(f"monitor-{monitor_id}")
                    )
                    if status.status == AnalysisNodeStatus.UNKNOWN:
                        continue
                    if current_notified_status is None:
                        notified_node_analysis.set(f"monitor-{monitor_id}", status)
                    elif (
                        current_notified_status is not None
                        and current_notified_status.status != status.status
                    ):
                        notified_node_analysis.set(f"monitor-{monitor_id}", status)
                        self.handle_webhook(
                            network_id,
                            monitor_id,
                            status.status,
                            WebhookType.MONITOR,
                        )

    def webhook_thread(self):
        while True:
            for network_id in self.store_manager.stores:
                if webhook := self._get_webhook(network_id):
                    self._notify_for_network(network_id, webhook)
            val = self.flag.wait(5)
            if val:
                break

    def stop(self):
        self.flag.set()
        self.thread.join()

    def handle_webhook(
        self,
        network_id: str,
        node_id: str,
        status: AnalysisNodeStatus,
        webhook_type: WebhookType,
    ):
        webhook = self._get_webhook(network_id)
        name = {
            WebhookType.NODE: "Node",
            WebhookType.MONITOR: "Monitor",
        }.get(webhook_type, "Unknown")
        if webhook is not None:
            # Enhanced status mapping with better colors and emojis
            status_info = {
                AnalysisNodeStatus.ONLINE: {
                    "color": 0x00FF54,  # Brighter green
                    "emoji": "🟢",
                    "description": f"{name} is now responding to pings",
                    "severity": "✅ Resolved",
                },
                AnalysisNodeStatus.OFFLINE: {
                    "color": 0xFF4757,  # Modern red
                    "emoji": "🔴",
                    "description": f"{name} is not responding to pings",
                    "severity": "⚠️ Alert",
                },
            }

            current_status = status_info.get(
                status,
                {
                    "color": 0x747D8C,  # Gray for unknown
                    "emoji": "⚪",
                    "description": f"{name} status is unknown",
                    "severity": "❓ Unknown",
                },
            )

            # Create more informative title
            title = f"{current_status['emoji']} {name} Status Change - {current_status['severity']}"

            # Enhanced description with more context
            embed = {
                "title": title,
                "description": current_status["description"],
                "color": current_status["color"],
                "fields": [
                    {
                        "name": "Network",
                        "value": network_id,
                        "inline": True,
                    },
                    {
                        "name": f"{name} ID",
                        "value": node_id,
                        "inline": True,
                    },
                ],
                "timestamp": datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat(),
            }

            data = {"embeds": [embed]}

            try:
                response = self.session.post(webhook, json=data, timeout=10)
                if response.status_code != 204:
                    self.logger.error(
                        "Failed to send webhook for node in network",
                        node_id=node_id,
                        net_id=network_id,
                        status=response.status_code,
                        body=response.text,
                    )
                else:
                    self.logger.info(
                        "Successfully sent webhook notification for status change",
                        node_id=node_id,
                        status=status.value,
                    )
            except requests.exceptions.Timeout:
                self.logger.error(
                    "Webhook request timed out for node in network ",
                    node_id=node_id,
                    net_id=network_id,
                )
            except requests.exceptions.RequestException as exc:
                self.logger.error(
                    "Network error while sending webhook for node in network",
                    node_id=node_id,
                    net_id=network_id,
                    exc=exc,
                )
            except Exception as exc:
                self.logger.error(
                    "Unexpected error while sending webhook for node in network",
                    node_id=node_id,
                    net_id=network_id,
                    exc=exc,
                )
