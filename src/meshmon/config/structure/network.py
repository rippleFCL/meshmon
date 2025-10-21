from enum import Enum
from typing import Annotated

from pydantic import BaseModel, StringConstraints


class MonitorTypes(Enum):
    PING = "ping"
    HTTP = "http"


class AllowBlock(BaseModel):
    allow: list[str] = []
    block: list[str] = []


class NetworkMonitor(AllowBlock, BaseModel):
    type: MonitorTypes
    name: str
    host: str
    interval: int | None = None
    retry: int | None = None


class NetworkRebroadcastConfig(BaseModel):
    name: str
    dest_name: str | None = None


class NetworkRebroadcastNetworkConfig(BaseModel):
    src_net: str
    prefix: str = ""
    monitors: list[NetworkRebroadcastConfig] = []


class NetworkNodeInfo(AllowBlock, BaseModel):
    node_id: Annotated[str, StringConstraints(to_lower=True)]
    url: str | None = None
    poll_rate: int | None = None
    retry: int | None = None
    rebroadcast: list[NetworkRebroadcastNetworkConfig] = []


class NetworkRatelimit(BaseModel):
    update: float = 5
    priority_update: float = 1


class NetworkClusterConfig(BaseModel):
    rate_limits: NetworkRatelimit = NetworkRatelimit()
    clock_pulse_interval: float = 10
    avg_clock_pulses: int = 30


class NetworkMonitorDefaults(BaseModel):
    interval: int = 120
    retry: int = 3


class NetworkNodeDefaults(BaseModel):
    poll_rate: int = 120
    retry: int = 3


class NetworkDefaults(BaseModel):
    monitors: NetworkMonitorDefaults = NetworkMonitorDefaults()
    nodes: NetworkNodeDefaults = NetworkNodeDefaults()


class NetworkRootConfig(BaseModel):
    node_config: list[NetworkNodeInfo]
    network_id: Annotated[str, StringConstraints(to_lower=True)]
    node_version: list[str] | None = None
    monitors: list[NetworkMonitor] = []
    cluster: NetworkClusterConfig = NetworkClusterConfig()
    defaults: NetworkDefaults = NetworkDefaults()
