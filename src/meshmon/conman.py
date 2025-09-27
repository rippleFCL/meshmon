import threading
import time

from structlog.stdlib import get_logger

from .config import NetworkConfigLoader, get_all_monitor_names, get_pingable_nodes
from .monitor import MonitorManager
from .pulsewave.distrostore import PingData, StoreManager
from .update import UpdateManager
from .webhooks import AnalysedNodeStatus

logger = get_logger()


class ConfigManager:
    def __init__(
        self,
        config: NetworkConfigLoader,
        stores: StoreManager,
        monitors: MonitorManager,
        update_manager: UpdateManager,
    ):
        self.update_manager = update_manager
        self.config = config
        self.store_manager = stores
        self.monitor_manager = monitors
        self.thread = threading.Thread(target=self.watcher, daemon=True)
        self.thread.start()

    def watcher(self):
        while True:
            time.sleep(10)
            try:
                if self.config.needs_reload():
                    self.update_manager.stop()
                    self.monitor_manager.stop()
                    self.config.reload()
                    self.store_manager.reload()
                    for network_id, network in self.config.networks.items():
                        store = self.store_manager.get_store(network_id)
                        ctx = store.get_context("ping_data", PingData)
                        ctx.allowed_keys = get_pingable_nodes(network)
                        ctx = store.get_context(
                            "last_notified_status", AnalysedNodeStatus
                        )
                        ctx.allowed_keys = list(network.key_mapping.verifiers.keys())
                        ctx = store.get_context("network_analysis", AnalysedNodeStatus)
                        ctx.allowed_keys = list(network.key_mapping.verifiers.keys())
                        ctx = store.get_context("monitor_data", PingData)
                        ctx.allowed_keys = get_all_monitor_names(
                            network, store.key_mapping.signer.node_id
                        )
                        ctx = store.get_context("monitor_analysis", AnalysedNodeStatus)
                        ctx.allowed_keys = get_all_monitor_names(
                            network, store.key_mapping.signer.node_id
                        )

                    self.monitor_manager.reload()
                    self.update_manager.reload()
            except Exception as exc:
                logger.error("Error in config watcher", exc=exc)
