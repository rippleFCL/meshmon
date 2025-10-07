import datetime
import hashlib
import threading

import requests
from pydantic import BaseModel
from structlog.stdlib import get_logger

from .analysis.store import NodeStatus
from .config import NetworkConfigLoader
from .distrostore import StoreManager
from .monitor import AnalysedNodeStatus


class HashedWebhook(BaseModel):
    hashed_webhook: str

    @classmethod
    def from_webhook(cls, webhook: str) -> "HashedWebhook":
        hashed = hashlib.sha256(webhook.encode()).hexdigest()
        return cls(hashed_webhook=hashed)


class LastNotification(BaseModel):
    timestamp: datetime.datetime


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

    def _cluster_agrees(self, network_id: str) -> bool:
        store = self.store_manager.stores[network_id]
        local_analysis = store.get_context("network_analysis", AnalysedNodeStatus)
        online_nodes = 0

        for node_id in store.nodes:
            remote_status = store.get_context(
                "network_analysis", AnalysedNodeStatus, node_id
            )
            if remote_status is None:
                continue
            status = local_analysis.get(node_id)
            if status is None or status.status != NodeStatus.ONLINE:
                continue
            for peer_id, status in remote_status:
                local_status = local_analysis.get(peer_id)
                if local_status is None or local_status.status != status.status:
                    return False
            online_nodes += 1
        if online_nodes == 1:
            return False

        return True

    def _get_webhook(self, network_id: str) -> str | None:
        return self.config.networks[network_id].node_cfg.discord_webhook

    def _get_priority(self, node_id: str, network_id: str) -> int:
        for idx, node in enumerate(self.config.networks[network_id].node_config):
            if node.node_id == node_id:
                return idx
        return 0

    def leader_priority(
        self, network_id: str, exclude_self: bool = False
    ) -> tuple[str, int] | None:
        current_store = self.store_manager.get_store(network_id)
        current_hash = current_store.get_value("webhook_hash", HashedWebhook)
        current_analysis = current_store.get_context(
            "network_analysis", AnalysedNodeStatus
        )
        if current_hash is None:
            webhook = self._get_webhook(network_id)
            if not webhook:
                return None
            current_store.set_value("webhook_hash", HashedWebhook.from_webhook(webhook))
            current_hash = current_store.get_value("webhook_hash", HashedWebhook)
            if current_hash is None:
                return None

        current_node = current_store.key_mapping.signer.node_id
        current_priority = self._get_priority(current_node, network_id)
        nodes: list[tuple[str, int]] = [(current_node, current_priority)]
        for node_id in current_store.nodes:
            node_hash = current_store.get_value("webhook_hash", HashedWebhook, node_id)
            if (
                node_hash is not None
                and node_hash.hashed_webhook == current_hash.hashed_webhook
            ):
                current_priority = self._get_priority(node_id, network_id)
                node_status = current_analysis.get(node_id)
                if node_status is not None and node_status.status == NodeStatus.ONLINE:
                    nodes.append((node_id, current_priority))
        if exclude_self:
            nodes = [
                n for n in nodes if n[0] != current_store.key_mapping.signer.node_id
            ]
        if not nodes:
            return None
        nodes.sort(key=lambda x: x[1])
        leader_node, leader_priority = nodes[0]
        return leader_node, leader_priority

    def is_leader(self, network_id: str) -> bool:
        current_node = self.store_manager.get_store(
            network_id
        ).key_mapping.signer.node_id
        leader_priority = self.leader_priority(network_id)
        if leader_priority is None:
            return False
        return leader_priority[0] == current_node

    def _catchup(self, network_id: str):
        current_store = self.store_manager.get_store(network_id)
        next_leader = self.leader_priority(network_id, exclude_self=True)
        if next_leader is None:
            return
        leader_node, _ = next_leader
        leader_last_notification = current_store.get_value(
            "last_notification", LastNotification, leader_node
        )
        current_last_notification = current_store.get_value(
            "last_notification", LastNotification
        )
        leader_status = current_store.get_context(
            "last_notified_status", AnalysedNodeStatus, leader_node
        )
        if (
            leader_last_notification is None
            or current_last_notification is None
            or leader_status is None
        ):
            return
        if leader_last_notification.timestamp > current_last_notification.timestamp:
            current_status = current_store.get_context(
                "last_notified_status", AnalysedNodeStatus
            )
            self.logger.info(
                "Catching up to leader for network",
                leader_node=leader_node,
                net_id=network_id,
            )
            for node_id, status in leader_status:
                current_status.set(node_id, status)
            current_store.set_value("last_notification", leader_last_notification)

    def _notify_for_network(self, network_id: str):
        self.logger.debug("Processing notifications for network", net_id=network_id)
        current_store = self.store_manager.get_store(network_id)
        analysis_ctx = current_store.get_context("network_analysis", AnalysedNodeStatus)

        if self.is_leader(network_id):
            current_status = current_store.get_context(
                "last_notified_status", AnalysedNodeStatus
            )
            self.logger.debug("Acting as leader for network", net_id=network_id)
            self._catchup(network_id)
            updated = False
            for node_id, status in analysis_ctx:
                current_notified_status = current_status.get(node_id)
                if current_notified_status is not None:
                    if current_notified_status.status != status.status:
                        self.logger.info(
                            "Status change detected for node in network",
                            net_id=network_id,
                            node_id=node_id,
                            to=status.status,
                            **{"from": current_notified_status.status},
                        )
                        self.handle_webhook(network_id, node_id, status.status)
                        current_status.set(node_id, status)
                        updated = True
                else:
                    self.logger.debug(
                        "Setting initial status for node in network",
                        net_id=network_id,
                        node_id=node_id,
                        to=status.status,
                    )
                    current_status.set(node_id, status)
                    updated = True
            if updated:
                self.logger.debug(
                    "Updating network due to status changes", net_id=network_id
                )
                current_store.set_value(
                    "last_notification",
                    LastNotification(
                        timestamp=datetime.datetime.now(tz=datetime.timezone.utc)
                    ),
                )

            else:
                self.logger.debug(
                    "No status changes detected for network", net_id=network_id
                )
        elif (
            leader_data := self.leader_priority(network_id, exclude_self=True)
        ) is not None:
            leader_node, _ = leader_data
            self.logger.debug(
                "Following leader for network",
                leader_node=leader_node,
                net_id=network_id,
            )
            leader_status = current_store.get_context(
                "last_notified_status", AnalysedNodeStatus, leader_node
            )
            node_status = current_store.get_context(
                "last_notified_status", AnalysedNodeStatus
            )
            if leader_status is None:
                self.logger.info(
                    "No leader status found for leader in network",
                    leader_node=leader_node,
                    net_id=network_id,
                )
                return
            for node_id, status in leader_status:
                current_notified_status = node_status.get(node_id)
                if current_notified_status is not None:
                    if current_notified_status.status != status.status:
                        node_status.set(node_id, status)
                else:
                    node_status.set(node_id, status)

    def webhook_thread(self):
        while True:
            for network_id in self.store_manager.stores:
                if (
                    self._cluster_agrees(network_id)
                    and self._get_webhook(network_id) is not None
                ):
                    self._notify_for_network(network_id)
            val = self.flag.wait(1)
            if val:
                break

    def stop(self):
        self.flag.set()
        self.thread.join()

    def handle_webhook(self, network_id: str, node_id: str, status: NodeStatus):
        webhook = self._get_webhook(network_id)
        if webhook is not None:
            # Enhanced status mapping with better colors and emojis
            status_info = {
                NodeStatus.ONLINE: {
                    "color": 0x00FF54,  # Brighter green
                    "emoji": "🟢",
                    "description": "Node is now responding to pings",
                    "severity": "✅ Resolved",
                },
                NodeStatus.OFFLINE: {
                    "color": 0xFF4757,  # Modern red
                    "emoji": "🔴",
                    "description": "Node is not responding to pings",
                    "severity": "⚠️ Alert",
                },
            }

            current_status = status_info.get(
                status,
                {
                    "color": 0x747D8C,  # Gray for unknown
                    "emoji": "⚪",
                    "description": "Node status is unknown",
                    "severity": "❓ Unknown",
                },
            )

            # Create more informative title
            title = f"{current_status['emoji']} Node Status Change - {current_status['severity']}"

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
                        "name": "Node ID",
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
