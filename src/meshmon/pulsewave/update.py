import asyncio
import json
import time
from asyncio import Task
from threading import Thread
from typing import TYPE_CHECKING, Protocol

from meshmon.pulsewave.crypto import KeyMapping

from .config import NodeConfig, PulseWaveConfig
from .data import StoreData

if TYPE_CHECKING:
    from .store import SharedStore


class UpdateCallback(Protocol):
    async def handle_update(
        self, data: str, update_manager: "UpdateManager", node_cfg: NodeConfig
    ) -> bool: ...


class UpdateHandler(Protocol):
    def handle_update(
        self, store: StoreData, update_manager: "UpdateManager", node_cfg: NodeConfig
    ) -> None: ...


class IncrementalUpdater:
    def __init__(self):
        self.end_data = StoreData()

    def diff(self, other: StoreData) -> StoreData:
        return self.end_data.diff(other)

    def update(self, other: StoreData, key_mapping: KeyMapping) -> bool:
        return self.end_data.update(other, key_mapping)

    def clear(self):
        self.end_data = StoreData()


class UpdateManager:
    def __init__(
        self,
        callback: UpdateCallback,
        handler: UpdateHandler,
        db_config: PulseWaveConfig,
        store: "SharedStore",
    ):
        self.callback = callback
        self.handler = handler
        self.db_config = db_config
        self.store = store
        self.rate_limit = db_config.update_rate_limit
        # Per-node events and tasks
        self.node_update_events: dict[str, asyncio.Event] = {}
        self.node_tasks: dict[str, Task] = {}
        self.node_incremental_handlers: dict[str, IncrementalUpdater] = {
            node_id: IncrementalUpdater() for node_id in db_config.nodes.keys()
        }
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        self._start_node_tasks()

    def _start_node_tasks(self):
        """Start a dedicated task for each node"""
        for node_cfg in self.db_config.nodes.values():
            node_id = node_cfg.node_id
            self.node_update_events[node_id] = asyncio.Event()
            self.node_tasks[node_id] = self.loop.create_task(
                self._node_update_loop(node_cfg)
            )

    async def _node_update_loop(self, node_cfg: NodeConfig):
        """Dedicated update loop for a single node with rate limiting"""
        node_id = node_cfg.node_id
        last_update_time = 0.0
        update_event = self.node_update_events[node_id]
        increment_handler = self.node_incremental_handlers[node_id]
        while True:
            # Wait for an update event
            await update_event.wait()

            # Clear the event
            update_event.clear()
            self.handler.handle_update(self.store.store, self, node_cfg)
            # Apply rate limiting
            current_time = time.time()

            # Get fresh data and send update
            data = increment_handler.diff(self.store.store).model_dump(mode="json")
            try:
                update_success = await self.callback.handle_update(
                    json.dumps(data), self, node_cfg
                )
                if update_success:
                    increment_handler.update(
                        StoreData.model_validate(data), self.db_config.key_mapping
                    )
                else:
                    increment_handler.clear()
            except Exception as e:
                # Log error but continue with other nodes
                print(f"Error updating node {node_cfg.node_id}: {e}")

            time_since_last = current_time - last_update_time
            last_update_time = time.time()

            if time_since_last < self.rate_limit:
                await asyncio.sleep(self.rate_limit - time_since_last)

    async def handle_update(self):
        """Trigger updates for all nodes by setting their events"""
        for event in self.node_update_events.values():
            event.set()

    async def handle_instant_update(self):
        """Instant update that calls the callback on all nodes without rate limiting"""

        # Call update callback on all nodes
        for node_cfg in self.db_config.nodes.values():
            self.handler.handle_update(self.store.store, self, node_cfg)
            increment_handler = self.node_incremental_handlers[node_cfg.node_id]
            data = increment_handler.diff(self.store.store).model_dump_json()
            try:
                updates_succeeded = await self.callback.handle_update(
                    data, self, node_cfg
                )
                if updates_succeeded:
                    increment_handler.update(
                        StoreData.model_validate(data), self.db_config.key_mapping
                    )
                else:
                    increment_handler.clear()
            except Exception as e:
                # Log error but continue with other nodes
                print(f"Error updating node {node_cfg.node_id}: {e}")

    async def handle_data_update(self):
        """Triggers a rate-limited update and returns instantly. Sets flags for all nodes."""
        self.loop.create_task(self.handle_update())

    async def handle_instant_data_update(self):
        """Triggers an instant update and returns instantly"""
        # Schedule the instant update task
        self.loop.create_task(self.handle_instant_update())

    def update(self, data: StoreData):
        """Triggers a rate-limited update and returns instantly. Sets flags for all nodes."""
        diff = self.store.store.diff(data)
        instant_update = False
        for node_id, node_diff in diff.nodes.items():
            if node_diff.consistency is None:
                continue
            instant_update = True
        self.store.store.update(data, self.db_config.key_mapping)
        if instant_update:
            asyncio.run_coroutine_threadsafe(
                self.handle_instant_data_update(), self.loop
            )
        else:
            asyncio.run_coroutine_threadsafe(self.handle_data_update(), self.loop)

    def cleanup(self):
        """Cancel all node tasks - call when shutting down"""
        for task in self.node_tasks.values():
            if not task.done():
                task.cancel()
