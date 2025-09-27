import logging
from typing import Iterator, Literal, overload

from pydantic import BaseModel

from .crypto import KeyMapping
from .data import (
    DateEvalType,
    SignedBlockData,
    StoreContextData,
    StoreData,
    StoreNodeData,
)
from .views import MutableStoreCtxView, StoreCtxView

logger = logging.getLogger("meshmon.distrostore")


class SharedStore:
    def __init__(self, key_mapping: KeyMapping):
        self.store: StoreData = StoreData()
        self.key_mapping = key_mapping
        self.load()
        logger.debug("SharedStore initialized.")

    def values(self, node_id: str | None = None) -> Iterator[str]:
        node_data = self.store.nodes.get(node_id or self.key_mapping.signer.node_id)
        if node_data:
            for value_id in node_data.values:
                yield value_id

    def contexts(self, node_id: str | None = None) -> Iterator[str]:
        node_data = self.store.nodes.get(node_id or self.key_mapping.signer.node_id)
        if node_data:
            for context_name in node_data.contexts:
                yield context_name

    def get_value[T: BaseModel](
        self, value_id: str, model: type[T], node_id: str | None = None
    ) -> T | None:
        if node_data := self.store.nodes.get(
            node_id or self.key_mapping.signer.node_id
        ):
            if value_data := node_data.values.get(value_id):
                return model.model_validate(value_data.data)

    def set_value(
        self,
        value_id: str,
        data: BaseModel,
        req_type: DateEvalType = DateEvalType.NEWER,
    ):
        node_data = self.store.nodes[self.key_mapping.signer.node_id]

        signed_data = SignedBlockData.new(
            self.key_mapping.signer, data, block_id=value_id, rep_type=req_type
        )
        node_data.values[value_id] = signed_data

    @overload
    def _get_ctx(
        self, context_name: str, node_id: str, create_if_missing: Literal[True]
    ) -> StoreContextData: ...

    @overload
    def _get_ctx(
        self, context_name: str, node_id: str, create_if_missing: Literal[False] = False
    ) -> StoreContextData | None: ...

    def _get_ctx(
        self, context_name: str, node_id: str, create_if_missing: bool = False
    ) -> StoreContextData | None:
        node_data = self.store.nodes.get(node_id)
        if node_data:
            ctx_data = node_data.contexts.get(context_name)
            if ctx_data or not create_if_missing:
                return ctx_data
        if create_if_missing:
            node_data = self.store.nodes[node_id]
            ctx_data = StoreContextData.new(self.key_mapping.signer, context_name)
            node_data.contexts[context_name] = ctx_data
            return ctx_data
        return None

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
            node_id = self.key_mapping.signer.node_id
            ctx_data = self._get_ctx(context_name, node_id, create_if_missing=True)
            return MutableStoreCtxView(
                self.store, node_id, context_name, model, self.key_mapping.signer
            )
        else:
            ctx_data = self._get_ctx(context_name, node_id)
            if ctx_data is None:
                return None
            return StoreCtxView(
                self.store, node_id, context_name, model, self.key_mapping.signer
            )

    def update_from_dump(self, dump: dict):
        store_update = StoreData.model_validate(dump)
        return self.store.update(store_update, self.key_mapping)

    def dump(self):
        return self.store.model_dump(mode="json")

    def load(self):
        self.store.nodes[self.key_mapping.signer.node_id] = StoreNodeData.new(
            self.key_mapping.signer
        )

    @property
    def nodes(self) -> list[str]:
        return list(self.key_mapping.verifiers.keys())


6
