import threading
from typing import Any, Callable, Protocol

from .config import Config


class ConfigPreprocessor[T: Any](Protocol):
    def preprocess(self, config: Config | None) -> T | None: ...


class ConfigWatcher[T: Any = Config]:
    def __init__(self, preprocessor: ConfigPreprocessor[T], initial_config: T):
        self.preprocessor = preprocessor
        self.lock = threading.RLock()
        self.current_config = initial_config
        self.subscribers: list[Callable[[T], None]] = []

    def subscribe(self, callback: Callable[[T], None]) -> None:
        with self.lock:
            self.subscribers.append(callback)

    def new_config(self, config: Config) -> bool:
        new_config = self.preprocessor.preprocess(config)
        if new_config is None:
            return False
        with self.lock:
            for callback in self.subscribers:
                callback(new_config)
        return True


class ConfigBus:
    def __init__(self):
        self.lock = threading.RLock()
        self.watchers: list[ConfigWatcher[Any]] = []
        self.config: Config | None = None

    def get_watcher[T](
        self, preprocessor: ConfigPreprocessor[T]
    ) -> ConfigWatcher[T] | None:
        with self.lock:
            initial_config = preprocessor.preprocess(self.config)
            if initial_config is None:
                return
            watcher = ConfigWatcher(preprocessor, initial_config)
            self.watchers.append(watcher)
            return watcher

    @property
    def loaded(self) -> bool:
        with self.lock:
            return self.config is not None

    def new_config(self, config: Config):
        with self.lock:
            self.config = config
            to_remove = []
            for watcher in self.watchers:
                if not watcher.new_config(config):
                    to_remove.append(watcher)

            for watcher in to_remove:
                self.watchers.remove(watcher)
