from pydantic import BaseModel


class Validator(BaseModel):
    local_nonce: str
    remote_nonce: str
    network_id: str
    node_id: str


class Heartbeat(BaseModel):
    node_time: int


class HeartbeatResponse(BaseModel):
    node_time: int


class StoreUpdate(BaseModel):
    data: str
