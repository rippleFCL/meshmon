from typing import Protocol

from .config import NodeConfig


class UpdateCallback(Protocol):
    def handle_update(self, data: str, node_cfg: NodeConfig) -> bool: ...
