import datetime
from enum import Enum
from typing import Callable

import structlog
from pydantic import BaseModel

from .config import NetworkConfig, NetworkConfigLoader
from .pulsewave.config import PulseWaveConfig
from .pulsewave.store import SharedStore

logger = structlog.stdlib.get_logger().bind(module="pulsewave.distrostore")


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

    def _pulse_wave_config(self, network: NetworkConfig):


    def load_stores(self):
        for network in self.config.networks.values():
            new_store = SharedStore(network.key_mapping)
            if network.network_id in self.stores:
                logger.info(
                    "Store already exists; loading data from existing store",
                    network_id=network.network_id,
                )
                new_store.update_from_dump(self.stores[network.network_id].dump())
            else:
                logger.info(
                    "Creating new store",
                    network_id=network.network_id,
                )
                self.store_prefiller(new_store, network)
            self.stores[network.network_id] = new_store
            logger.debug("Loaded store", network_id=network.network_id)
        for network_id in list(self.stores.keys()):
            if network_id not in self.config.networks:
                logger.info(
                    "Removing obsolete store",
                    network_id=network_id,
                )
                del self.stores[network_id]

    def reload(self):
        self.load_stores()

    def get_store(self, network_id: str):
        return self.stores[network_id]
