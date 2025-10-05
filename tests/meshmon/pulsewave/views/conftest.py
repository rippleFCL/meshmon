"""Shared fixtures for PulseWave views testing."""

from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from src.meshmon.pulsewave.crypto import Signer
from src.meshmon.pulsewave.data import (
    SignedBlockData,
    StoreConsistencyData,
    StoreContextData,
)
from src.meshmon.pulsewave.update.update import UpdateManager


class TestModel(BaseModel):
    """Test model for view testing."""

    name: str
    value: int = 0
    description: str = "test"


@pytest.fixture
def mock_signer():
    """Create mock signer."""
    signer = Mock(spec=Signer)
    signer.node_id = "test_node"
    return signer


@pytest.fixture
def mock_update_manager():
    """Create mock update manager."""
    return Mock(spec=UpdateManager)


@pytest.fixture
def sample_context_data():
    """Create sample context data with test entries."""
    context_data = Mock(spec=StoreContextData)
    context_data.data = {}
    context_data.allowed_keys = None
    return context_data


@pytest.fixture
def populated_context_data(mock_signer):
    """Create context data populated with test signed blocks."""
    context_data = Mock(spec=StoreContextData)

    # Create mock signed block data
    signed_block1 = Mock(spec=SignedBlockData)
    signed_block1.data = {"name": "test1", "value": 10}

    signed_block2 = Mock(spec=SignedBlockData)
    signed_block2.data = {"name": "test2", "value": 20}

    context_data.data = {"item1": signed_block1, "item2": signed_block2}
    context_data.allowed_keys = None
    return context_data


@pytest.fixture
def mock_consistency_data():
    """Create mock consistency data."""
    consistency_data = Mock(spec=StoreConsistencyData)

    # Mock the various tables
    consistency_data.clock_table = Mock(spec=StoreContextData)
    consistency_data.clock_table.data = {}

    consistency_data.node_status_table = Mock(spec=StoreContextData)
    consistency_data.node_status_table.data = {}

    consistency_data.pulse_table = Mock(spec=StoreContextData)
    consistency_data.pulse_table.data = {}

    consistency_data.clock_pulse = None

    return consistency_data


@pytest.fixture
def sample_test_path():
    """Standard test path for views."""
    return "nodes.test_node.contexts.test_context"
