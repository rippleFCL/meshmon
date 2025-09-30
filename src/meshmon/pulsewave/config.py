from pydantic import BaseModel

from .crypto import Verifier, Signer


class NodeConfig(BaseModel):
    node_id: str
    uri: str
    verifier: Verifier


class CurrentNode(BaseModel):
    node_id: str
    signer: Signer
    verifier: Verifier


class PulseWaveConfig(BaseModel):
    current_node: CurrentNode
    nodes: dict[str, NodeConfig]
