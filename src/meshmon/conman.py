import threading
import time

from server import PingData
from .config import NetworkConfigLoader
from .distrostore import StoreManager
from .monitor import MonitorManager
import logging

logger = logging.getLogger("meshmon.conman")


class ConfigManager:
    def __init__(
        self,
        config: NetworkConfigLoader,
        stores: StoreManager,
        monitors: MonitorManager,
    ):
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
                    self.monitor_manager.stop()
                    self.config.reload()
                    self.store_manager.reload()
                    for network_id, network in self.config.networks.items():
                        store = self.store_manager.get_store(network_id)
                        ctx = store.get_context("ping_data", PingData)
                        ctx.allowed_keys = list(network.key_mapping.verifiers.keys())
                    self.monitor_manager.reload()
            except Exception as e:
                logger.error(f"Error in config watcher: {e}")
