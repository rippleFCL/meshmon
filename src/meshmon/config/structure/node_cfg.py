from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class ConfigTypes(Enum):
    GIT = "git"
    LOCAL = "local"


class NodeCfgNetwork(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory: str
    node_id: Annotated[str, StringConstraints(to_lower=True)]
    config_type: ConfigTypes = ConfigTypes.LOCAL
    git_repo: str | None = None
    discord_webhook: dict[str, str] | None = None


class NodeCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    networks: list[NodeCfgNetwork]
