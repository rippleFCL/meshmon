from dataclasses import dataclass
from enum import Enum
from pathlib import Path


from distmon.crypto import Signer, Verifier
from .crypto import KeyMapping
import yaml
from pydantic import BaseModel
from git import Repo
import shutil
import logging

logger = logging.getLogger("distromon.config")


class ConfigTypes(Enum):
    GITHUB = "github"
    LOCAL = "local"


class NodeCfgNetwork(BaseModel):
    name: str
    node_id: str
    config_type: ConfigTypes = ConfigTypes.LOCAL
    git_repo: str | None = None


class NodeCfg(BaseModel):
    networks: list[NodeCfgNetwork]
    login_password: str


class NetworkNodeInfo(BaseModel):
    node_id: str
    url: str
    poll_rate: int = 10
    retry: int = 2


class NetworkRootConfig(BaseModel):
    node_config: list[NetworkNodeInfo]
    network_id: str


@dataclass
class NetworkConfig:
    key_mapping: KeyMapping
    node_config: list[NetworkNodeInfo]
    network_id: str
    node_id: str

    def get_verifier(self, peer_id: str) -> Verifier | None:
        if peer_id not in self.key_mapping:
            return None
        return self.key_mapping.verifiers[peer_id]


# Class to load only network config
class NetworkConfigLoader:
    def __init__(self, config_dir: Path | str = "config", file_name: str = "nodeconf.yml"):
        """
        Loader for network configuration. Loads all network configs on initialization.
        """
        self.config_dir = Path(config_dir)
        self.file_name = file_name
        self.node_cfg = self._load_node_config()
        self.networks: dict[str, NetworkConfig] = self._load_all_network_configs()

    def _load_node_config(self) -> NodeCfg:
        """
        Load node configuration from nodeconf.yml.
        Returns a dict mapping network_name to NodeCfgNetwork.
        """
        nodeconf_path = self.config_dir / self.file_name
        logger.debug(f"Loading node config from: {nodeconf_path}")
        with open(nodeconf_path, "r") as f:
            data = yaml.safe_load(f)
        node_cfg = NodeCfg.model_validate(data)
        logger.debug(f"Loaded config for {len(node_cfg.networks)} networks")

        for network in node_cfg.networks:
            # If the config is from GitHub, clone or pull the repo
            if network.config_type == ConfigTypes.GITHUB and network.git_repo:
                # Use a temp directory for the repo
                repo_dir = self.config_dir / "networks" / network.name
                repo_url = network.git_repo
                if repo_dir.exists():
                    # If already cloned, pull latest
                    try:
                        repo = Repo(str(repo_dir))
                        origin = repo.remotes.origin
                        origin.pull()
                    except Exception as e:
                        # If pull fails, reclone
                        logger.debug(f"Git pull failed for {network.name}, recloning: {e}")
                        shutil.rmtree(repo_dir)
                        Repo.clone_from(repo_url, str(repo_dir))
                else:
                    Repo.clone_from(repo_url, str(repo_dir))
        return node_cfg

    def _load_network_config(self, net_cfg: NodeCfgNetwork) -> NetworkConfig:
        """
        Load a single network's config and keys.
        """
        logger.debug(f"Loading network config for: {net_cfg.name}")
        # Load the root network config
        net_config_path = self.config_dir / "networks" / net_cfg.name / "config.yml"
        with open(net_config_path, "r") as f:
            data = yaml.safe_load(f)
        root = NetworkRootConfig.model_validate(data)
        logger.debug(f"Network {net_cfg.name} has {len(root.node_config)} nodes")

        # Load key mapping for this network
        pubkey_dir = str(self.config_dir / "networks" / net_cfg.name / "pubkeys")
        verifier_ids = [node.node_id for node in root.node_config]
        verifiers = {}
        signer = Signer.by_id(net_cfg.node_id, root.network_id)
        signer.get_verifier().save(net_cfg.node_id, pubkey_dir)  # Save public key if not exists
        for vid in verifier_ids:
            try:
                verifiers[vid] = Verifier.by_id(vid, pubkey_dir)
            except Exception as e:
                logger.warning(f"Failed to load verifier {vid}: {e}")
        key_mapping = KeyMapping(signer=signer, verifiers=verifiers)
        logger.debug(f"Loaded {len(verifiers)} verifiers for network {net_cfg.name}")

        return NetworkConfig(
            node_config=root.node_config, network_id=root.network_id, key_mapping=key_mapping, node_id=net_cfg.node_id
        )

    def _load_all_network_configs(self) -> dict[str, NetworkConfig]:
        """
        Load all network configs as a list of NetworkConfig objects.
        """
        node_configs = self._load_node_config()
        net_configs = [self._load_network_config(cfg) for cfg in node_configs.networks]
        return {cfg.network_id: cfg for cfg in net_configs}
    def reload(self):
        """
        Reload all network configurations.
        """
        self.networks = self._load_all_network_configs()

    def get_network(self, network_id: str) -> NetworkConfig | None:
        """
        Get a network configuration by its ID.
        """
        return self.networks.get(network_id)

    def needs_reload(self):
        """
        Check if any GitHub-based network configurations have updates.
        Returns True if any repos had changes, False otherwise.
        """
        has_changes = False

        for network in self.node_cfg.networks:
            # Only check GitHub-based networks
            if network.config_type == ConfigTypes.GITHUB and network.git_repo:
                repo_dir = self.config_dir / "networks" / network.name

                if repo_dir.exists():
                    try:
                        repo = Repo(str(repo_dir))
                        # Get current commit hash before pulling
                        old_commit = repo.head.commit.hexsha

                        # Pull latest changes
                        origin = repo.remotes.origin
                        origin.pull()

                        # Get commit hash after pulling
                        new_commit = repo.head.commit.hexsha

                        # Check if there were any changes
                        if old_commit != new_commit:
                            logger.info(f"Network {network.name} has updates: {old_commit[:8]} -> {new_commit[:8]}")
                            has_changes = True
                        else:
                            logger.debug(f"Network {network.name} is up to date")

                    except Exception as e:
                        logger.warning(f"Failed to check updates for network {network.name}: {e}")
                        # If we can't check, assume no changes to avoid unnecessary reloads
                        continue
                else:
                    logger.debug(f"Network {network.name} repo directory does not exist")

        return has_changes
