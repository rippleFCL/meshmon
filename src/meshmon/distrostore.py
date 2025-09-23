import base64
import json
from typing import Callable, Iterator, Literal, overload
from pydantic import BaseModel


from .config import NetworkConfig, NetworkConfigLoader
from .crypto import Signer, KeyMapping, Verifier
import datetime
from enum import Enum
import logging


logger = logging.getLogger("meshmon.distrostore")


class NodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class DateEvalType(Enum):
    OLDER = "OLDER"
    NEWER = "NEWER"


class PingData(BaseModel):
    status: NodeStatus
    req_time_rtt: float
    date: datetime.datetime
    current_retry: int
    max_retrys: int
    ping_rate: int


class NodeInfo(BaseModel):
    status: NodeStatus
    version: str


class NodeDataRetention(BaseModel):
    date: datetime.datetime


class SignedBlockSignature(BaseModel):
    date: datetime.datetime
    data: dict
    block_id: str
    replacement_type: DateEvalType


class SignedBlockData(BaseModel):
    data: dict
    date: datetime.datetime
    block_id: str
    replacement_type: DateEvalType
    signature: str

    @classmethod
    def new(
        cls, signer: Signer, data: BaseModel, block_id: str, rep_type: DateEvalType
    ) -> "SignedBlockData":
        model_data = data.model_dump(mode="json")
        date = datetime.datetime.now(datetime.timezone.utc)
        data_sig_str = (
            SignedBlockSignature(
                data=model_data, date=date, block_id=block_id, replacement_type=rep_type
            )
            .model_dump_json()
            .encode()
        )
        encoded = base64.b64encode(signer.sign(data_sig_str)).decode()
        logger.debug(f"Creating new SignedNodeData for signer {signer.node_id}")
        return cls(
            data=model_data,
            signature=encoded,
            date=date,
            block_id=block_id,
            replacement_type=rep_type,
        )

    def verify(self, verifier: Verifier, block_id: str) -> bool:
        logger.debug(f"Verifying signature for sig_id {verifier.node_id}")
        data_sig_str = SignedBlockSignature(
            data=self.data,
            date=self.date,
            block_id=self.block_id,
            replacement_type=self.replacement_type,
        ).model_dump_json()
        verified = (
            verifier.verify(data_sig_str.encode(), base64.b64decode(self.signature))
            and self.block_id == block_id
        )
        if verified:
            logger.debug(f"Signature verified for sig_id {verifier.node_id}")
        else:
            logger.warning(
                f"Signature verification failed for sig_id {verifier.node_id}"
            )
        return verified


class StoreContextData(BaseModel):
    data: dict[str, SignedBlockData] = {}
    date: datetime.datetime
    context_name: str
    allowed_keys: list[str]
    sig: str

    @classmethod
    def new(
        cls, signer: Signer, context_name: str, allowed_keys: list[str] | None = None
    ) -> "StoreContextData":
        if allowed_keys is None:
            allowed_keys = []
        date = datetime.datetime.now(datetime.timezone.utc)
        sig_str = json.dumps(
            {
                "context_name": context_name,
                "date": date.isoformat(),
                "allowed_keys": allowed_keys,
            }
        ).encode()
        sig = base64.b64encode(signer.sign(sig_str)).decode()
        return cls(
            data={},
            date=date,
            context_name=context_name,
            sig=sig,
            allowed_keys=allowed_keys,
        )

    def verify(self, verifier: Verifier, context_name: str) -> bool:
        sig_str = json.dumps(
            {
                "context_name": self.context_name,
                "date": self.date.isoformat(),
                "allowed_keys": self.allowed_keys,
            }
        ).encode()
        verified = (
            verifier.verify(sig_str, base64.b64decode(self.sig))
            and self.context_name == context_name
        )
        if verified:
            logger.debug(f"Context signature verified for context {self.context_name}")
        else:
            logger.warning(
                f"Context signature verification failed for context {self.context_name}"
            )
        return verified

    def update(
        self, context_data: "StoreContextData", verifier: Verifier, context_name: str
    ):
        updated = False
        if not (context_data.context_name == self.context_name == context_name):
            logger.warning(
                f"Context name mismatch: {self.context_name} vs {context_data.context_name}"
            )
            return False
        if not context_data.verify(verifier, context_name):
            logger.warning(
                f"New context data signature verification failed for context {self.context_name}"
            )
            return False
        if context_data.date > self.date:
            old_allowed_keys = self.allowed_keys
            self.date = context_data.date
            self.sig = context_data.sig
            self.allowed_keys = context_data.allowed_keys
            self.context_name = context_data.context_name
            if old_allowed_keys != self.allowed_keys:
                logger.debug(
                    f"Allowed keys updated for context {self.context_name}: {old_allowed_keys} -> {self.allowed_keys}"
                )
                for key in list(self.data.keys()):
                    if key not in self.allowed_keys:
                        logger.info(
                            f"Removing disallowed key {key} from context {self.context_name}"
                        )
                        del self.data[key]
            updated = True

        for key, value in context_data.data.items():
            if self.allowed_keys and key not in self.allowed_keys:
                logger.info(f"Key {key} not allowed in context {self.context_name}")
                if key in self.data:
                    logger.info(
                        f"Removing disallowed key {key} from context {self.context_name}"
                    )
                    del self.data[key]
                    updated = True
                continue
            if key not in self.data:
                if value.verify(verifier, key):
                    self.data[key] = value
                    updated = True
            elif (
                value.replacement_type == DateEvalType.NEWER
                and value.date > self.data[key].date
            ):
                if value.verify(verifier, key):
                    self.data[key] = value
                    updated = True
            elif (
                value.replacement_type == DateEvalType.OLDER
                and value.date < self.data[key].date
            ):
                if value.verify(verifier, key):
                    self.data[key] = value
                    updated = True
        return updated


class StoreNodeData(BaseModel):
    contexts: dict[str, StoreContextData] = {}
    values: dict[str, SignedBlockData] = {}

    def update(self, node_data: "StoreNodeData", verifier: Verifier):
        updated = False
        for context_name, context_data in node_data.contexts.items():
            if context_name not in self.contexts:
                if context_data.verify(verifier, context_name):
                    new_ctx = StoreContextData(
                        date=context_data.date,
                        context_name=context_name,
                        sig=context_data.sig,
                        allowed_keys=context_data.allowed_keys,
                    )
                    new_ctx.update(context_data, verifier, context_name)
                    self.contexts[context_name] = new_ctx
                    updated = True
            else:
                updated = self.contexts[context_name].update(
                    context_data, verifier, context_name
                )
        for key, value in node_data.values.items():
            if key not in self.values:
                if value.verify(verifier, key):
                    self.values[key] = value
                    updated = True
            elif (
                self.values[key].replacement_type == DateEvalType.NEWER
                and value.date > self.values[key].date
            ):
                if value.verify(verifier, key):
                    updated = True
                    self.values[key] = value

            elif (
                self.values[key].replacement_type == DateEvalType.OLDER
                and value.date < self.values[key].date
            ):
                if value.verify(verifier, key):
                    self.values[key] = value
                    updated = True
        return updated


class StoreData(BaseModel):
    nodes: dict[str, StoreNodeData] = {}

    def update(self, store_data: "StoreData", key_mapping: KeyMapping):
        updated = False
        for node_id, node_data in store_data.nodes.items():
            if node_id not in key_mapping.verifiers:
                logger.warning(
                    f"Node ID {node_id} not in key mapping verifiers; skipping update."
                )
                continue
            if node_id not in self.nodes:
                new_node = StoreNodeData()
                new_node.update(node_data, key_mapping.verifiers[node_id])
                self.nodes[node_id] = new_node
                updated = True
            else:
                current_node = self.nodes[node_id]
                updated = current_node.update(node_data, key_mapping.verifiers[node_id])
        return updated


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
        ctx_data.data[key] = signed_data


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
        node_data = self.store.nodes.setdefault(
            self.key_mapping.signer.node_id, StoreNodeData()
        )

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
            node_data = self.store.nodes.setdefault(node_id, StoreNodeData())
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
        self.store.update(store_update, self.key_mapping)

    def dump(self):
        return self.store.model_dump(mode="json")

    def load(self):
        for node_id in self.key_mapping.verifiers:
            if node_id not in self.store.nodes:
                self.store.nodes[node_id] = StoreNodeData()
        self.store.nodes[self.key_mapping.signer.node_id] = StoreNodeData()

    @property
    def nodes(self) -> list[str]:
        return list(self.key_mapping.verifiers.keys())


class StoreManager:
    def __init__(
        self,
        config: NetworkConfigLoader,
        store_prefiller: Callable[[SharedStore, NetworkConfig], None],
    ):
        self.config = config
        self.store_prefiller = store_prefiller
        self.stores: dict[str, SharedStore] = {}
        self.load_stores()

    def load_stores(self):
        for network in self.config.networks.values():
            new_store = SharedStore(network.key_mapping)
            if network.network_id in self.stores:
                logger.info(
                    f"Network ID {network.network_id} already exists; loading data from existing store."
                )
                new_store.update_from_dump(self.stores[network.network_id].dump())
            else:
                logger.info(f"Creating new store for network ID {network.network_id}.")
                self.store_prefiller(new_store, network)
            self.stores[network.network_id] = new_store
            logger.debug(f"Loaded store for network ID {network.network_id}")
        for network_id in list(self.stores.keys()):
            if network_id not in self.config.networks:
                logger.info(f"Removing store for obsolete network ID {network_id}.")
                del self.stores[network_id]

    def reload(self):
        self.load_stores()

    def get_store(self, network_id: str):
        return self.stores[network_id]
