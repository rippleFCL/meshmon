import base64
import json
from typing import Iterator
from pydantic import BaseModel

from .config import NetworkConfigLoader
from .crypto import Signer, KeyMapping, Verifier
import datetime
from enum import Enum
import logging


logger = logging.getLogger("distromon.distrostore")


class NodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class BaseNodeData(BaseModel):
    date: datetime.datetime


class PingData(BaseModel):
    status: NodeStatus
    req_time_outbound: float = 0
    req_time_rtt: float = 0

class NodeData(BaseNodeData):
    ping_data: dict[str, PingData] = {}
    node_id: str
    date: datetime.datetime
    version: str

class NodeConfig:
    node_id: str
    pub_key: str


class SignedNodeData[T: BaseNodeData](BaseModel):
    data: T
    signature: str
    sig_id: str

    @classmethod
    def new(cls, signer: Signer, data: T) -> "SignedNodeData[T]":
        model_data = data.model_dump_json().encode()
        encoded = base64.b64encode(signer.sign(model_data)).decode()
        logger.debug(f"Creating new SignedNodeData for signer {signer.sid}")
        return cls(data=data, signature=encoded, sig_id=signer.sid)

    def verify(self, verifier: Verifier) -> bool:
        logger.debug(f"Verifying signature for sig_id {self.sig_id}")
        decoded = verifier.verify(self.data.model_dump_json().encode(), base64.b64decode(self.signature))
        if decoded:
            logger.debug(f"Signature verified for sig_id {self.sig_id}")
        else:
            logger.warning(f"Signature verification failed for sig_id {self.sig_id}")
        return decoded

    @property
    def date(self) -> datetime.datetime:
        return self.data.date


class SharedStore[T: BaseNodeData]:
    def __init__(self, key_mapping: KeyMapping, data_model: type[T]):
        self.store: dict[str, SignedNodeData[T]] = {}
        self.key_mapping = key_mapping
        self.data_model = data_model
        logger.debug("SharedStore initialized.")

    def update_from_dump(self, dump: dict):
        logger.debug(f"Updating store from dump with {len(dump)} entries.")
        for node_data in dump.values():
            self.update_node(SignedNodeData[self.data_model].model_validate(node_data))

    def update_node(self, node_data: SignedNodeData[T]):
        sig_id = node_data.sig_id
        logger.debug(f"Attempting to update node for sig_id {sig_id}")
        if sig_id not in self.key_mapping.verifiers:
            logger.warning(f"sig_id {sig_id} not in key_mapping.verifiers; skipping update.")
            return
        if not (sig_id not in self.store or node_data.date > self.store[sig_id].date):
            logger.debug(f"No update needed for sig_id {sig_id}; existing data is newer or same.")
            return
        if node_data.verify(self.key_mapping.verifiers[sig_id]):
            logger.debug(f"Node data updated for sig_id {sig_id}")
            self.store[sig_id] = node_data
        else:
            logger.warning(f"Node data verification failed for sig_id {sig_id}; not updating store.")

    def __iter__(self) -> Iterator[tuple[str, SignedNodeData[T]]]:
        return iter(self.store.items())

    def update(self, data: T):
        new_data = SignedNodeData[T].new(self.key_mapping.signer, data)
        self.update_node(new_data)

    def get(self, sig_id: str | None = None) -> T | None:
        if sig_id is None:
            sig_id = self.key_mapping.signer.sid
        data = self.store.get(sig_id)
        if data is None:
            return None
        return self.data_model.model_validate(data.data.model_dump())

    def dump(self):
        data = {sig_id: node_data.model_dump(mode="json") for sig_id, node_data in self.store.items()}
        return data

    def __getitem__(self, item: str) -> SignedNodeData[T]:
        return self.store[item]

    def validate(self):
        for node_data in self.store.values():
            verifier = self.key_mapping.verifiers.get(node_data.sig_id)
            if not verifier or not node_data.verify(verifier):
                logger.warning(f"Node data validation failed for sig_id {node_data.sig_id}")
                return False
        logger.info("All node data validated successfully.")
        return True


class StoreManager[T: BaseNodeData]:
    def __init__(self, config: NetworkConfigLoader, model: type[T]):
        self.config = config
        self.model = model
        self.stores = self.load_stores()

    def load_stores(self):
        stores: dict[str, SharedStore] = {}
        for network in self.config.networks.values():
            stores[network.network_id] = SharedStore(network.key_mapping, self.model)
        return stores

    def reload(self):
        self.stores = self.load_stores()


    def get_store(self, network_id: str) -> SharedStore[T]:
        return self.stores[network_id]
