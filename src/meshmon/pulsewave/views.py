from .crypto import Signer
from pydantic import BaseModel
from .data import StoreData, DateEvalType, StoreContextData, SignedBlockData
from typing import Iterator
from logging import getLogger

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

    @property
    def allowed_keys(self) -> list[str]:
        ctx_data = self._get_ctx_data()
        return ctx_data.allowed_keys.copy()

    @allowed_keys.setter
    def allowed_keys(self, keys: list[str]):
        new_ctx = StoreContextData.new(self.signer, self.context_name, keys)
        ctx_data = self._get_ctx_data()
        ctx_data.update(new_ctx, self.signer.get_verifier(), self.context_name)


class MutableStoreCtxView[T: BaseModel](StoreCtxView[T]):
    def __init__(
        self,
        store: StoreData,
        node_id: str,
        context_name: str,
        model: type[T],
        signer: Signer,
    ):
        super().__init__(store, node_id, context_name, model, signer)

    def set(self, key: str, data: T, rep_type: DateEvalType = DateEvalType.NEWER):
        ctx_data = self._get_ctx_data()
        signed_data = SignedBlockData.new(
            self.signer, data, block_id=key, rep_type=rep_type
        )
        if ctx_data.allowed_keys and key not in ctx_data.allowed_keys:
            logger.warning(f"Key {key} not in allowed keys; skipping set operation.")
            return
        ctx_data.data[key] = signed_data
