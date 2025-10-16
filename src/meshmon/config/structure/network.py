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


class NetworkRootConfig(BaseModel):
    node_config: list[NetworkNodeInfo]
    network_id: Annotated[str, StringConstraints(to_lower=True)]
    node_version: list[str] | None = None
    monitors: list[NetworkMonitor] = []
