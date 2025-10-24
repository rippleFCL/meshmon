import datetime
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel


class DSObjectStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class DSNotifiedStatus(BaseModel):
    status: DSObjectStatus


class DSPingData(BaseModel):
    status: DSObjectStatus
    req_time_rtt: float
    date: datetime.datetime


class DSMonitorData(DSPingData):
    group: str
    name: str
    interval: int
    retry: int

    def get_uid(self) -> str:
        return sha256(f"{self.group}:{self.name}".encode()).hexdigest()


class DSNodeStatus(BaseModel):
    status: DSObjectStatus
    last_updated: datetime.datetime


class DSMonitorStatus(BaseModel):
    group: str
    name: str
    last_updated: datetime.datetime
    status: DSObjectStatus

    def get_uid(self) -> str:
        return sha256(f"{self.group}:{self.name}".encode()).hexdigest()


class DSNodeInfo(BaseModel):
    version: str


class DSNodeDataRetention(BaseModel):
    date: datetime.datetime
