import threading
import time
from .config import NetworkConfigLoader
from .distrostore import StoreManager
from .monitor import MonitorManager


class ConfigManager:
    def __init__(self, config: NetworkConfigLoader, stores: StoreManager, monitors: MonitorManager):
        self.config = config
        self.store_manager = stores
        self.monitor_manager = monitors
        self.thread = threading.Thread(target=self.watcher, daemon=True)
        self.thread.start()

    def watcher(self):
        while True:
            time.sleep(10)
            if self.config.needs_reload():
                self.config.reload()
                self.store_manager.reload()
                self.monitor_manager.reload()
