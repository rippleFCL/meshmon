import datetime
import logging
from enum import Enum
from typing import Callable

from pydantic import BaseModel

from ..config import NetworkConfig, NetworkConfigLoader
from .store import SharedStore

logger = logging.getLogger("meshmon.distrostore")


class NodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


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
