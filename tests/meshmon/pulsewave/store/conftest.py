from unittest.mock import Mock, patch

import pytest

from src.meshmon.pulsewave.config import CurrentNode, NodeConfig, PulseWaveConfig
from src.meshmon.pulsewave.crypto import KeyMapping, Signer, Verifier
from src.meshmon.pulsewave.store import SharedStore
from src.meshmon.pulsewave.update.update import UpdateHandler


@pytest.fixture
def mock_signer():
    """Create mock signer with node_id."""
    signer = Mock(spec=Signer)
    signer.node_id = "test_node"
    return signer


@pytest.fixture
def mock_verifier():
    """Create mock verifier."""
    return Mock(spec=Verifier)


@pytest.fixture
def key_mapping(mock_signer, mock_verifier):
    """Create mock key mapping."""
    mapping = Mock(spec=KeyMapping)
    mapping.signer = mock_signer
    mapping.verifiers = {"test_node": mock_verifier, "other_node": mock_verifier}
    return mapping


@pytest.fixture
def current_node(mock_signer, mock_verifier):
    """Create CurrentNode configuration."""
    return CurrentNode(node_id="test_node", signer=mock_signer, verifier=mock_verifier)


@pytest.fixture
def pulse_config(current_node, mock_verifier):
    """Create PulseWaveConfig for testing."""
    return PulseWaveConfig(
        current_node=current_node,
        nodes={
            "test_node": NodeConfig(
                node_id="test_node",
                uri="https://test.example.com",
                verifier=mock_verifier,
                heartbeat_interval=5.0,
                heartbeat_retry=3,
            ),
            "other_node": NodeConfig(
                node_id="other_node",
                uri="https://other.example.com",
                verifier=Mock(spec=Verifier),
                heartbeat_interval=5.0,
                heartbeat_retry=3,
            ),
        },
        update_rate_limit=1,
        clock_pulse_interval=5,
    )


@pytest.fixture
def mock_update_handler():
    """Create mock update handler."""
    return Mock(spec=UpdateHandler)


@pytest.fixture
def shared_store(pulse_config, mock_update_handler):
    """Create SharedStore instance for testing."""
    mock_matcher = Mock()
    mock_handler = Mock()

    with (
        patch("src.meshmon.pulsewave.store.UpdateManager") as mock_update_manager,
        patch("src.meshmon.pulsewave.store.ClockPulseGenerator"),
        patch(
            "src.meshmon.pulsewave.store.get_clock_table_handler",
            return_value=(mock_matcher, mock_handler),
        ),
        patch(
            "src.meshmon.pulsewave.store.get_pulse_table_handler",
            return_value=(mock_matcher, mock_handler),
        ),
        patch(
            "src.meshmon.pulsewave.store.get_data_update_handler",
            return_value=(mock_matcher, mock_handler),
        ),
    ):
        store = SharedStore(pulse_config, mock_update_handler)
        store.update_manager = mock_update_manager.return_value
        return store


@pytest.fixture
def filled_shared_store(shared_store, mock_signer):
    """Create SharedStore with some initial data."""
    shared_store.store.nodes[mock_signer.node_id] = Mock()
    shared_store.store.nodes[mock_signer.node_id].values = {
        "value1": Mock(),
        "value2": Mock(),
    }
    shared_store.store.nodes[mock_signer.node_id].contexts = {
        "context1": Mock(),
        "context2": Mock(),
    }
    return shared_store
