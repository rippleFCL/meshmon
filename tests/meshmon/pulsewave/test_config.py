"""
Tests for the pulsewave configuration module.

These tests verify that the configuration classes work correctly,
including NodeConfig, CurrentNode, and PulseWaveConfig functionality.
"""

from unittest.mock import Mock

import pytest

from src.meshmon.pulsewave.config import CurrentNode, NodeConfig, PulseWaveConfig
from src.meshmon.pulsewave.crypto import KeyMapping, Signer, Verifier


class TestNodeConfig:
    """Test cases for NodeConfig dataclass."""

    def test_node_config_creation(self):
        """Test creating a NodeConfig instance."""
        verifier = Mock(spec=Verifier)

        node_config = NodeConfig(
            node_id="test_node_1",
            uri="https://example.com/api",
            verifier=verifier,
            heartbeat_interval=5.0,
            heartbeat_retry=3,
        )

        assert node_config.node_id == "test_node_1"
        assert node_config.uri == "https://example.com/api"
        assert node_config.verifier == verifier
        assert node_config.heartbeat_interval == 5.0
        assert node_config.heartbeat_retry == 3

    def test_node_config_equality(self):
        """Test NodeConfig equality comparison."""
        verifier1 = Mock(spec=Verifier)
        verifier2 = Mock(spec=Verifier)

        node1 = NodeConfig("node1", "https://example.com", verifier1, 5.0, 3)
        node2 = NodeConfig("node1", "https://example.com", verifier1, 5.0, 3)
        node3 = NodeConfig("node1", "https://example.com", verifier2, 5.0, 3)

        assert node1 == node2
        assert node1 != node3

    def test_node_config_immutable(self):
        """Test that NodeConfig fields can be modified (dataclass is mutable by default)."""
        verifier = Mock(spec=Verifier)
        node = NodeConfig("node1", "https://example.com", verifier, 5.0, 3)

        # Should be able to modify fields
        node.node_id = "new_id"
        assert node.node_id == "new_id"


class TestCurrentNode:
    """Test cases for CurrentNode dataclass."""

    def test_current_node_creation(self):
        """Test creating a CurrentNode instance."""
        signer = Mock(spec=Signer)
        verifier = Mock(spec=Verifier)

        current_node = CurrentNode(
            node_id="current_node", signer=signer, verifier=verifier
        )

        assert current_node.node_id == "current_node"
        assert current_node.signer == signer
        assert current_node.verifier == verifier

    def test_current_node_has_both_signer_and_verifier(self):
        """Test that CurrentNode includes both signer and verifier."""
        signer = Mock(spec=Signer)
        verifier = Mock(spec=Verifier)

        current_node = CurrentNode("node1", signer, verifier)

        # Current node should have both capabilities
        assert hasattr(current_node, "signer")
        assert hasattr(current_node, "verifier")
        assert current_node.signer == signer
        assert current_node.verifier == verifier


class TestPulseWaveConfig:
    """Test cases for PulseWaveConfig dataclass."""

    @pytest.fixture
    def mock_signer(self):
        """Mock signer for testing."""
        signer = Mock(spec=Signer)
        signer.node_id = "current_node"
        return signer

    @pytest.fixture
    def mock_verifier(self):
        """Mock verifier for testing."""
        return Mock(spec=Verifier)

    @pytest.fixture
    def mock_verifier2(self):
        """Second mock verifier for testing."""
        return Mock(spec=Verifier)

    @pytest.fixture
    def current_node(self, mock_signer, mock_verifier):
        """Mock current node for testing."""
        return CurrentNode(
            node_id="current_node", signer=mock_signer, verifier=mock_verifier
        )

    @pytest.fixture
    def node_configs(self, mock_verifier2):
        """Mock node configurations for testing."""
        return {
            "remote_node_1": NodeConfig(
                node_id="remote_node_1",
                uri="https://node1.example.com/api",
                verifier=mock_verifier2,
                heartbeat_interval=5.0,
                heartbeat_retry=3,
            ),
            "remote_node_2": NodeConfig(
                node_id="remote_node_2",
                uri="https://node2.example.com/api",
                verifier=Mock(spec=Verifier),
                heartbeat_interval=5.0,
                heartbeat_retry=3,
            ),
        }

    @pytest.fixture
    def pulse_config(self, current_node, node_configs):
        """Complete PulseWaveConfig for testing."""
        return PulseWaveConfig(
            current_node=current_node,
            nodes=node_configs,
            update_rate_limit=5,
            clock_pulse_interval=10,
        )

    def test_pulse_wave_config_creation(self, pulse_config):
        """Test creating a PulseWaveConfig instance."""
        assert pulse_config.current_node.node_id == "current_node"
        assert len(pulse_config.nodes) == 2
        assert pulse_config.update_rate_limit == 5
        assert pulse_config.clock_pulse_interval == 10

    def test_get_verifier_for_remote_node(self, pulse_config):
        """Test getting verifier for a remote node."""
        verifier = pulse_config.get_verifier("remote_node_1")

        assert verifier is not None
        assert verifier == pulse_config.nodes["remote_node_1"].verifier

    def test_get_verifier_for_current_node(self, pulse_config):
        """Test getting verifier for the current node."""
        verifier = pulse_config.get_verifier("current_node")

        assert verifier is not None
        assert verifier == pulse_config.current_node.verifier

    def test_get_verifier_for_unknown_node(self, pulse_config):
        """Test getting verifier for an unknown node returns None."""
        verifier = pulse_config.get_verifier("unknown_node")

        assert verifier is None

    def test_get_verifier_with_empty_nodes(self, current_node):
        """Test getting verifier when nodes dict is empty."""
        config = PulseWaveConfig(
            current_node=current_node,
            nodes={},
            update_rate_limit=1,
            clock_pulse_interval=5,
        )

        # Should still work for current node
        verifier = config.get_verifier("current_node")
        assert verifier == current_node.verifier

        # Should return None for any other node
        verifier = config.get_verifier("some_other_node")
        assert verifier is None

    def test_key_mapping_property(
        self, pulse_config, mock_signer, mock_verifier, mock_verifier2
    ):
        """Test the key_mapping property creates correct KeyMapping."""
        key_mapping = pulse_config.key_mapping

        assert isinstance(key_mapping, KeyMapping)
        assert key_mapping.signer == mock_signer

        # Should include verifiers for all nodes including current node
        expected_verifiers = {
            "current_node": mock_verifier,
            "remote_node_1": mock_verifier2,
            "remote_node_2": pulse_config.nodes["remote_node_2"].verifier,
        }

        assert key_mapping.verifiers == expected_verifiers

    def test_key_mapping_includes_current_node_verifier(self, current_node):
        """Test that key_mapping includes current node's verifier."""
        config = PulseWaveConfig(
            current_node=current_node,
            nodes={},  # No remote nodes
            update_rate_limit=1,
            clock_pulse_interval=5,
        )

        key_mapping = config.key_mapping

        assert current_node.node_id in key_mapping.verifiers
        assert key_mapping.verifiers[current_node.node_id] == current_node.verifier

    def test_key_mapping_with_duplicate_node_id(
        self, mock_signer, mock_verifier, mock_verifier2
    ):
        """Test key_mapping when current node ID appears in nodes dict."""
        # Create scenario where current node ID is also in nodes dict
        current_node = CurrentNode("shared_id", mock_signer, mock_verifier)
        nodes = {
            "shared_id": NodeConfig(
                "shared_id", "https://example.com", mock_verifier2, 5.0, 3
            ),
            "other_node": NodeConfig(
                "other_node", "https://other.com", Mock(spec=Verifier), 5.0, 3
            ),
        }

        config = PulseWaveConfig(
            current_node=current_node,
            nodes=nodes,
            update_rate_limit=1,
            clock_pulse_interval=5,
        )

        key_mapping = config.key_mapping

        # Current node's verifier should override the one in nodes dict
        assert key_mapping.verifiers["shared_id"] == mock_verifier

    def test_pulse_wave_config_with_zero_limits(self, current_node):
        """Test PulseWaveConfig with zero rate limits."""
        config = PulseWaveConfig(
            current_node=current_node,
            nodes={},
            update_rate_limit=0,
            clock_pulse_interval=0,
        )

        assert config.update_rate_limit == 0
        assert config.clock_pulse_interval == 0

    def test_pulse_wave_config_with_large_limits(self, current_node):
        """Test PulseWaveConfig with large rate limits."""
        config = PulseWaveConfig(
            current_node=current_node,
            nodes={},
            update_rate_limit=999999,
            clock_pulse_interval=999999,
        )

        assert config.update_rate_limit == 999999
        assert config.clock_pulse_interval == 999999

    def test_nodes_dict_modification(self, pulse_config, mock_verifier):
        """Test that nodes dict can be modified after creation."""
        original_count = len(pulse_config.nodes)

        # Add a new node
        new_node = NodeConfig(
            "new_node", "https://new.example.com", mock_verifier, 5.0, 3
        )
        pulse_config.nodes["new_node"] = new_node

        assert len(pulse_config.nodes) == original_count + 1
        assert pulse_config.get_verifier("new_node") == mock_verifier

    def test_config_string_representation(self, pulse_config):
        """Test that config objects have useful string representations."""
        config_str = str(pulse_config)

        # Should contain key information
        assert "current_node" in config_str
        assert "update_rate_limit" in config_str
        assert "clock_pulse_interval" in config_str

    def test_config_with_special_characters_in_node_id(
        self, mock_signer, mock_verifier
    ):
        """Test config with special characters in node IDs."""
        current_node = CurrentNode(
            "node-with_special.chars", mock_signer, mock_verifier
        )
        nodes = {
            "node@domain.com": NodeConfig(
                "node@domain.com", "https://example.com", Mock(spec=Verifier), 5.0, 3
            ),
            "node_123": NodeConfig(
                "node_123", "https://test.com", Mock(spec=Verifier), 5.0, 3
            ),
        }

        config = PulseWaveConfig(
            current_node=current_node,
            nodes=nodes,
            update_rate_limit=1,
            clock_pulse_interval=5,
        )

        # Should handle special characters correctly
        assert config.get_verifier("node-with_special.chars") == mock_verifier
        assert config.get_verifier("node@domain.com") is not None
        assert config.get_verifier("node_123") is not None

    def test_empty_uri_handling(self, mock_verifier):
        """Test NodeConfig with empty URI."""
        node = NodeConfig("test_node", "", mock_verifier, 5.0, 3)

        assert node.uri == ""
        assert node.node_id == "test_node"
        assert node.verifier == mock_verifier
        assert node.heartbeat_interval == 5.0
        assert node.heartbeat_retry == 3

    def test_config_immutability_of_nested_objects(self, pulse_config):
        """Test that modifying nested objects affects the config."""
        original_node_id = pulse_config.current_node.node_id

        # Modify the current node
        pulse_config.current_node.node_id = "modified_id"

        # Should be modified since dataclasses are mutable by default
        assert pulse_config.current_node.node_id == "modified_id"
        assert pulse_config.current_node.node_id != original_node_id
