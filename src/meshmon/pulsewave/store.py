from typing import Iterator, overload

import structlog
from pydantic import BaseModel

from meshmon.config.bus import ConfigWatcher

from .config import PulseWaveConfig
from .data import (
    DateEvalType,
    SignedBlockData,
    StoreConsistencyData,
    StoreContextData,
    StoreData,
    StoreNodeData,
)
from .secrets import SecretContainer
from .update.events import RateLimitedHandler
from .update.handlers import (
    ClockTableHandler,
    DataUpdateHandler,
    LeaderElectionHandler,
    NodeStatusHandler,
    PulseTableHandler,
)
from .update.manager import ClockPulseGenerator
from .update.update import UpdateHandler, UpdateManager
from .views import (
    ConsistencyContextView,
    MutableStoreConsistencyView,
    MutableStoreCtxView,
    NodeConsistencyContextView,
    StoreConsistencyView,
    StoreCtxView,
)

logger = structlog.stdlib.get_logger().bind(module="pulsewave.store")


class SharedStore:
    def __init__(
        self,
        config_watcher: ConfigWatcher[PulseWaveConfig],
        update_handler: UpdateHandler,
    ):
        self.store: StoreData = StoreData()
        self.config_watcher = config_watcher
        self.config = config_watcher.current_config
        config_watcher.subscribe(self.new_config)
        self.secret_store = SecretContainer()
        self.update_manager = UpdateManager(self)
        self.update_manager.add_handler(ClockTableHandler(config_watcher))
        self.update_manager.add_handler(PulseTableHandler())
        self.update_manager.add_handler(NodeStatusHandler())
        self.update_manager.add_handler(DataUpdateHandler())
        self.update_manager.add_handler(LeaderElectionHandler(self.secret_store))

        self.update_manager.add_event_handler(update_handler)
        self.update_manager.add_event_handler(
            RateLimitedHandler(update_handler, self.config_watcher),
        )

        self.consistency_controller = ClockPulseGenerator(self, self.update_manager)
        logger.debug("SharedStore initialized.")

    def add_handler(self, handler: UpdateHandler):
        self.update_manager.add_handler(handler)

    def new_config(self, config: PulseWaveConfig):
        self.config = config
        self.update_manager.trigger_event("config_reload")

    @overload
    def _get_node(self) -> StoreNodeData: ...

    @overload
    def _get_node(self, node_id: str | None) -> StoreNodeData | None: ...

    def _get_node(self, node_id: str | None = None) -> StoreNodeData | None:
        if node_id is None:
            node_id = self.config.key_mapping.signer.node_id
            node_data = self.store.nodes.get(node_id)
            if node_data is None:
                node_data = StoreNodeData.new()
                self.store.nodes[node_id] = node_data
                self.update_manager.trigger_update([f"nodes.{node_id}"])
            return node_data
        else:
            return self.store.nodes.get(node_id)

    def values(self, node_id: str | None = None) -> Iterator[str]:
        node_data = self._get_node(node_id)

        if node_data:
            for value_id in node_data.values:
                yield value_id

    def contexts(self, node_id: str | None = None) -> Iterator[str]:
        node_data = self._get_node(node_id)
        if node_data:
            for context_name in node_data.contexts:
                yield context_name

    def get_value[T: BaseModel](
        self, value_id: str, model: type[T], node_id: str | None = None
    ) -> T | None:
        if node_data := self._get_node(node_id):
            if value_data := node_data.values.get(value_id):
                return model.model_validate(value_data.data)

    def set_value(
        self,
        value_id: str,
        data: BaseModel,
        req_type: DateEvalType = DateEvalType.NEWER,
    ):
        signed_data = SignedBlockData.new(
            self.config.key_mapping.signer,
            data,
            block_id=value_id,
            path=f"nodes.{self.config.key_mapping.signer.node_id}.values.{value_id}",
            rep_type=req_type,
        )
        self._get_node().values[value_id] = signed_data
        self.update_manager.trigger_update(
            [f"nodes.{self.config.key_mapping.signer.node_id}.values.{value_id}"]
        )

    @overload
    def _get_ctx(self, context_name: str) -> StoreContextData: ...

    @overload
    def _get_ctx(self, context_name: str, node_id: str) -> StoreContextData | None: ...

    def _get_ctx(
        self, context_name: str, node_id: str | None = None
    ) -> StoreContextData | None:
        if node_id is None:
            node_id = self.config.key_mapping.signer.node_id
        node_data = self.store.nodes.get(node_id)
        if node_data:
            ctx_data = node_data.contexts.get(context_name)
            if ctx_data:
                return ctx_data
        if node_id == self.config.key_mapping.signer.node_id:
            node_data = self.store.nodes.get(node_id)
            if node_data is None:
                node_data = StoreNodeData.new()
                self.store.nodes[node_id] = node_data

            ctx_data = StoreContextData.new(
                self.config.key_mapping.signer, context_name
            )
            node_data.contexts[context_name] = ctx_data
            self.update_manager.trigger_update(
                [f"nodes.{node_id}.contexts.{context_name}"]
            )
            return ctx_data
        return None

    @overload
    def _get_consistency(self) -> StoreConsistencyData: ...

    @overload
    def _get_consistency(self, node_id: str) -> StoreConsistencyData | None: ...

    def _get_consistency(
        self, node_id: str | None = None
    ) -> StoreConsistencyData | None:
        if node_id is None:
            node_id = self.config.key_mapping.signer.node_id
        node_data = self.store.nodes.get(node_id)
        if node_data:
            consistency_data = node_data.consistency
            if consistency_data:
                return consistency_data
        if node_id == self.config.key_mapping.signer.node_id:
            node_data = self.store.nodes.get(node_id)
            if node_data is None:
                node_data = StoreNodeData.new()
                self.store.nodes[node_id] = node_data

            consistency_data = StoreConsistencyData.new(self.config.key_mapping.signer)
            node_data.consistency = consistency_data
            self.update_manager.trigger_update([f"nodes.{node_id}.consistency"])
            return consistency_data
        return None

    def get_consistency_context[T: BaseModel](
        self, context_name: str, model: type[T], secret: str | None = None
    ) -> ConsistencyContextView[T]:
        if secret is not None:
            if context_name not in self.secret_store:
                self.secret_store.add_secret(context_name, secret)
            elif not self.secret_store.validate_secret(context_name, secret):
                raise ValueError("Invalid secret for context")

        return ConsistencyContextView(
            self.store,
            context_name,
            f"nodes.{self.config.key_mapping.signer.node_id}.consistency.consistent_contexts.{context_name}",
            model,
            self.config.key_mapping,
            self.update_manager,
            secret,
        )

    def local_consistency_contexts(self) -> Iterator[str]:
        node_data = self._get_node()
        if node_data and node_data.consistency:
            for context_name in node_data.consistency.consistent_contexts:
                yield context_name

    def all_consistency_contexts(self) -> Iterator[NodeConsistencyContextView]:
        for node_id in self.nodes:
            yield NodeConsistencyContextView(
                node_id,
                self.store,
            )

    @overload
    def get_context[T: BaseModel](
        self, context_name: str, model: type[T], node_id: str
    ) -> StoreCtxView[T] | None: ...

    @overload
    def get_context[T: BaseModel](
        self, context_name: str, model: type[T]
    ) -> MutableStoreCtxView[T]: ...

    def get_context[T: BaseModel](
        self, context_name: str, model: type[T], node_id: str | None = None
    ) -> StoreCtxView[T] | MutableStoreCtxView[T] | None:
        if node_id is None:
            node_id = self.config.key_mapping.signer.node_id
            ctx_data = self._get_ctx(context_name)
            return MutableStoreCtxView(
                f"nodes.{node_id}.contexts.{context_name}",
                ctx_data,
                model,
                self.config.key_mapping.signer,
                self.update_manager,
            )
        else:
            ctx_data = self._get_ctx(context_name, node_id)
            if ctx_data is None:
                return None
            return StoreCtxView(
                f"nodes.{node_id}.contexts.{context_name}",
                ctx_data,
                model,
                self.config.key_mapping.signer,
            )

    @overload
    def get_consistency(self, node_id: str) -> StoreConsistencyView | None: ...

    @overload
    def get_consistency(self) -> MutableStoreConsistencyView: ...

    def get_consistency(
        self, node_id: str | None = None
    ) -> StoreConsistencyView | MutableStoreConsistencyView | None:
        if node_id is None:
            node_id = self.config.key_mapping.signer.node_id
            ctx_data = self._get_consistency()
            return MutableStoreConsistencyView(
                f"nodes.{node_id}.consistency",
                ctx_data,
                self.config.key_mapping.signer,
                self.update_manager,
            )
        else:
            ctx_data = self._get_consistency(node_id)
            if ctx_data is None:
                return None
            return StoreConsistencyView(
                f"nodes.{node_id}.consistency",
                ctx_data,
                self.config.key_mapping.signer,
                self.update_manager,
            )

    def dump(self):
        return self.store.model_dump_json()

    def update_from_dump(self, data: str) -> None:
        new_store = StoreData.model_validate_json(data)
        updated_paths = self.store.update(new_store, self.config.key_mapping)
        if updated_paths:
            self.update_manager.trigger_update(updated_paths)

    @property
    def nodes(self) -> list[str]:
        return list(self.config.key_mapping.verifiers.keys())

    def stop(self):
        self.update_manager.stop()
        self.consistency_controller.stop()
        logger.info("SharedStore stopped.")

    def start(self):
        self.update_manager.start()
        self.consistency_controller.start()
        logger.info("SharedStore started.")
