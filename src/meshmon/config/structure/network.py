from enum import Enum
from typing import Annotated

from pydantic import BaseModel, StringConstraints


class MonitorTypes(Enum):
    PING = "ping"
    HTTP = "http"


class NetworkMonitor(BaseModel):
    name: str
    type: MonitorTypes
    host: str
    interval: int = 10
    retry: int = 2


class NetworkNodeInfo(BaseModel):
    node_id: Annotated[str, StringConstraints(to_lower=True)]
    url: str | None = None
    poll_rate: int = 10
    retry: int = 2


class NetworkRatelimit(BaseModel):
    update: float = 5
    priority_update: float = 0


class NetworkClusterConfig(BaseModel):
    rate_limits: NetworkRatelimit = NetworkRatelimit()
    clock_pulse_interval: float = 1


class NetworkRootConfig(BaseModel):
    node_config: list[NetworkNodeInfo]
    network_id: Annotated[str, StringConstraints(to_lower=True)]
    node_version: list[str] | None = None
    monitors: list[NetworkMonitor] = []
    cluster: NetworkClusterConfig = NetworkClusterConfig()
