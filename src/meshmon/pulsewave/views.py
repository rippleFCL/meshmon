from logging import getLogger
from typing import Iterator

from pydantic import BaseModel

from .crypto import Signer
from .data import (
    DateEvalType,
    SignedBlockData,
    StoreClockPulse,
    StoreClockTableEntry,
    StoreConsistencyData,
    StoreContextData,
    StoreNodeStatusEntry,
    StorePulseTableEntry,
)
from .update.update import UpdateManager

logger = getLogger("meshmon.distrostore")


class StoreCtxView[T: BaseModel]:
    def __init__(
        self,
        path: str,
        context_data: StoreContextData,
        model: type[T],
        signer: Signer,
    ):
        self.path = path
        self.context_data = context_data
        self.model = model
        self.signer = signer

    def __iter__(self) -> Iterator[tuple[str, T]]:
        for value in self.context_data.data:
            data = self.get(value)
            if data is not None:
                yield value, data

    def __len__(self) -> int:
        return len(self.context_data.data)

    def __contains__(self, key: str) -> bool:
        return key in self.context_data.data

    def get(self, key: str) -> T | None:
        if key in self.context_data.data:
            return self.model.model_validate(self.context_data.data[key].data)
        return None


class MutableStoreCtxView[T: BaseModel](StoreCtxView[T]):
    def __init__(
        self,
        path: str,
        context_data: StoreContextData,
        model: type[T],
        signer: Signer,
        update_handler: UpdateManager,
    ):
        self.update_handler = update_handler
        super().__init__(path, context_data, model, signer)

    def set(self, key: str, data: T, rep_type: DateEvalType = DateEvalType.NEWER):
        if self.context_data.allowed_keys and key not in self.context_data.allowed_keys:
            logger.warning(f"Key {key} not in allowed keys; skipping set operation.")
            return
        signed_data = SignedBlockData.new(
            self.signer, data, block_id=key, rep_type=rep_type
        )
        self.context_data.data[key] = signed_data
        self.update_handler.trigger_update([f"{self.path}.{key}"])

    @property
    def allowed_keys(self) -> list[str]:
        return self.context_data.allowed_keys.copy()

    @allowed_keys.setter
    def allowed_keys(self, keys: list[str]):
        self.context_data.allowed_keys = keys
        self.update_handler.trigger_update([f"{self.path}.allowed_keys"])


class StoreConsistencyView:
    def __init__(
        self,
        path: str,
        consistency_data: StoreConsistencyData,
        signer: Signer,
        update_handler: UpdateManager,
    ):
        self.consistency_data = consistency_data
        self.path = path
        self.signer = signer
        self.update_handler = update_handler

    @property
    def clock_table(self) -> StoreCtxView[StoreClockTableEntry] | None:
        if self.consistency_data is None:
            return None
        return StoreCtxView(
            f"{self.path}.clock_table",
            self.consistency_data.clock_table,
            StoreClockTableEntry,
            self.signer,
        )

    @property
    def node_status_table(self) -> StoreCtxView[StoreNodeStatusEntry] | None:
        if self.consistency_data is None:
            return None
        return StoreCtxView(
            f"{self.path}.node_status_table",
            self.consistency_data.node_status_table,
            StoreNodeStatusEntry,
            self.signer,
        )

    @property
    def pulse_table(self) -> StoreCtxView[StorePulseTableEntry] | None:
        if self.consistency_data is None:
            return None
        return StoreCtxView(
            f"{self.path}.pulse_table",
            self.consistency_data.pulse_table,
            StorePulseTableEntry,
            self.signer,
        )

    @property
    def clock_pulse(self) -> StoreClockPulse | None:
        if self.consistency_data is None or self.consistency_data.clock_pulse is None:
            return None
        return StoreClockPulse.model_validate(self.consistency_data.clock_pulse.data)


class MutableStoreConsistencyView(StoreConsistencyView):
    def __init__(
        self,
        path: str,
        consistency_data: StoreConsistencyData,
        signer: Signer,
        update_handler: UpdateManager,
    ):
        super().__init__(path, consistency_data, signer, update_handler)

    @property
    def clock_table(self) -> MutableStoreCtxView[StoreClockTableEntry]:
        return MutableStoreCtxView(
            f"{self.path}.clock_table",
            self.consistency_data.clock_table,
            StoreClockTableEntry,
            self.signer,
            self.update_handler,
        )

    @property
    def node_status_table(self) -> MutableStoreCtxView[StoreNodeStatusEntry]:
        return MutableStoreCtxView(
            f"{self.path}.node_status_table",
            self.consistency_data.node_status_table,
            StoreNodeStatusEntry,
            self.signer,
            self.update_handler,
        )

    @property
    def pulse_table(self) -> MutableStoreCtxView[StorePulseTableEntry]:
        return MutableStoreCtxView(
            f"{self.path}.pulse_table",
            self.consistency_data.pulse_table,
            StorePulseTableEntry,
            self.signer,
            self.update_handler,
        )

    @property
    def clock_pulse(self) -> StoreClockPulse | None:
        return super().clock_pulse

    @clock_pulse.setter
    def clock_pulse(self, pulse: StoreClockPulse):
        if self.consistency_data is None:
            raise ValueError("Consistency data not found for the node.")
        signed_data = SignedBlockData.new(self.signer, pulse, block_id="clock_pulse")
        self.consistency_data.clock_pulse = signed_data
        self.update_handler.trigger_update([f"{self.path}.clock_pulse"])
