import datetime
import hashlib
import threading

import requests
from pydantic import BaseModel
from structlog.stdlib import get_logger

from .analysis.store import NodeStatus
from .config import NetworkConfigLoader
from .distrostore import StoreManager


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

    def _get_webhook(self, network_id: str) -> str | None:
        return self.config.networks[network_id].node_cfg.discord_webhook

    def _notify_for_network(self, network_id: str):
        # webhook = self._get_webhook(network_id)
        # if webhook is None:
        #     return
        # hashed_webhook = HashedWebhook.from_webhook(webhook)
        # store = self.store_manager.get_store(network_id)
        # analysis = store.get_consistency_context(
        #     hashed_webhook.hashed_webhook, AnalysedNodeStatus, webhook
        # )
        ...

    def webhook_thread(self):
        while True:
            for network_id in self.store_manager.stores:
                if self._get_webhook(network_id) is not None:
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
