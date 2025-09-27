import os
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, StringConstraints
from structlog.stdlib import get_logger

from meshmon.version import SEMVER

from .git import Repo
from .pulsewave.crypto import KeyMapping, Signer, Verifier

logger = get_logger()


class ConfigTypes(Enum):
    GIT = "git"
    LOCAL = "local"


class NodeCfgNetwork(BaseModel):
    directory: str
    node_id: Annotated[str, StringConstraints(to_lower=True)]
    config_type: ConfigTypes = ConfigTypes.LOCAL
    git_repo: str | None = None
    discord_webhook: str | None = None


class NodeCfg(BaseModel):
    networks: list[NodeCfgNetwork]


class MonitorTypes(Enum):
    PING = "ping"
    HTTP = "http"


class NetworkMonitor(BaseModel):
    name: str
    type: MonitorTypes
    host: str
    interval: int = 10
    retry: int = 2


class NetworkNodeInfo(BaseModel):
    node_id: Annotated[str, StringConstraints(to_lower=True)]
    url: str | None = None
    poll_rate: int = 10
    retry: int = 2
    local_monitors: list[NetworkMonitor] = []


class NetworkRootConfig(BaseModel):
    node_config: list[NetworkNodeInfo]
    network_id: Annotated[str, StringConstraints(to_lower=True)]
    node_version: list[str] | None = None
    monitors: list[NetworkMonitor] = []


@dataclass
class NetworkConfig:
    key_mapping: KeyMapping
    node_config: list[NetworkNodeInfo]
    monitors: list[NetworkMonitor]
    network_id: str
    node_id: str
    node_cfg: NodeCfgNetwork

    def get_verifier(self, peer_id: str) -> Verifier | None:
        if peer_id not in self.key_mapping:
            return None
        return self.key_mapping.verifiers[peer_id]


# Class to load only network config
class NetworkConfigLoader:
    def __init__(
        self, config_dir: Path | str = "config", file_name: str = "nodeconf.yml"
    ):
        """
        Loader for network configuration. Loads all network configs on initialization.
        """
        self.config_dir = Path(config_dir)
        self.file_name = file_name
        self.node_cfg = self._load_node_config()
        self.networks: dict[str, NetworkConfig] = self._load_all_network_configs()
        self.latest_mtime = self.get_latest_mtime(self.config_dir / "networks")
        self.nodecfg_latest_mtime = self.get_netconf_mtime()

    def _load_node_config(self) -> NodeCfg:
        """
        Load node configuration from nodeconf.yml.
        Returns a dict mapping network_name to NodeCfgNetwork.
        """
        nodeconf_path = self.config_dir / self.file_name
        logger.debug(f"Loading node config from: {nodeconf_path}")
        with open(nodeconf_path, "r") as f:  # TODO: handle file not found
            data = yaml.safe_load(f)
        node_cfg = NodeCfg.model_validate(data)
        logger.debug(f"Loaded config for {len(node_cfg.networks)} networks")

        for network in node_cfg.networks:
            network_dir = self.config_dir / "networks" / network.directory
            if network.config_type == ConfigTypes.GIT and network.git_repo:
                try:
                    repo = Repo(network.git_repo, str(network_dir))
                    repo.clone_or_update()
                except Exception as e:
                    # If pull fails, reclone
                    logger.debug(f"Git pull failed for {network.directory}, error: {e}")
                    shutil.rmtree(network_dir)
            else:
                # For local configs, ensure the directory exists
                network_dir.mkdir(parents=True, exist_ok=True)
                config_path = network_dir / "config.yml"
                if not config_path.exists():
                    example_data = NetworkRootConfig(
                        node_config=[NetworkNodeInfo(node_id=network.node_id)],
                        network_id=network.directory,
                    )
                    with open(config_path, "w") as f:
                        yaml.safe_dump(
                            example_data.model_dump(mode="json", exclude_defaults=True),
                            f,
                        )
        return node_cfg

    def _load_network_config(self, net_cfg: NodeCfgNetwork) -> NetworkConfig | None:
        """
        Load a single network's config and keys.
        """
        logger.debug(f"Loading network config for: {net_cfg.directory}")
        # Load the root network config
        net_config_path = (
            self.config_dir / "networks" / net_cfg.directory / "config.yml"
        )
        if not net_config_path.exists():
            return None
        with open(net_config_path, "r") as f:
            data = yaml.safe_load(f)
        root = NetworkRootConfig.model_validate(data)
        if root.node_version:
            for version in root.node_version:
                if not SEMVER.match(version):
                    logger.warning(
                        f"Node version constraint '{version}' for network '{net_cfg.directory}' is not compatible with current node version '{SEMVER}'"
                    )
                    return None

        logger.debug(f"Network {net_cfg.directory} has {len(root.node_config)} nodes")

        # Load key mapping for this network
        global_pubkey_dir = str(self.config_dir / ".public_keys" / net_cfg.directory)
        pubkey_dir = str(self.config_dir / "networks" / net_cfg.directory / "pubkeys")
        verifier_ids = [node.node_id for node in root.node_config]
        verifiers = {}
        signer = Signer.by_id(
            net_cfg.node_id, str(self.config_dir / ".private_keys" / net_cfg.directory)
        )
        verifier = signer.get_verifier()
        if net_cfg.config_type == ConfigTypes.LOCAL:
            verifier.save(net_cfg.node_id, pubkey_dir)  # Save public key if not exists
        else:
            verifier.save(net_cfg.node_id, global_pubkey_dir)

        for vid in verifier_ids:
            try:
                verifiers[vid] = Verifier.by_id(vid, pubkey_dir)
            except Exception as e:
                logger.warning(f"Failed to load verifier {vid}: {e}")
        key_mapping = KeyMapping(signer=signer, verifiers=verifiers)
        logger.debug(
            f"Loaded {len(verifiers)} verifiers for network {net_cfg.directory}"
        )

        return NetworkConfig(
            node_config=root.node_config,
            network_id=root.network_id,
            monitors=root.monitors,
            key_mapping=key_mapping,
            node_id=net_cfg.node_id,
            node_cfg=net_cfg,
        )

    def _load_all_network_configs(self) -> dict[str, NetworkConfig]:
        """
        Load all network configs as a list of NetworkConfig objects.
        """
        node_configs = self._load_node_config()
        net_configs = [self._load_network_config(cfg) for cfg in node_configs.networks]
        return {cfg.network_id: cfg for cfg in net_configs if cfg is not None}

    def reload(self):
        """
        Reload all network configurations.
        """
        self.node_cfg = self._load_node_config()
        self.networks = self._load_all_network_configs()
        self.latest_mtime = self.get_latest_mtime(self.config_dir / "networks")
        self.nodecfg_latest_mtime = self.get_netconf_mtime()

    def get_network(self, network_id: str) -> NetworkConfig | None:
        """
        Get a network configuration by its ID.
        """
        return self.networks.get(network_id)

    def get_netconf_mtime(self) -> float:
        """
        Get the modification time of the main nodeconf.yml file.
        """
        return (self.config_dir / self.file_name).stat().st_mtime

    def get_latest_mtime(self, network_path: Path) -> float:
        """
        Get the latest access time of all config files.
        Used to detect changes for reloads.
        """
        latest_mtime = 0.0
        for root, _, files in os.walk(network_path):
            for file in files:
                file_path = Path(root) / file
                mtime = file_path.stat().st_mtime
                if mtime > latest_mtime:
                    latest_mtime = mtime
        file_mtime = (self.config_dir / self.file_name).stat().st_mtime
        return max(latest_mtime, file_mtime)

    def needs_reload(self):
        """
        Check if any Git-based network configurations have updates.
        Returns True if any repos had changes, False otherwise.
        """
        has_changes = False

        for network in self.node_cfg.networks:
            # Only check Git-based networks
            network_path = self.config_dir / "networks" / network.directory
            if network.config_type == ConfigTypes.GIT and network.git_repo:
                if network_path.exists():
                    try:
                        repo = Repo(network.git_repo, str(network_path))
                        needs_update = repo.needs_update()

                        if needs_update:
                            logger.info(f"Network {network.directory} has updates")
                            has_changes = True
                        else:
                            logger.debug(f"Network {network.directory} is up to date")

                    except Exception as e:
                        logger.warning(
                            f"Failed to check updates for network {network.directory}: {e}"
                        )
                        # If we can't check, assume no changes to avoid unnecessary reloads
                        continue
                else:
                    logger.debug(
                        f"Network {network.directory} repo directory does not exist"
                    )
            elif self.get_latest_mtime(network_path) > self.latest_mtime:
                logger.info("Configuration files have been modified, reloading")
                has_changes = True
        if self.get_netconf_mtime() > self.nodecfg_latest_mtime:
            logger.info("Node configuration file has been modified, reloading")
            has_changes = True
        return has_changes


def get_pingable_nodes(network: NetworkConfig) -> list[str]:
    connectable: dict[str, bool] = {}
    for node_cfg in network.node_config:
        if node_cfg.url:
            connectable[node_cfg.node_id] = True
        else:
            connectable[node_cfg.node_id] = False
    allowed_keys = []
    for node_id in network.key_mapping.verifiers.keys():
        if connectable.get(node_id, False):
            allowed_keys.append(node_id)
    return allowed_keys


def get_all_monitor_names(network: NetworkConfig, node_id: str) -> list[str]:
    monitor_names = set()
    for monitor in network.monitors:
        monitor_names.add(monitor.name)
    for node in network.node_config:
        if node.node_id != node_id:
            continue
        for monitor in node.local_monitors:
            monitor_names.add(monitor.name)
    return list(monitor_names)
