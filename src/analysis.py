from pydantic import BaseModel


class inboundData(BaseModel):
    node_id: str
    timestamp: float
    data: dict
