from dataclasses import dataclass

from .crypto import KeyMapping, Signer, Verifier


@dataclass
class NodeConfig:
    node_id: str
    uri: str
    verifier: Verifier
    heartbeat_interval: float
    heartbeat_retry: int


@dataclass
class CurrentNode:
    node_id: str
    signer: Signer
    verifier: Verifier


@dataclass
class PulseWaveConfig:
    current_node: CurrentNode
    nodes: dict[str, NodeConfig]
    update_rate_limit: float
    instant_update_rate_limit: float
    clock_pulse_interval: float

    def get_verifier(self, node_id: str) -> Verifier | None:
        node_cfg = self.nodes.get(node_id)
        if node_cfg:
            return node_cfg.verifier
        if node_id == self.current_node.node_id:
            return self.current_node.verifier
        return None

    @property
    def key_mapping(self) -> KeyMapping:
        verifiers = {cfg.node_id: cfg.verifier for cfg in self.nodes.values()}
        verifiers[self.current_node.node_id] = self.current_node.verifier
        return KeyMapping(self.current_node.signer, verifiers)
