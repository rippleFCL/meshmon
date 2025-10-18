import datetime
from logging import getLogger
from typing import Iterator, overload

from pydantic import BaseModel

from .crypto import KeyMapping, Signer
from .data import (
    DateEvalType,
    SignedBlockData,
    StoreClockPulse,
    StoreClockTableEntry,
    StoreConsistencyData,
    StoreConsistentContextData,
    StoreContextData,
    StoreData,
    StoreLeaderEntry,
    StoreLeaderStatus,
    StoreNodeData,
    StoreNodeStatus,
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
        for value in list(self.context_data.data):
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
        signed_data = SignedBlockData.new(
            self.signer,
            data,
            block_id=key,
            path=f"{self.path}.{key}",
            rep_type=rep_type,
        )
        self.context_data.data[key] = signed_data
        if key not in self.context_data.allowed_keys:
            self.context_data.allowed_keys.append(key)
            self.context_data.resign(self.signer)
        self.update_handler.trigger_update([f"{self.path}.{key}"])

    def delete(self, key: str):
        if key in self.context_data.data:
            del self.context_data.data[key]
            if key in self.context_data.allowed_keys:
                self.context_data.allowed_keys.remove(key)
                self.context_data.resign(self.signer)
            self.update_handler.trigger_update([f"{self.path}.{key}"])


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
        signed_data = SignedBlockData.new(
            self.signer, pulse, path=f"{self.path}.clock_pulse", block_id="clock_pulse"
        )
        self.consistency_data.clock_pulse = signed_data
        self.update_handler.trigger_update([f"{self.path}.clock_pulse"])


class ConsistencyContextEntry(BaseModel):
    signed_block: SignedBlockData
    date: datetime.datetime


class ConsistencyContextView[T: BaseModel]:
    def __init__(
        self,
        store: "StoreData",
        ctx_name: str,
        path: str,
        model: type[T],
        key_mapping: KeyMapping,
        update_handler: UpdateManager,
        secret: str | None = None,
    ):
        self.update_handler = update_handler
        self.model = model
        self.key_mapping = key_mapping
        self.secret = secret
        self.store = store
        self.ctx_name = ctx_name
        self.path = path
        self._get_consistency()

    @overload
    def _get_consistency(self) -> StoreConsistentContextData: ...

    @overload
    def _get_consistency(self, node_id: str) -> StoreConsistentContextData | None: ...

    def _get_consistency(
        self, node_id: str | None = None
    ) -> StoreConsistentContextData | None:
        if node_id is not None:
            node_data = self.store.nodes.get(node_id)
            if not node_data:
                return None
            consistency = node_data.consistency
            if not consistency:
                return None
            return consistency.consistent_contexts.get(self.ctx_name)

        updated_paths = []
        current_node_id = self.key_mapping.signer.node_id
        node_data = self.store.nodes.get(current_node_id)
        if node_data is None:
            node_data = StoreNodeData.new()
            self.store.nodes[current_node_id] = node_data
            updated_paths.append(f"nodes.{current_node_id}")
        if node_data.consistency is None:
            node_data.consistency = StoreConsistencyData.new(self.key_mapping.signer)
            updated_paths.append(f"nodes.{current_node_id}.consistency")

        cons_ctx = node_data.consistency.consistent_contexts.get(self.ctx_name)
        if cons_ctx is None:
            cons_ctx = StoreConsistentContextData.new(
                self.key_mapping.signer, self.ctx_name, f"{self.path}", self.secret
            )
            if self.ctx_name not in node_data.consistency.allowed_contexts:
                node_data.consistency.allowed_contexts.append(self.ctx_name)
                node_data.consistency.resign(self.key_mapping.signer)
            node_data.consistency.consistent_contexts[self.ctx_name] = cons_ctx
            updated_paths.append(
                f"nodes.{current_node_id}.consistency.consistent_contexts.{self.ctx_name}"
            )
        if updated_paths:
            self.update_handler.trigger_update(updated_paths)
        return cons_ctx

    def _get_consistent_ctx_entry(
        self, node_id: str, key: str
    ) -> SignedBlockData | None:
        cons_ctx = self._get_consistency(node_id)
        if not cons_ctx or not cons_ctx.context or key not in cons_ctx.context.data:
            return None
        return cons_ctx.context.data[key]

    def _get_clock_entry(self, node_id: str) -> StoreClockTableEntry | None:
        current_node_id = self.key_mapping.signer.node_id

        node_data = self.store.nodes.get(current_node_id)
        if not node_data or not node_data.consistency:
            return None
        consistency = node_data.consistency
        if node_id not in consistency.clock_table.data:
            return None
        if node_id not in consistency.clock_table.data:
            return None
        data = consistency.clock_table.data[node_id].data
        return StoreClockTableEntry.model_validate(data)

    @property
    def leader_status(self) -> StoreLeaderEntry | None:
        node_id = self.key_mapping.signer.node_id
        consistency_ctx = self._get_consistency(node_id)
        if not consistency_ctx or not consistency_ctx.leader:
            return None
        leader_data = SignedBlockData.model_validate(consistency_ctx.leader.data)
        return StoreLeaderEntry.model_validate(leader_data.data)

    @leader_status.setter
    def leader_status(self, status: StoreLeaderEntry):
        consistency_ctx = self._get_consistency()
        consistency_ctx.leader = SignedBlockData.new(
            self.key_mapping.signer,
            data=SignedBlockData.new(
                self.key_mapping.signer,
                status,
                block_id="leader_status",
                path=f"{self.path}.leader.leader_status",
                secret=self.secret,
            ),
            path=f"{self.path}.leader",
            block_id="leader",
        )

    def get_leader_status(self, node_id: str) -> StoreLeaderEntry | None:
        consistency_ctx = self._get_consistency(node_id)
        if not consistency_ctx or not consistency_ctx.leader:
            return None
        leader_data = SignedBlockData.model_validate(consistency_ctx.leader.data)
        return StoreLeaderEntry.model_validate(leader_data.data)

    def is_leader(self) -> bool:
        leaders = []
        for node_id in self.online_nodes():
            ctx = self._get_consistency(node_id)
            if not ctx or not ctx.leader:
                continue
            verifier = self.key_mapping.get_verifier(node_id)
            if not verifier:
                continue
            if not ctx.leader.verify(verifier, "leader", f"{self.path}.leader"):
                continue
            leader_data = SignedBlockData.model_validate(ctx.leader.data)
            if not leader_data.verify(
                verifier, "leader_status", f"{self.path}.leader_status", self.secret
            ):
                continue
            leader_entry = StoreLeaderEntry.model_validate(leader_data.data)
            if leader_entry.status == StoreLeaderStatus.LEADER:
                leaders.append(node_id)
        if len(leaders) != 1:
            return False
        return leaders[0] == self.key_mapping.signer.node_id

    def get(self, key: str) -> T | None:
        entries = []
        for node_id in self.store.nodes:
            entry = self._get_consistent_ctx_entry(node_id, key)
            if not entry:
                continue

            verifier = self.key_mapping.get_verifier(node_id)
            if not verifier:
                continue

            ct_entry = self._get_clock_entry(node_id)
            if not ct_entry:
                continue

            entry_date = entry.date + ct_entry.delta
            entries.append(ConsistencyContextEntry(signed_block=entry, date=entry_date))
        if not entries:
            return None
        entries.sort(key=lambda x: x.date, reverse=True)
        return self.model.model_validate(entries[0].signed_block.data)

    def set(self, key: str, data: T):
        updated_paths = []
        signed_data = SignedBlockData.new(
            self.key_mapping.signer, data, path=f"{self.path}.{key}", block_id=key
        )
        cons_ctx = self._get_consistency()
        if cons_ctx.context is None:
            cons_ctx.context = StoreContextData.new(
                self.key_mapping.signer, self.ctx_name
            )
            updated_paths.append(self.path)
        cons_ctx.context.data[key] = signed_data
        if key not in cons_ctx.context.allowed_keys:
            cons_ctx.context.allowed_keys.append(key)
            cons_ctx.context.resign(self.key_mapping.signer)
        updated_paths.append(f"{self.path}.{key}")
        self.update_handler.trigger_update(updated_paths)

    def online_nodes(self) -> list[str]:
        nodes = []
        node_data = self.store.nodes.get(self.key_mapping.signer.node_id)
        if not node_data or not node_data.consistency:
            return nodes
        node_statuses = node_data.consistency.node_status_table
        for node in self.nodes():
            if node in node_statuses.data:
                status_entry = StoreNodeStatusEntry.model_validate(
                    node_statuses.data[node].data
                )
                if status_entry.status == StoreNodeStatus.ONLINE:
                    nodes.append(node)
        return nodes

    def nodes(self) -> list[str]:
        nodes = []
        for node_id in list(self.store.nodes):
            cons_ctx = self._get_consistency(node_id)
            if not cons_ctx:
                continue
            leader = cons_ctx.leader
            verifier = self.key_mapping.get_verifier(node_id)
            if not verifier:
                continue
            if not leader:
                continue
            node_data = SignedBlockData.model_validate(leader.data)
            if not node_data.verify(
                verifier, "leader_status", f"{self.path}.leader_status", self.secret
            ):
                continue
            nodes.append(node_id)
        return nodes


class NodeConsistencyContextView:
    def __init__(
        self,
        node_id: str,
        store: "StoreData",
    ):
        self.store = store
        self.node_id = node_id

    def node_statuses(self) -> Iterator[tuple[str, StoreLeaderEntry]]:
        node_data = self.store.nodes.get(self.node_id)
        if not node_data or not node_data.consistency:
            return
        consistency = node_data.consistency.consistent_contexts
        for cluster_id, entry in consistency.items():
            if not entry.leader:
                continue
            leader_data = SignedBlockData.model_validate(entry.leader.data)
            yield cluster_id, StoreLeaderEntry.model_validate(leader_data.data)
