import datetime
from enum import Enum

from pydantic import BaseModel


class ClusterNodeStatusEnum(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class ClusterClockTableEntry(BaseModel):
    delta_ms: float
    node_time: datetime.datetime


class ClusterInfo(BaseModel):
    node_statuses: dict[str, ClusterNodeStatusEnum]
    clock_table: dict[str, ClusterClockTableEntry]


class ClusterInfoApi(BaseModel):
    networks: dict[str, ClusterInfo] = {}
