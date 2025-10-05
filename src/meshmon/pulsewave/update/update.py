import re
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Protocol

import structlog

from ..config import PulseWaveConfig
from ..crypto import KeyMapping
from ..data import StoreData

if TYPE_CHECKING:
    from ..store import SharedStore


class UpdateHandler(Protocol):
    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None: ...

    def handle_update(self) -> None: ...


class IncrementalUpdater:
    def __init__(self):
        self.end_data = StoreData()

    def diff(self, other: StoreData, exclude_node_id: str) -> StoreData:
        diff = self.end_data.diff(other)
        if exclude_node_id in diff.nodes:
            del diff.nodes[exclude_node_id]
        return diff

    def update(self, other: StoreData, key_mapping: KeyMapping):
        self.end_data.update(other, key_mapping)

    def clear(self):
        self.end_data = StoreData()


class DedupeQueue:
    def __init__(self):
        self.queue = set()
        self.has_items = Event()
        self.lock = Lock()

    def add(self, items: list[str]):
        with self.lock:
            self.has_items.set()
            for item in items:
                self.queue.add(item)

    def pop_all(self) -> list[str]:
        with self.lock:
            self.has_items.clear()
            items = list(self.queue)
            self.queue.clear()
            return items

    def wait_for_items(self, timeout: float | None = None) -> bool:
        return self.has_items.wait(timeout)

    @property
    def empty(self) -> bool:
        return not self.has_items.is_set()


class UpdateMatcher(Protocol):
    def matches(self, name: str) -> bool: ...


class RegexPathMatcher:
    def __init__(self, pattern: list[str]):
        self.pattern = re.compile("|".join(pattern))

    def matches(self, name: str) -> bool:
        return bool(self.pattern.match(name))


class ExactPathMatcher:
    def __init__(self, path: str):
        self.path = path

    def matches(self, name: str) -> bool:
        return name == self.path


class UpdateController:
    def __init__(self):
        self.handlers: list[tuple[UpdateMatcher, UpdateHandler]] = []
        self.handler_cache: dict[str, list[UpdateHandler]] = {}

    def handle(
        self, event: str, store: "SharedStore", update_manager: "UpdateManager"
    ) -> None:
        if event in self.handler_cache:
            for handler in self.handler_cache[event]:
                handler.handle_update()

        handlers = []
        for matcher, handler in self.handlers:
            if matcher.matches(event):
                handlers.append(handler)
                handler.handle_update()
        self.handler_cache[event] = handlers

    def add(self, matcher: UpdateMatcher, handler: UpdateHandler):
        self.handlers.append((matcher, handler))
        self.handler_cache.clear()


class UpdateManager:
    def __init__(
        self,
        db_config: PulseWaveConfig,
        store: "SharedStore",
    ):
        self.logger = structlog.stdlib.get_logger().bind(module="pulsewave.update")
        self.event_queue = DedupeQueue()
        self.event_controller = UpdateController()
        self.idle = Event()

        self.update_queue = DedupeQueue()
        self.update_controller = UpdateController()

        self.db_config = db_config
        self.store = store
        self.thread: Thread = Thread(
            target=self.looped_executor, args=(self.update_loop,), daemon=True
        )
        self.thread.start()
        self.event_thread: Thread = Thread(
            target=self.looped_executor, args=(self.event_loop,), daemon=True
        )
        self.event_thread.start()

    def add_handler(self, matcher: UpdateMatcher, callback: UpdateHandler):
        callback.bind(self.store, self)
        self.update_controller.add(matcher, callback)

    def add_event_handler(self, matcher: UpdateMatcher, callback: UpdateHandler):
        callback.bind(self.store, self)
        self.event_controller.add(matcher, callback)

    def trigger_update(self, path: list[str]):
        self.logger.debug("Triggering update", path=path)
        self.idle.clear()
        self.update_queue.add(path)

    def trigger_event(self, event: str):
        self.logger.debug("Triggering event", event_id=event)
        self.event_queue.add([event])

    def event_loop(self):
        self.event_queue.wait_for_items()
        events = self.event_queue.pop_all()
        if not self.idle.wait():
            return
        for event in events:
            self.logger.debug("Processing event", event_id=event)
            self.event_controller.handle(event, self.store, self)

    def update_loop(self):
        self.update_queue.wait_for_items()
        while True:
            paths = self.update_queue.pop_all()
            for path in paths:
                self.logger.debug("Processing update", path_id=path)
                self.update_controller.handle(path, self.store, self)
            if self.update_queue.empty:
                break
        self.idle.set()

    def looped_executor(self, func):
        while True:
            func()

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        return self.idle.wait(timeout)

    def stop(self):
        self.logger.info("Stopping update manager")
        # TODO: Implement proper stopping mechanism


#     async def _node_update_loop(self, node_cfg: NodeConfig):
#         """Dedicated update loop for a single node with rate limiting"""
#         node_id = node_cfg.node_id
#         last_update_time = 0.0
#         update_event = self.node_update_events[node_id]
#         increment_handler = self.node_incremental_handlers[node_id]
#         while True:
#             # Wait for an update event
#             await update_event.wait()
#
#             # Clear the event
#             update_event.clear()
#             # Apply rate limiting
#             current_time = time.time()
#
#             # Get fresh data and send update
#             data = increment_handler.diff(self.store.store, node_id)
#             if data.nodes:
#                 try:
#                     update_success = await self.callback.handle_update(
#                         data.model_dump_json(),
#                         self,
#                         node_cfg,
#                         self.db_config.current_node,
#                     )
#                     if update_success:
#                         increment_handler.update(data, self.db_config.key_mapping)
#                     else:
#                         increment_handler.clear()
#                 except Exception as e:
#                     # Log error but continue with other nodes
#                     print(f"Error updating node {node_cfg.node_id}: {e}")
#
#             time_since_last = current_time - last_update_time
#             last_update_time = time.time()
#
#             if time_since_last < self.rate_limit:
#                 await asyncio.sleep(self.rate_limit - time_since_last)
