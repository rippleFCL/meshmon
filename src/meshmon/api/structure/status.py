from enum import Enum

from pydantic import BaseModel


class NodeStatusEnum(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class ConnectionType(Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class ConnectionNodeInfo(BaseModel):
    rtt: float
    name: str
    conn_type: ConnectionType


class ConnectionInfo(BaseModel):
    src_node: ConnectionNodeInfo
    dest_node: ConnectionNodeInfo


class MonitorStatusEnum(Enum):
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"


class MonitorConnectionInfo(BaseModel):
    node_id: str
    monitor_id: str
    rtt: float
    status: MonitorStatusEnum


class MonitorInfo(BaseModel):
    monitor_id: str
    name: str
    group: str
    status: MonitorStatusEnum


class NodeInfo(BaseModel):
    node_id: str
    status: NodeStatusEnum
    version: str


class NetworkInfo(BaseModel):
    nodes: dict[str, NodeInfo]
    connections: list[ConnectionInfo]
    monitors: list[MonitorInfo]
    monitor_connections: list[MonitorConnectionInfo]


class MeshMonApi(BaseModel):
    networks: dict[str, NetworkInfo] = {}


class DebugApi(BaseModel):
    pass
