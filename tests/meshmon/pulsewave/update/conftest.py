"""
Shared fixtures for pulsewave update module tests.
"""

import datetime
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from src.meshmon.pulsewave.config import CurrentNode, NodeConfig, PulseWaveConfig
from src.meshmon.pulsewave.crypto import KeyMapping, Signer
from src.meshmon.pulsewave.data import StoreConsistencyData, StoreData, StoreNodeData


@pytest.fixture
def mock_signer():
    """Create a mock signer for testing."""
    private_key = Ed25519PrivateKey.generate()
    return Signer("test_node_1", private_key)


@pytest.fixture
def mock_verifier(mock_signer):
    """Create a verifier from the mock signer."""
    return mock_signer.get_verifier()


@pytest.fixture
def another_signer():
    """Create another signer for multi-node testing."""
    private_key = Ed25519PrivateKey.generate()
    return Signer("test_node_2", private_key)


@pytest.fixture
def another_verifier(another_signer):
    """Create another verifier for multi-node testing."""
    return another_signer.get_verifier()


@pytest.fixture
def key_mapping(mock_signer, another_signer):
    """Create a key mapping with multiple signers."""
    return KeyMapping(
        signer=mock_signer,
        verifiers={
            mock_signer.node_id: mock_signer.get_verifier(),
            another_signer.node_id: another_signer.get_verifier(),
        },
    )


@pytest.fixture
def current_node(mock_signer):
    """Create a current node configuration."""
    return CurrentNode(
        node_id=mock_signer.node_id,
        signer=mock_signer,
        verifier=mock_signer.get_verifier(),
    )


@pytest.fixture
def node_config(another_verifier):
    """Create a node configuration."""
    return NodeConfig(
        node_id=another_verifier.node_id,
        uri="http://localhost:8080",
        verifier=another_verifier,
    )


@pytest.fixture
def pulse_config(current_node, node_config):
    """Create a PulseWaveConfig for testing."""
    return PulseWaveConfig(
        current_node=current_node,
        nodes={node_config.node_id: node_config},
        update_rate_limit=1,
        clock_pulse_interval=5,
    )


@pytest.fixture
def mock_shared_store():
    """Create a mock SharedStore for testing."""
    store = Mock()
    store.key_mapping = Mock()
    store.get_consistency = Mock()
    store.nodes = ["node1", "node2"]
    store.dump = Mock(return_value=StoreData())
    store.update_from_dump = Mock()
    return store


@pytest.fixture
def sample_store_data(mock_signer):
    """Create sample store data for testing."""
    store_data = StoreData()
    node_data = StoreNodeData.new()
    node_data.consistency = StoreConsistencyData.new(mock_signer)
    store_data.nodes[mock_signer.node_id] = node_data
    return store_data


@pytest.fixture
def fixed_datetime():
    """Fixed datetime for consistent testing."""
    return datetime.datetime(2025, 10, 5, 12, 0, 0, tzinfo=datetime.timezone.utc)
