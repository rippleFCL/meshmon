import datetime
from enum import Enum

from pydantic import BaseModel


class DSNodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class DSPingData(BaseModel):
    status: DSNodeStatus
    req_time_rtt: float
    date: datetime.datetime


class DSNodeInfo(BaseModel):
    status: DSNodeStatus
    version: str


class DSNodeDataRetention(BaseModel):
    date: datetime.datetime
