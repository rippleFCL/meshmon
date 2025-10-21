from enum import Enum
from typing import Annotated

from pydantic import BaseModel, StringConstraints


class ConfigTypes(Enum):
    GIT = "git"
    LOCAL = "local"


class NodeCfgNetwork(BaseModel):
    directory: str
    node_id: Annotated[str, StringConstraints(to_lower=True)]
    config_type: ConfigTypes = ConfigTypes.LOCAL
    git_repo: str | None = None
    discord_webhook: dict[str, str] | None = None


class NodeCfg(BaseModel):
    networks: list[NodeCfgNetwork]
