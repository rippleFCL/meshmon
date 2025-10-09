import threading
import time

from structlog.stdlib import get_logger

from .config import NetworkConfigLoader
from .distrostore import StoreManager

# from .monitor import MonitorManager

logger = get_logger()


class ConfigManager:
    def __init__(
        self,
        config: NetworkConfigLoader,
        stores: StoreManager,
    ):
        self.config = config
        self.store_manager = stores
        # self.monitor_manager = monitors
        self.thread = threading.Thread(target=self.watcher, daemon=True)
        self.thread.start()

    def watcher(self):
        while True:
            time.sleep(10)
            try:
                if self.config.needs_reload():
                    # self.monitor_manager.stop()
                    self.config.reload()
                    self.store_manager.reload()
                    # self.monitor_manager.reload()
            except Exception as exc:
                logger.error("Error in config watcher", exc=exc)
