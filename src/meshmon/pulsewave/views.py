from logging import getLogger
from typing import Iterator

from pydantic import BaseModel

from meshmon.pulsewave.update import UpdateManager

from .crypto import Signer
from .data import (
    DateEvalType,
    SignedBlockData,
    StoreContextData,
    StoreData,
    StoreNodeData,
)

logger = getLogger("meshmon.distrostore")


class StoreCtxView[T: BaseModel]:
    def __init__(
        self,
        store: StoreData,
        node_id: str,
        context_name: str,
        model: type[T],
        signer: Signer,
    ):
        self.store = store
        self.node_id = node_id
        self.context_name = context_name
        self.model = model
        self.signer = signer

    def _get_ctx_data(self) -> StoreContextData:
        return self.store.nodes[self.node_id].contexts[self.context_name]

    def __iter__(self) -> Iterator[tuple[str, T]]:
        ctx_data = self._get_ctx_data()
        for value in ctx_data.data:
            data = self.get(value)
            if data is not None:
                yield value, data

    def __len__(self) -> int:
        ctx_data = self._get_ctx_data()
        return len(ctx_data.data)

    def __contains__(self, key: str) -> bool:
        ctx_data = self._get_ctx_data()
        return key in ctx_data.data

    def get(self, key: str) -> T | None:
        ctx_data = self._get_ctx_data()
        if key in ctx_data.data:
            return self.model.model_validate(ctx_data.data[key].data)
        return None


class MutableStoreCtxView[T: BaseModel](StoreCtxView[T]):
    def __init__(
        self,
        store: StoreData,
        node_id: str,
        context_name: str,
        model: type[T],
        signer: Signer,
        update_handler: UpdateManager,
    ):
        self.update_handler = update_handler
        super().__init__(store, node_id, context_name, model, signer)

    def set(self, key: str, data: T, rep_type: DateEvalType = DateEvalType.NEWER):
        ctx_data = self._get_ctx_data()
        signed_data = SignedBlockData.new(
            self.signer, data, block_id=key, rep_type=rep_type
        )
        if ctx_data.allowed_keys and key not in ctx_data.allowed_keys:
            logger.warning(f"Key {key} not in allowed keys; skipping set operation.")
            return
        update_store = StoreData(
            nodes={
                self.node_id: StoreNodeData(
                    contexts={
                        self.context_name: StoreContextData(
                            data={key: signed_data},
                            date=ctx_data.date,
                            context_name=self.context_name,
                            sig=ctx_data.sig,
                            allowed_keys=ctx_data.allowed_keys,
                        )
                    }
                )
            }
        )
        self.update_handler.update(update_store)

    @property
    def allowed_keys(self) -> list[str]:
        ctx_data = self._get_ctx_data()
        return ctx_data.allowed_keys.copy()

    @allowed_keys.setter
    def allowed_keys(self, keys: list[str]):
        new_ctx = StoreContextData.new(self.signer, self.context_name, keys)
        update_store = StoreData(
            nodes={self.node_id: StoreNodeData(contexts={self.context_name: new_ctx})}
        )
        self.update_handler.update(update_store)
