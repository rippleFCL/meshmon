from enum import Enum

from pydantic import BaseModel


class NotificationClusterStatusEnum(Enum):
    LEADER = "LEADER"
    FOLLOWER = "FOLLOWER"
    WAITING_FOR_CONSENSUS = "WAITING_FOR_CONSENSUS"
    NOT_PARTICIPATING = "NOT_PARTICIPATING"
    OFFLINE = "OFFLINE"


class NotificationCluster(BaseModel):
    node_statuses: dict[str, NotificationClusterStatusEnum] = {}


class NotificationClusters(BaseModel):
    clusters: dict[str, NotificationCluster] = {}


class NotificationClusterApi(BaseModel):
    networks: dict[str, NotificationClusters] = {}
