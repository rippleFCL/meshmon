from analysis.analysis import analyze_all_networks, Status
from meshmon.distrostore import StoreManager
from meshmon.config import NetworkConfigLoader
import threading
import logging
import datetime


logger = logging.getLogger("meshmon.webhooks")


class WebhookHandler:
    def __init__(self, store_manager: StoreManager, config: NetworkConfigLoader):
        self.store_manager = store_manager
        self.config = config
        self.node_status = {}
        self.flag = threading.Event()
        self.thread = threading.Thread(target=self.webhook_thread, daemon=True)
        self.thread.start()

    def webhook_thread(self):
        while True:
            network_data = analyze_all_networks(self.store_manager, self.config)
            for network_id, analysis in network_data.networks.items():
                for node_id, node_analysis in analysis.node_analyses.items():
                    if (network_id, node_id) not in self.node_status:
                        if node_analysis.outbound_info or node_analysis.inbound_info:
                            self.node_status[(network_id, node_id)] = (
                                node_analysis.node_status
                            )
                        continue
                    if (
                        self.node_status[(network_id, node_id)]
                        != node_analysis.node_status
                    ):
                        logger.info(
                            f"Node {node_id} in network {network_id} status changed to {node_analysis.node_status}"
                        )
                        self.handle_webhook(
                            network_id, node_id, node_analysis.node_status
                        )
                        self.node_status[(network_id, node_id)] = (
                            node_analysis.node_status
                        )
            val = self.flag.wait(1)
            if val:
                break

    def stop(self):
        self.flag.set()
        self.thread.join()

    def handle_webhook(self, network_id: str, node_id: str, status: Status):
        if self.config.node_cfg.discord_webhook:
            import requests

            webhook_url = self.config.node_cfg.discord_webhook

            # Enhanced status mapping with better colors and emojis
            status_info = {
                Status.ONLINE: {
                    "color": 0x00FF54,  # Brighter green
                    "emoji": "🟢",
                    "description": "Node is now operational and responding",
                    "severity": "✅ Resolved",
                },
                Status.OFFLINE: {
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
            description = f"{current_status['description']}\n\n**Network:** `{network_id}`, **Node:** `{node_id}`"
            timestamp = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
            embed = {
                "title": title,
                "description": description,
                "color": current_status["color"],
                "fields": [
                    {
                        "name": "⏰ Event Time",
                        "value": f"<t:{timestamp}:F>\n<t:{timestamp}:R>",
                    },
                ],
                "timestamp": datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat(),
                "footer": {
                    "text": "Meshmon Network Monitor • Automated Status Update",
                    "icon_url": "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/Globe%20with%20meridians/3D/globe_with_meridians_3d.png",
                },
                "author": {
                    "name": "Meshmon",
                    "icon_url": "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/Chart%20increasing/3D/chart_increasing_3d.png",
                },
            }

            # Add thumbnail based on status
            if status == Status.ONLINE:
                embed["thumbnail"] = {
                    "url": "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/Check%20mark/3D/check_mark_3d.png"
                }
            elif status == Status.OFFLINE:
                embed["thumbnail"] = {
                    "url": "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/Cross%20mark/3D/cross_mark_3d.png"
                }

            data = {"embeds": [embed]}

            try:
                response = requests.post(webhook_url, json=data, timeout=10)
                if response.status_code != 204:
                    logger.error(
                        f"Failed to send webhook for node {node_id} in network {network_id}: {response.status_code} {response.text}"
                    )
                else:
                    logger.info(
                        f"Successfully sent webhook notification for {node_id} status change to {status.value}"
                    )
            except requests.exceptions.Timeout:
                logger.error(
                    f"Webhook request timed out for node {node_id} in network {network_id}"
                )
            except requests.exceptions.RequestException as e:
                logger.error(
                    f"Network error while sending webhook for node {node_id} in network {network_id}: {e}"
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error while sending webhook for node {node_id} in network {network_id}: {e}"
                )
