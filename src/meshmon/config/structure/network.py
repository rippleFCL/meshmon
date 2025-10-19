from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class MonitorTypes(Enum):
    PING = "ping"
    HTTP = "http"


class AllowBlock(BaseModel):
    allow: list[str] = []
    block: list[str] = []


class NetworkMonitor(AllowBlock, BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: MonitorTypes
    host: str
    interval: int | None = None
    retry: int | None = None


class NetworkNodeInfo(AllowBlock, BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_id: Annotated[str, StringConstraints(to_lower=True)]
    url: str
    poll_rate: int | None = None
    retry: int | None = None


class NetworkRatelimit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update: float = 5
    priority_update: float = 0.25


class NetworkClusterConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate_limits: NetworkRatelimit = NetworkRatelimit()
    clock_pulse_interval: float = 5
    avg_clock_pulses: int = 30


class NetworkMonitorDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interval: int = 30
    retry: int = 2


class NetworkNodeDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    poll_rate: int = 10
    retry: int = 6


class NetworkDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monitors: NetworkMonitorDefaults = NetworkMonitorDefaults()
    nodes: NetworkNodeDefaults = NetworkNodeDefaults()


class NetworkRootConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_config: list[NetworkNodeInfo]
    network_id: Annotated[str, StringConstraints(to_lower=True)]
    node_version: list[str] | None = None
    monitors: list[NetworkMonitor] = []
    cluster: NetworkClusterConfig = NetworkClusterConfig()
    defaults: NetworkDefaults = NetworkDefaults()
