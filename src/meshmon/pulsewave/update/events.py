import time
from threading import Event, Thread
from typing import TYPE_CHECKING

import structlog

from .update import UpdateHandler, UpdateManager

if TYPE_CHECKING:
    from ..store import SharedStore


class LocalStores:
    def __init__(self):
        self.stores: dict[str, "SharedStore"] = {}
        self.logger = structlog.stdlib.get_logger().bind(module="pulsewave.callbacks")

    def add_store(self, store: "SharedStore"):
        node_id = store.key_mapping.signer.node_id
        self.stores[node_id] = store
        self.logger.info("Store added", node_id=node_id)

    def __iter__(self):
        return iter(self.stores.items())


class LocalHandler(UpdateHandler):
    def __init__(self, stores: LocalStores):
        self.stores = stores
        self.logger = structlog.stdlib.get_logger().bind(module="pulsewave.callbacks")

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.store = store

    def handle_update(
        self,
    ) -> None:
        current_node_id = self.store.key_mapping.signer.node_id
        self.logger.debug("LocalHandler handling update", src_id=current_node_id)

        for node_id, node_store in self.stores:
            if node_id == current_node_id:
                continue
            self.logger.debug(
                "Sending to store", node_id=node_id, src_id=current_node_id
            )
            data = self.store.dump()
            node_store.update_from_dump(data)


class RateLimitedHandler(UpdateHandler):
    def __init__(self, handler: UpdateHandler, min_interval: float):
        self.handler = handler
        self.min_interval = min_interval
        self.trigger = Event()
        self.logger = structlog.stdlib.get_logger().bind(module="pulsewave.callbacks")

    def _handler_loop(self):
        self.logger.debug("RateLimitedHandler loop started")
        while True:
            self.trigger.wait()
            self.trigger.clear()
            self.handle_update()
            time.sleep(self.min_interval)

    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None:
        self.handler.bind(store, update_manager)
        thread = Thread(target=self._handler_loop, daemon=True)
        thread.start()

    def handle_update(
        self,
    ) -> None:
        self.logger.debug("RateLimitedHandler triggered")
        self.trigger.set()
