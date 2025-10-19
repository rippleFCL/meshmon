import math
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import pydantic
import yaml
from pydantic import StringConstraints
from structlog.stdlib import get_logger

from ..event_log import EventID, EventLog, EventType
from ..git import Repo
from ..pulsewave.crypto import KeyMapping, Signer, Verifier
from ..utils import format_pydantic_error
from ..version import SEMVER
from .structure.network import (
    MonitorTypes,
    NetworkClusterConfig,
    NetworkNodeInfo,
    NetworkRootConfig,
)
from .structure.node_cfg import ConfigTypes, NodeCfg, NodeCfgNetwork


@dataclass
class LoadedNetworkNodeInfo:
    node_id: str
    url: str
    poll_rate: int
    retry: int


@dataclass
class LoadedNetworkMonitor:
    name: str
    type: MonitorTypes
    host: str
    interval: int
    retry: int


@dataclass
class NetworkConfig:
    node_config: list[LoadedNetworkNodeInfo]
    network_id: Annotated[str, StringConstraints(to_lower=True)]
    monitors: list[LoadedNetworkMonitor]
    key_mapping: KeyMapping
    node_id: Annotated[str, StringConstraints(to_lower=True)]
    node_cfg: NodeCfgNetwork
    cluster: NetworkClusterConfig

    def get_verifier(self, node_id: str) -> Verifier | None:
        return self.key_mapping.get_verifier(node_id)


@dataclass
class Config:
    networks: dict[str, NetworkConfig]


class NetworkConfigLoader:
    def __init__(
        self,
        event_log: EventLog,
        config_dir: Path | str = "config",
        file_name: str = "nodeconf.yml",
    ):
        """
        Loader for network configuration. Loads all network configs on initialization.
        """
        self.event_log = event_log
        self.config_dir = Path(config_dir)
        self.file_name = file_name
        self.logger = get_logger().bind(
            module="meshmon.config.config", component="NetworkConfigLoader"
        )
        self._node_cfg: NodeCfg | None = None
        self.latest_mtime = 0
        self.nodecfg_latest_mtime = 0

    def _load_node_config(self) -> NodeCfg | None:
        """
        Load node configuration from nodeconf.yml.
        Returns a dict mapping network_name to NodeCfgNetwork.
        """
        nodeconf_path = self.config_dir / self.file_name
        self.logger.debug("Loading node config", path=nodeconf_path)

        try:
            with open(nodeconf_path, "r") as f:  # TODO: handle file not found
                data = yaml.safe_load(f)
            node_cfg = NodeCfg.model_validate(data)
        except FileNotFoundError:
            self.event_log.log_event(
                EventType.ERROR,
                EventID(mid="nodeconf", src="NetworkConfigLoader"),
                f"Node configuration file not found: {nodeconf_path}",
                "Node Configuration Missing",
            )
            return
        except yaml.YAMLError:
            self.event_log.log_event(
                EventType.ERROR,
                EventID(mid="nodeconf", src="NetworkConfigLoader"),
                f"Failed to parse node configuration file: {nodeconf_path}",
                "Node Configuration Invalid",
            )
            return
        except pydantic.ValidationError as exc:
            self.event_log.log_event(
                EventType.ERROR,
                EventID(mid="nodeconf", src="NetworkConfigLoader"),
                f"Node configuration validation error:\n{format_pydantic_error(exc)}",
                "Node Configuration Validation Error",
            )
            return
        self.event_log.clear_event(mid="nodeconf")
        self.logger.debug("Loaded config", network_count=len(node_cfg.networks))

        for network in node_cfg.networks:
            network_dir = self.config_dir / "networks" / network.directory
            if network.config_type == ConfigTypes.GIT and network.git_repo:
                try:
                    repo = Repo(network.git_repo, str(network_dir))
                    repo.clone_or_update()
                except Exception as exc:
                    # If pull fails, reclone
                    self.logger.warning(
                        "Git pull failed for", exc=exc, network=network.directory
                    )
                    shutil.rmtree(network_dir)
            else:
                # For local configs, ensure the directory exists
                network_dir.mkdir(parents=True, exist_ok=True)
                config_path = network_dir / "config.yml"
                if not config_path.exists():
                    example_data = NetworkRootConfig(
                        node_config=[
                            NetworkNodeInfo(node_id=network.node_id, url="<replace_me>")
                        ],
                        network_id=network.directory,
                    )
                    with open(config_path, "w") as f:
                        yaml.safe_dump(
                            example_data.model_dump(mode="json", exclude_defaults=True),
                            f,
                        )

        networks = [n.directory for n in node_cfg.networks]
        clear_events = []
        for event in self.event_log.events:
            if event.mid == "netconf" and event.network_id not in networks:
                clear_events.append(event)
        for event in clear_events:
            self.event_log.clear_event(
                mid=event.mid,
                network_id=event.network_id,
            )
        return node_cfg

    def _load_network_config(self, net_cfg: NodeCfgNetwork) -> NetworkConfig | None:
        """
        Load a single network's config and keys.
        """
        self.logger.debug("Loading network config", path=net_cfg.directory)
        # Load the root network config
        net_config_path = (
            self.config_dir / "networks" / net_cfg.directory / "config.yml"
        )
        if not net_config_path.exists():
            self.event_log.log_event(
                EventType.ERROR,
                EventID(
                    mid="netconf",
                    src="NetworkConfigLoader",
                    network_id=net_cfg.directory,
                ),
                f"Network configuration file not found for network {net_cfg.directory}, expected at {net_config_path}",
                "Network Configuration Missing",
            )
            self.logger.error(
                "Network configuration file not found", network_id=net_cfg.directory
            )
            return None
        self.event_log.clear_event(mid="netconf", network_id=net_cfg.directory)
        try:
            with open(net_config_path, "r") as f:
                data = yaml.safe_load(f)
            root = NetworkRootConfig.model_validate(data)
        except yaml.YAMLError as exc:
            self.event_log.log_event(
                EventType.ERROR,
                EventID(
                    mid="netconf",
                    src="NetworkConfigLoader",
                    network_id=net_cfg.directory,
                ),
                f"Failed to parse network configuration file for network {net_cfg.directory} at {net_config_path}",
                "Network Configuration Invalid",
            )
            self.logger.error(
                "Failed to parse network configuration",
                network_id=net_cfg.directory,
                error=exc,
            )
            return None
        except pydantic.ValidationError as exc:
            self.event_log.log_event(
                EventType.ERROR,
                EventID(
                    mid="netconf",
                    src="NetworkConfigLoader",
                    network_id=net_cfg.directory,
                ),
                f"Failed to validate network configuration for network {net_cfg.directory}:\n{format_pydantic_error(exc)}",
                "Network Configuration Invalid",
            )
            self.logger.error(
                "Failed to validate network configuration",
                network_id=net_cfg.directory,
                error=exc,
            )
            return None
        if root.node_version:
            for version in root.node_version:
                if not SEMVER.match(version):
                    self.logger.warning(
                        f"Node version constraint '{version}' for network '{net_cfg.directory}' is not compatible with current node version '{SEMVER}'"
                    )
                    self.event_log.log_event(
                        EventType.WARNING,
                        EventID(
                            mid="netconf",
                            src="NetworkConfigLoader",
                            network_id=net_cfg.directory,
                        ),
                        f"Node version constraint '{version}' for network '{net_cfg.directory}' is not compatible with current node version '{SEMVER}'",
                        "Node Version Incompatible",
                    )
                    return None
        if net_cfg.node_id not in [node.node_id for node in root.node_config]:
            self.logger.warning(
                "Node ID for this MeshMon instance is not present in the node configuration for network",
                network_id=root.network_id,
                node_id=net_cfg.node_id,
            )
            self.event_log.log_event(
                EventType.WARNING,
                EventID(
                    mid="netconf",
                    src="NetworkConfigLoader",
                    network_id=net_cfg.directory,
                ),
                f"Node ID for this MeshMon instance is not present in the node configuration for network {net_cfg.directory}",
                "Node ID Missing",
            )
            return None
        self.logger.debug(
            f"Network {net_cfg.directory} has {len(root.node_config)} nodes"
        )
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
            except Exception as exc:
                self.event_log.log_event(
                    EventType.ERROR,
                    EventID(
                        mid="netconf",
                        src="NetworkConfigLoader",
                        network_id=net_cfg.directory,
                    ),
                    f"Failed to load verifier for node {vid} in network {net_cfg.directory}: {exc}",
                    "Verifier Load Error",
                )
                self.logger.warning("Failed to load verifier", exc=exc, vid=vid)
                return None
        key_mapping = KeyMapping(signer=signer, verifiers=verifiers)
        self.logger.debug(
            "Loaded verifiers for network",
            network=net_cfg.directory,
            count=len(verifiers),
        )

        drift = math.pi * 3
        pulse_offset = root.cluster.rate_limits.priority_update / drift
        root.cluster.clock_pulse_interval += (
            pulse_offset  # Adjust clock pulse interval based on rate limit
        )
        loaded_node_cfg = []
        for node in root.node_config:
            loaded_node_cfg.append(
                LoadedNetworkNodeInfo(
                    node_id=node.node_id,
                    url=node.url or "",
                    poll_rate=node.poll_rate or root.defaults.nodes.poll_rate,
                    retry=node.retry or root.defaults.nodes.retry,
                )
            )
        loaded_monitors = []
        for monitor in root.monitors:
            loaded_monitors.append(
                LoadedNetworkMonitor(
                    name=monitor.name,
                    type=monitor.type,
                    host=monitor.host,
                    interval=monitor.interval or root.defaults.monitors.interval,
                    retry=monitor.retry or root.defaults.monitors.retry,
                )
            )
        self.event_log.clear_event(mid="netconf", network_id=net_cfg.directory)
        return NetworkConfig(
            node_config=loaded_node_cfg,
            network_id=root.network_id,
            monitors=loaded_monitors,
            key_mapping=key_mapping,
            node_id=net_cfg.node_id,
            node_cfg=net_cfg,
            cluster=root.cluster,
        )

    def _load_all_network_configs(self) -> dict[str, NetworkConfig] | None:
        """
        Load all network configs as a list of NetworkConfig objects.
        """
        self._node_cfg = self._load_node_config()
        if self._node_cfg is None:
            return None
        net_configs = [
            self._load_network_config(cfg) for cfg in self._node_cfg.networks
        ]
        return {cfg.network_id: cfg for cfg in net_configs if cfg is not None}

    def load(self):
        """
        Reload all network configurations.
        """
        conf = self._load_all_network_configs()
        self.latest_mtime = self.get_latest_mtime(self.config_dir / "networks")
        self.nodecfg_latest_mtime = self.get_netconf_mtime()
        if conf is None:
            return None
        self.config = Config(networks=conf)
        return self.config

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
        if self._node_cfg:
            for network in self._node_cfg.networks:
                # Only check Git-based networks
                network_path = self.config_dir / "networks" / network.directory
                if network.config_type == ConfigTypes.GIT and network.git_repo:
                    if network_path.exists():
                        try:
                            repo = Repo(network.git_repo, str(network_path))
                            needs_update = repo.needs_update()

                            if needs_update:
                                self.logger.info(
                                    "Network has updates", network=network.directory
                                )
                                has_changes = True
                            else:
                                self.logger.debug(
                                    "Network is up to date", network=network.directory
                                )

                        except Exception as exc:
                            self.logger.warning(
                                "Failed to check updates for network",
                                network=network.directory,
                                exc=exc,
                            )
                            # If we can't check, assume no changes to avoid unnecessary reloads
                            continue
                    else:
                        self.logger.debug(
                            "Network repo directory does not exist",
                            network=network.directory,
                        )
                elif self.get_latest_mtime(network_path) > self.latest_mtime:
                    self.logger.info(
                        "Configuration files have been modified, reloading"
                    )
                    has_changes = True
        if self.get_netconf_mtime() > self.nodecfg_latest_mtime:
            self.logger.info("Node configuration file has been modified, reloading")
            has_changes = True
        return has_changes
