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
    group: str = "default"
    interval: int | None = None
    retry: int | None = None


class NetworkRebroadcastMonitorConfig(BaseModel):
    name: str
    group: str | None = None


class NetworkRebGroupRewrite(BaseModel):
    src_group: str
    dest_group: str


class NetworkRebMonRewrite(BaseModel):
    src_monitor: str
    dest_monitor: str
    src_group: str | None = None
    dest_group: str | None = None


class NetworkRebroadcastNetworkConfig(BaseModel):
    apply_to: list[str]
    src_net: str
    group_prefix: str = ""
    monitor_prefix: str = ""
    group_rewrites: list[NetworkRebGroupRewrite] = []
    monitor_rewrites: list[NetworkRebMonRewrite] = []
    groups: list[str] = []
    monitors: list[NetworkRebroadcastMonitorConfig] = []


class NetworkNodeInfo(AllowBlock, BaseModel):
    node_id: Annotated[str, StringConstraints(to_lower=True)]
    url: str | None = None
    poll_rate: int | None = None
    retry: int | None = None


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
    rebroadcasts: list[NetworkRebroadcastNetworkConfig] = []
