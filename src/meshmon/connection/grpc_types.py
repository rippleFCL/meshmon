from pydantic import BaseModel


class Validator(BaseModel):
    client_nonce: str
    server_nonce: str
    network_id: str
    node_id: str


class Heartbeat(BaseModel):
    node_time: int


class HeartbeatResponse(BaseModel):
    node_time: int


class StoreUpdate(BaseModel):
    data: str
