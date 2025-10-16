import time
from threading import Event, Thread
from typing import TYPE_CHECKING

import structlog

from meshmon.pulsewave.update.update import UpdateMatcher

from ...config.bus import ConfigWatcher
from ..store import PulseWaveConfig
from .update import ExactPathMatcher, UpdateHandler, UpdateManager

if TYPE_CHECKING:
    from ..store import SharedStore


class RateLimitedHandler(UpdateHandler):
    def __init__(
        self, handler: UpdateHandler, config_watcher: "ConfigWatcher[PulseWaveConfig]"
    ):
        self.config_watcher = config_watcher
        self.min_interval = self.config_watcher.current_config.update_rate_limit
        self.config_watcher.subscribe(self.reload)
        self.handler = handler
        self.trigger = Event()
        self.stop_event = Event()
        self._matcher = ExactPathMatcher("update")
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.pulsewave.update.events", component="RateLimitedHandler"
        )

    def reload(self, new_config: PulseWaveConfig) -> None:
        self.logger.info(
            "Config reload triggered for RateLimitedHandler",
            old_interval=self.min_interval,
            new_interval=new_config.update_rate_limit,
        )
        self.min_interval = new_config.update_rate_limit
        self.logger.debug("RateLimitedHandler config updated successfully")

    def _handler_loop(self):
        self.logger.debug("RateLimitedHandler loop started")
        while self.stop_event.is_set() is False:
            if self.trigger.wait(1):
                self.trigger.clear()
                self.handler.handle_update()
                time.sleep(self.min_interval)

    def stop(self) -> None:
        self.logger.info("Stopping RateLimitedHandler")
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join()

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.handler.bind(store, update_manager)
        self.thread = Thread(target=self._handler_loop, name="rate-limited-handler")
        self.thread.start()

    def handle_update(
        self,
    ) -> None:
        self.logger.debug("RateLimitedHandler triggered")
        self.trigger.set()

    def matcher(self) -> UpdateMatcher:
        return self._matcher
