import threading
from typing import Any, Callable, Protocol

import structlog

from .config import Config


class ConfigPreprocessor[T: Any](Protocol):
    def preprocess(self, config: Config | None) -> T | None: ...


class ConfigWatcher[T: Any = Config]:
    def __init__(self, preprocessor: ConfigPreprocessor[T], initial_config: T):
        self.preprocessor = preprocessor
        self.lock = threading.RLock()
        self.current_config = initial_config
        self.subscribers: list[Callable[[T], None]] = []
        self.logger = structlog.get_logger().bind(
            module="meshmon.config.bus",
            component="ConfigWatcher",
            preprocessor=preprocessor.__class__.__name__,
        )

    def subscribe(self, callback: Callable[[T], None]) -> None:
        with self.lock:
            self.subscribers.append(callback)
            self.logger.debug(
                "Subscriber registered",
                callback=callback.__name__
                if hasattr(callback, "__name__")
                else str(callback),
                total_subscribers=len(self.subscribers),
            )

    def new_config(self, config: Config) -> bool:
        self.logger.debug("Processing new config through preprocessor")
        new_config = self.preprocessor.preprocess(config)
        if new_config is None:
            self.logger.debug("Preprocessor returned None, watcher will be removed")
            return False
        with self.lock:
            self.logger.debug(
                "Notifying subscribers of config change",
                subscriber_count=len(self.subscribers),
            )
            for callback in self.subscribers:
                callback_name = (
                    callback.__name__
                    if hasattr(callback, "__name__")
                    else str(callback)
                )
                self.logger.debug("Calling subscriber", callback=callback_name)
                try:
                    callback(new_config)
                    self.logger.debug(
                        "Subscriber completed successfully", callback=callback_name
                    )
                except Exception as e:
                    self.logger.error(
                        "Subscriber callback failed",
                        callback=callback_name,
                        error=str(e),
                        exc_info=True,
                    )
        return True


class ConfigBus:
    def __init__(self):
        self.lock = threading.RLock()
        self.watchers: list[ConfigWatcher[Any]] = []
        self.config: Config | None = None
        self.logger = structlog.get_logger().bind(
            module="meshmon.config.bus", component="ConfigBus"
        )

    def get_watcher[T](
        self, preprocessor: ConfigPreprocessor[T]
    ) -> ConfigWatcher[T] | None:
        with self.lock:
            preprocessor_name = preprocessor.__class__.__name__
            self.logger.debug(
                "Creating new watcher",
                preprocessor=preprocessor_name,
            )
            initial_config = preprocessor.preprocess(self.config)
            if initial_config is None:
                self.logger.warning(
                    "Preprocessor returned None, watcher creation failed",
                    preprocessor=preprocessor_name,
                )
                return
            watcher = ConfigWatcher(preprocessor, initial_config)
            self.watchers.append(watcher)
            self.logger.debug(
                "Watcher created successfully",
                preprocessor=preprocessor_name,
                total_watchers=len(self.watchers),
            )
            return watcher

    @property
    def loaded(self) -> bool:
        with self.lock:
            return self.config is not None

    def new_config(self, config: Config):
        with self.lock:
            self.logger.info(
                "Processing new config",
                watcher_count=len(self.watchers),
            )
            self.config = config
            to_remove = []
            for watcher in self.watchers:
                preprocessor_name = watcher.preprocessor.__class__.__name__
                self.logger.debug(
                    "Updating watcher with new config",
                    preprocessor=preprocessor_name,
                )
                if not watcher.new_config(config):
                    self.logger.debug(
                        "Watcher returned False, marking for removal",
                        preprocessor=preprocessor_name,
                    )
                    to_remove.append(watcher)

            for watcher in to_remove:
                preprocessor_name = watcher.preprocessor.__class__.__name__
                self.watchers.remove(watcher)
                self.logger.info(
                    "Watcher removed",
                    preprocessor=preprocessor_name,
                    remaining_watchers=len(self.watchers),
                )
