import re
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING, Protocol

import structlog

if TYPE_CHECKING:
    from ..store import SharedStore


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


class UpdateHandler(Protocol):
    def bind(self, store: "SharedStore", update_manager: "UpdateManager") -> None: ...

    def handle_update(self) -> None: ...

    def stop(self) -> None: ...

    def matcher(self) -> UpdateMatcher: ...


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
        self.handlers: list[UpdateHandler] = []
        self.handler_cache: dict[str, list[UpdateHandler]] = {}
        self.current_matchers: list[UpdateMatcher] = []

    def handle(self, events: list[str]) -> None:
        execute_handlers = []
        updated = False
        for handler in self.handlers:
            if handler.matcher() not in self.current_matchers:
                self.current_matchers.append(handler.matcher())
                updated = True

        if updated:  # Clear handler cache if matchers have changed
            self.handler_cache.clear()

        for event in events:
            handlers = []
            if event in self.handler_cache:
                for handler in self.handler_cache[event]:
                    handler.handle_update()

            for handler in self.handlers:
                matcher = handler.matcher()
                if matcher.matches(event):
                    handlers.append(handler)
                    if handler not in execute_handlers:
                        execute_handlers.append(handler)
            self.handler_cache[event] = handlers

        for handler in execute_handlers:
            handler.handle_update()

    def stop(self) -> None:
        for handler in self.handlers:
            handler.stop()

    def add(self, handler: UpdateHandler):
        self.handlers.append(handler)
        self.handler_cache.clear()


class UpdateManager:
    def __init__(
        self,
        store: "SharedStore",
    ):
        self.logger = structlog.stdlib.get_logger().bind(
            module="meshmon.pulsewave.update.update", component="UpdateManager"
        )
        self.event_queue = DedupeQueue()
        self.event_controller = UpdateController()
        self.idle = Event()

        self.update_queue = DedupeQueue()
        self.update_controller = UpdateController()

        self.store = store
        self.update_thread: Thread = Thread(
            target=self.looped_executor,
            args=(self.update_loop,),
            name="update-loop",
        )
        self.event_thread: Thread = Thread(
            target=self.looped_executor,
            args=(self.event_loop,),
            name="event-loop",
        )
        self.stop_event: Event = Event()

    def add_handler(self, handler: UpdateHandler):
        handler.bind(self.store, self)
        self.update_controller.add(handler)

    def add_event_handler(self, handler: UpdateHandler):
        handler.bind(self.store, self)
        self.event_controller.add(handler)

    def trigger_update(self, path: list[str]):
        self.idle.clear()
        self.update_queue.add(path)

    def trigger_event(self, event: str):
        self.event_queue.add([event])

    def event_loop(self):
        if self.event_queue.wait_for_items(1):
            events = self.event_queue.pop_all()
            if not self.idle.wait():
                return
            self.logger.debug("Processing events", event_ids=events)
            self.event_controller.handle(events)

    def update_loop(self):
        if self.update_queue.wait_for_items(1):
            while True:
                paths = self.update_queue.pop_all()
                self.logger.debug("Processing updates", path_ids=paths)
                self.update_controller.handle(paths)
                if self.update_queue.empty:
                    break
        self.idle.set()

    def looped_executor(self, func):
        while self.stop_event.is_set() is False:
            func()

    def wait_until_idle(self, timeout: float | None = None) -> bool:
        return self.idle.wait(timeout)

    def stop(self):
        self.logger.info("Stopping update manager")
        self.stop_event.set()
        self.idle.set()
        if self.update_thread.is_alive():
            self.update_thread.join()
        if self.event_thread.is_alive():
            self.event_thread.join()
        self.update_controller.stop()
        self.event_controller.stop()

    def start(self):
        self.update_thread.start()
        self.event_thread.start()
