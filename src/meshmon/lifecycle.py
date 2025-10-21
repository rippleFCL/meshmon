import threading

from structlog.stdlib import get_logger

from .config.bus import ConfigBus
from .config.config import NetworkConfigLoader
from .connection.grpc_server import GrpcServer
from .connection.heartbeat import HeartbeatController
from .distrostore import StoreManager
from .monitor.manager import MonitorManager
from .webhooks import WebhookManager


class LifecycleManager:
    def __init__(
        self,
        config: NetworkConfigLoader,
        webhooks: WebhookManager,
        stores: StoreManager,
        grpc_server: GrpcServer,
        monitor_manager: MonitorManager,
        heartbeat_controller: HeartbeatController,
        config_bus: ConfigBus,
    ):
        self.heartbeat_controller = heartbeat_controller
        self.logger = get_logger().bind(
            module="meshmon.lifecycle", component="LifecycleManager"
        )
        self.grpc_server = grpc_server
        self.config = config
        self.store_manager = stores
        self.webhook_manager = webhooks
        self.monitor_manager = monitor_manager
        self.config_bus = config_bus
        # self.monitor_manager = monitors
        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self.watcher, name="lifecycle-manager")

    def watcher(self):
        self.logger.info("Starting lifecycle manager watcher thread")
        while not self._stop_event.is_set():
            try:
                if self.config.needs_reload():
                    new_config = self.config.load()
                    if new_config:
                        self.logger.info(
                            "Configuration change detected, reloading components"
                        )
                        self.config_bus.new_config(new_config)
                    else:
                        self.logger.error("Failed to load new configuration")

            except Exception as exc:
                self.logger.error("Error in config watcher", exc_info=exc)
            if self._stop_event.wait(10):
                break

    def start(self):
        self.heartbeat_controller.start()
        self.webhook_manager.start()
        self.grpc_server.start()
        self.monitor_manager.start()
        self.thread.start()

    def stop(self):
        self._stop_event.set()
        if self.thread.is_alive():
            self.thread.join()

        self.heartbeat_controller.stop()
        self.webhook_manager.stop()
        self.grpc_server.stop()
        self.monitor_manager.stop()
