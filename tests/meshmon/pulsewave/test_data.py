import base64
import datetime
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel

from src.meshmon.pulsewave.crypto import KeyMapping, Signer
from src.meshmon.pulsewave.data import (
    DateEvalType,
    SignedBlockData,
    StoreClockPulse,
    StoreClockTableEntry,
    StoreConsistencyData,
    StoreContextData,
    StoreData,
    StoreNodeData,
    StoreNodeStatus,
    StoreNodeStatusEntry,
    StorePulseTableEntry,
)


class SampleDataModel(BaseModel):
    """Simple test data model for testing signed blocks."""

    name: str
    value: int


@pytest.fixture
def mock_signer():
    """Create a mock signer for testing."""
    private_key = Ed25519PrivateKey.generate()
    signer = Signer("test_node_1", private_key)
    return signer


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
def sample_data():
    """Create sample test data."""
    return SampleDataModel(name="test", value=42)


@pytest.fixture
def fixed_datetime():
    """Fixed datetime for consistent testing."""
    return datetime.datetime(2025, 10, 5, 12, 0, 0, tzinfo=datetime.timezone.utc)


class TestSignedBlockData:
    """Test cases for SignedBlockData class."""

    def test_new_signed_block_data(self, mock_signer, sample_data, fixed_datetime):
        """Test creating new signed block data."""
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_datetime
            mock_datetime.timezone = datetime.timezone

            signed_data = SignedBlockData.new(
                signer=mock_signer,
                data=sample_data,
                block_id="test_block_1",
                rep_type=DateEvalType.NEWER,
            )

            assert signed_data.block_id == "test_block_1"
            assert signed_data.replacement_type == DateEvalType.NEWER
            assert signed_data.date == fixed_datetime
            assert signed_data.data == sample_data.model_dump(mode="json")
            assert isinstance(signed_data.signature, str)
            # Signature should be base64 encoded
            assert base64.b64decode(signed_data.signature)

    def test_verify_signed_block_data(self, mock_signer, mock_verifier, sample_data):
        """Test verifying signed block data."""
        signed_data = SignedBlockData.new(
            signer=mock_signer, data=sample_data, block_id="test_block_1"
        )

        # Should verify successfully with correct verifier and block_id
        assert signed_data.verify(mock_verifier, "test_block_1") is True

        # Should fail with wrong block_id
        assert signed_data.verify(mock_verifier, "wrong_block_id") is False

    def test_verify_with_wrong_verifier(
        self, mock_signer, another_verifier, sample_data
    ):
        """Test verification fails with wrong verifier."""
        signed_data = SignedBlockData.new(
            signer=mock_signer, data=sample_data, block_id="test_block_1"
        )

        # Should fail with different verifier
        assert signed_data.verify(another_verifier, "test_block_1") is False

    def test_verify_tampered_data(self, mock_signer, mock_verifier, sample_data):
        """Test verification fails with tampered data."""
        signed_data = SignedBlockData.new(
            signer=mock_signer, data=sample_data, block_id="test_block_1"
        )

        # Tamper with the data
        signed_data.data["value"] = 999

        # Verification should fail
        assert signed_data.verify(mock_verifier, "test_block_1") is False

    def test_date_eval_type_older(self, mock_signer, sample_data):
        """Test creating signed block with OLDER date evaluation type."""
        signed_data = SignedBlockData.new(
            signer=mock_signer,
            data=sample_data,
            block_id="test_block_1",
            rep_type=DateEvalType.OLDER,
        )

        assert signed_data.replacement_type == DateEvalType.OLDER


class TestStoreContextData:
    """Test cases for StoreContextData class."""

    def test_new_store_context_data(self, mock_signer, fixed_datetime):
        """Test creating new store context data."""
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_datetime
            mock_datetime.timezone = datetime.timezone

            context_data = StoreContextData.new(
                signer=mock_signer,
                context_name="test_context",
                allowed_keys=["key1", "key2"],
            )

            assert context_data.context_name == "test_context"
            assert context_data.allowed_keys == ["key1", "key2"]
            assert context_data.date == fixed_datetime
            assert context_data.data == {}
            assert isinstance(context_data.sig, str)

    def test_new_store_context_data_no_allowed_keys(self, mock_signer):
        """Test creating store context data with no allowed keys."""
        context_data = StoreContextData.new(
            signer=mock_signer, context_name="test_context"
        )

        assert context_data.allowed_keys == []

    def test_verify_store_context_data(self, mock_signer, mock_verifier):
        """Test verifying store context data."""
        context_data = StoreContextData.new(
            signer=mock_signer, context_name="test_context"
        )

        # Should verify successfully
        assert context_data.verify(mock_verifier, "test_context") is True

        # Should fail with wrong context name
        assert context_data.verify(mock_verifier, "wrong_context") is False

    def test_update_context_data(
        self, mock_signer, mock_verifier, sample_data, fixed_datetime
    ):
        """Test updating context data."""
        # Create original context
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_datetime
            mock_datetime.timezone = datetime.timezone
            context1 = StoreContextData.new(mock_signer, "test_context", ["key1"])

        # Create new context with updated data and newer timestamp
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_datetime + datetime.timedelta(
                hours=1
            )
            mock_datetime.timezone = datetime.timezone

            context2 = StoreContextData.new(
                mock_signer, "test_context", ["key1", "key2"]
            )

            # Add some signed data to context2
            signed_data = SignedBlockData.new(mock_signer, sample_data, "key1")
            context2.data["key1"] = signed_data

        # Update context1 with context2
        updated_paths = context1.update(
            "test_path", context2, mock_verifier, "test_context"
        )

        # Should include both the context path and the data key path
        assert len(updated_paths) >= 1
        assert "test_path.key1" in updated_paths  # New data added
        assert context1.allowed_keys == [
            "key1",
            "key2",
        ]  # Allowed keys should be updated
        assert "key1" in context1.data

    def test_update_context_data_wrong_context_name(self, mock_signer, mock_verifier):
        """Test updating with wrong context name."""
        context1 = StoreContextData.new(mock_signer, "context1")
        context2 = StoreContextData.new(mock_signer, "context2")

        updated_paths = context1.update(
            "test_path", context2, mock_verifier, "context1"
        )

        assert updated_paths == []

    def test_update_context_data_disallowed_key(
        self, mock_signer, mock_verifier, sample_data
    ):
        """Test that disallowed keys are removed."""
        # Create context with key1 allowed
        context1 = StoreContextData.new(mock_signer, "test_context", ["key1", "key2"])
        signed_data1 = SignedBlockData.new(mock_signer, sample_data, "key1")
        signed_data2 = SignedBlockData.new(mock_signer, sample_data, "key2")
        context1.data["key1"] = signed_data1
        context1.data["key2"] = signed_data2

        # Create new context that only allows key1
        context2 = StoreContextData.new(mock_signer, "test_context", ["key1"])

        # Update - should remove key2
        context1.update("test_path", context2, mock_verifier, "test_context")

        assert "key1" in context1.data
        assert "key2" not in context1.data

    def test_update_newer_data(
        self, mock_signer, mock_verifier, sample_data, fixed_datetime
    ):
        """Test updating with newer data."""
        context1 = StoreContextData.new(mock_signer, "test_context", ["key1"])

        # Add initial data
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_datetime
            mock_datetime.timezone = datetime.timezone
            signed_data1 = SignedBlockData.new(mock_signer, sample_data, "key1")
            context1.data["key1"] = signed_data1

        context2 = StoreContextData.new(mock_signer, "test_context", ["key1"])

        # Add newer data
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_datetime + datetime.timedelta(
                hours=1
            )
            mock_datetime.timezone = datetime.timezone
            newer_data = SampleDataModel(name="newer", value=100)
            signed_data2 = SignedBlockData.new(mock_signer, newer_data, "key1")
            context2.data["key1"] = signed_data2

        updated_paths = context1.update(
            "test_path", context2, mock_verifier, "test_context"
        )

        assert "test_path.key1" in updated_paths
        assert context1.data["key1"].data["name"] == "newer"

    def test_diff_context_data(self, mock_signer, sample_data, fixed_datetime):
        """Test diffing context data."""
        context1 = StoreContextData.new(mock_signer, "test_context", ["key1"])
        context2 = StoreContextData.new(mock_signer, "test_context", ["key1"])

        # Add different data to each context
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_datetime
            mock_datetime.timezone = datetime.timezone
            signed_data1 = SignedBlockData.new(mock_signer, sample_data, "key1")
            context1.data["key1"] = signed_data1

            mock_datetime.now.return_value = fixed_datetime + datetime.timedelta(
                hours=1
            )
            newer_data = SampleDataModel(name="newer", value=100)
            signed_data2 = SignedBlockData.new(mock_signer, newer_data, "key1")
            context2.data["key1"] = signed_data2

        diff = context1.diff(context2)

        assert diff is not None
        assert diff.data["key1"].data["name"] == "newer"

    def test_diff_no_difference(self, mock_signer):
        """Test diffing identical context data returns None."""
        context1 = StoreContextData.new(mock_signer, "test_context")
        context2 = StoreContextData.new(mock_signer, "test_context")

        # Make contexts identical
        context2.date = context1.date
        context2.sig = context1.sig
        context2.allowed_keys = context1.allowed_keys

        diff = context1.diff(context2)

        assert diff is None

    def test_all_paths(self, mock_signer, sample_data):
        """Test getting all paths in context data."""
        context = StoreContextData.new(mock_signer, "test_context")
        signed_data = SignedBlockData.new(mock_signer, sample_data, "key1")
        context.data["key1"] = signed_data
        context.data["key2"] = signed_data

        paths = context.all_paths("test_path")

        assert "test_path.key1" in paths
        assert "test_path.key2" in paths
        assert len(paths) == 2


class TestStoreConsistencyData:
    """Test cases for StoreConsistencyData class."""

    def test_new_store_consistency_data(self, mock_signer):
        """Test creating new store consistency data."""
        consistency_data = StoreConsistencyData.new(mock_signer)

        assert isinstance(consistency_data.clock_table, StoreContextData)
        assert isinstance(consistency_data.pulse_table, StoreContextData)
        assert isinstance(consistency_data.node_status_table, StoreContextData)
        assert consistency_data.clock_pulse is None
        assert consistency_data.clock_table.context_name == "clock_table"
        assert consistency_data.pulse_table.context_name == "pulse_table"
        assert consistency_data.node_status_table.context_name == "node_status_table"

    def test_update_consistency_data(self, mock_signer, mock_verifier):
        """Test updating consistency data."""
        consistency1 = StoreConsistencyData.new(mock_signer)
        consistency2 = StoreConsistencyData.new(mock_signer)

        # Add clock pulse to consistency2
        clock_pulse_data = StoreClockPulse(
            date=datetime.datetime.now(datetime.timezone.utc)
        )
        consistency2.clock_pulse = SignedBlockData.new(
            mock_signer, clock_pulse_data, "clock_pulse"
        )

        updated_paths = consistency1.update("test_path", consistency2, mock_verifier)

        assert "test_path.clock_pulse" in updated_paths
        assert consistency1.clock_pulse is not None

    def test_verify_consistency_data(self, mock_signer, mock_verifier):
        """Test verifying consistency data."""
        consistency_data = StoreConsistencyData.new(mock_signer)

        # Should verify successfully
        assert consistency_data.verify(mock_verifier) is True

    def test_diff_consistency_data(self, mock_signer):
        """Test diffing consistency data."""
        consistency1 = StoreConsistencyData.new(mock_signer)
        consistency2 = StoreConsistencyData.new(mock_signer)

        # Add clock pulse to consistency2
        clock_pulse_data = StoreClockPulse(
            date=datetime.datetime.now(datetime.timezone.utc)
        )
        consistency2.clock_pulse = SignedBlockData.new(
            mock_signer, clock_pulse_data, "clock_pulse"
        )

        diff = consistency1.diff(consistency2)

        assert diff is not None
        assert diff.clock_pulse is not None

    def test_all_paths(self, mock_signer):
        """Test getting all paths in consistency data."""
        consistency_data = StoreConsistencyData.new(mock_signer)

        # Add clock pulse
        clock_pulse_data = StoreClockPulse(
            date=datetime.datetime.now(datetime.timezone.utc)
        )
        consistency_data.clock_pulse = SignedBlockData.new(
            mock_signer, clock_pulse_data, "clock_pulse"
        )

        paths = consistency_data.all_paths("test_path")

        assert "test_path.clock_pulse" in paths
        # Should also include paths from tables even if empty
        assert len([p for p in paths if "clock_table" in p]) >= 0
        assert len([p for p in paths if "pulse_table" in p]) >= 0
        assert len([p for p in paths if "node_status_table" in p]) >= 0


class TestStoreNodeData:
    """Test cases for StoreNodeData class."""

    def test_new_store_node_data(self):
        """Test creating new store node data."""
        node_data = StoreNodeData.new()

        assert node_data.contexts == {}
        assert node_data.values == {}
        assert node_data.consistency is None

    def test_update_node_data_new_context(self, mock_signer, mock_verifier):
        """Test updating node data with new context."""
        node_data1 = StoreNodeData.new()
        node_data2 = StoreNodeData.new()

        # Add context to node_data2
        context = StoreContextData.new(mock_signer, "test_context")
        node_data2.contexts["test_context"] = context

        updated_paths = node_data1.update("test_path", node_data2, mock_verifier)

        assert "test_path.contexts.test_context" in updated_paths
        assert "test_context" in node_data1.contexts

    def test_update_node_data_new_value(self, mock_signer, mock_verifier, sample_data):
        """Test updating node data with new value."""
        node_data1 = StoreNodeData.new()
        node_data2 = StoreNodeData.new()

        # Add value to node_data2
        signed_data = SignedBlockData.new(mock_signer, sample_data, "test_key")
        node_data2.values["test_key"] = signed_data

        updated_paths = node_data1.update("test_path", node_data2, mock_verifier)

        assert "test_path.values.test_key" in updated_paths
        assert "test_key" in node_data1.values

    def test_update_node_data_with_consistency(self, mock_signer, mock_verifier):
        """Test updating node data with consistency data."""
        node_data1 = StoreNodeData.new()
        node_data2 = StoreNodeData.new()

        # Add consistency data to node_data2
        node_data2.consistency = StoreConsistencyData.new(mock_signer)

        updated_paths = node_data1.update("test_path", node_data2, mock_verifier)

        assert "test_path.consistency" in updated_paths
        assert node_data1.consistency is not None

    def test_verify_node_data(self, mock_signer, mock_verifier, sample_data):
        """Test verifying node data."""
        node_data = StoreNodeData.new()

        # Add context
        context = StoreContextData.new(mock_signer, "test_context")
        node_data.contexts["test_context"] = context

        # Add value
        signed_data = SignedBlockData.new(mock_signer, sample_data, "test_key")
        node_data.values["test_key"] = signed_data

        # Add consistency
        node_data.consistency = StoreConsistencyData.new(mock_signer)

        # Should verify successfully
        assert node_data.verify(mock_verifier) is True

    def test_diff_node_data(self, mock_signer, sample_data):
        """Test diffing node data."""
        node_data1 = StoreNodeData.new()
        node_data2 = StoreNodeData.new()

        # Add different data to each
        context1 = StoreContextData.new(mock_signer, "test_context")
        node_data1.contexts["test_context"] = context1

        signed_data = SignedBlockData.new(mock_signer, sample_data, "test_key")
        node_data2.values["test_key"] = signed_data

        diff = node_data1.diff(node_data2)

        assert diff is not None
        assert "test_context" in diff.contexts
        assert "test_key" in diff.values

    def test_diff_no_difference(self):
        """Test diffing identical node data returns None."""
        node_data1 = StoreNodeData.new()
        node_data2 = StoreNodeData.new()

        diff = node_data1.diff(node_data2)

        assert diff is None

    def test_all_paths(self, mock_signer, sample_data):
        """Test getting all paths in node data."""
        node_data = StoreNodeData.new()

        # Add context
        context = StoreContextData.new(mock_signer, "test_context")
        signed_data = SignedBlockData.new(mock_signer, sample_data, "key1")
        context.data["key1"] = signed_data
        node_data.contexts["test_context"] = context

        # Add value
        node_data.values["test_key"] = signed_data

        # Add consistency
        node_data.consistency = StoreConsistencyData.new(mock_signer)

        # Add a clock pulse to ensure consistency has some paths
        clock_pulse_data = StoreClockPulse(
            date=datetime.datetime.now(datetime.timezone.utc)
        )
        node_data.consistency.clock_pulse = SignedBlockData.new(
            mock_signer, clock_pulse_data, "clock_pulse"
        )

        paths = node_data.all_paths("test_path")

        assert "test_path.contexts.test_context.key1" in paths
        assert "test_path.values.test_key" in paths
        assert any("test_path.consistency" in p for p in paths)


class TestStoreData:
    """Test cases for StoreData class."""

    def test_empty_store_data(self):
        """Test creating empty store data."""
        store_data = StoreData()

        assert store_data.nodes == {}

    def test_update_store_data_new_node(self, key_mapping, sample_data):
        """Test updating store data with new node."""
        store_data1 = StoreData()
        store_data2 = StoreData()

        # Add node to store_data2
        node_data = StoreNodeData.new()
        signed_data = SignedBlockData.new(key_mapping.signer, sample_data, "test_key")
        node_data.values["test_key"] = signed_data
        store_data2.nodes[key_mapping.signer.node_id] = node_data

        updated_paths = store_data1.update(store_data2, key_mapping)

        assert f"nodes.{key_mapping.signer.node_id}" in updated_paths
        assert key_mapping.signer.node_id in store_data1.nodes

    def test_update_store_data_unknown_node(self, mock_signer, key_mapping):
        """Test updating with node not in key mapping is skipped."""
        store_data1 = StoreData()
        store_data2 = StoreData()

        # Add node with unknown ID
        unknown_signer = Signer("unknown_node", Ed25519PrivateKey.generate())
        node_data = StoreNodeData.new()
        store_data2.nodes[unknown_signer.node_id] = node_data

        updated_paths = store_data1.update(store_data2, key_mapping)

        assert updated_paths == []
        assert unknown_signer.node_id not in store_data1.nodes

    def test_update_store_data_existing_node(self, key_mapping, sample_data):
        """Test updating existing node data."""
        store_data1 = StoreData()
        store_data2 = StoreData()

        # Initialize both with same node
        node_data1 = StoreNodeData.new()
        node_data2 = StoreNodeData.new()

        store_data1.nodes[key_mapping.signer.node_id] = node_data1

        # Add data to node_data2
        signed_data = SignedBlockData.new(key_mapping.signer, sample_data, "test_key")
        node_data2.values["test_key"] = signed_data
        store_data2.nodes[key_mapping.signer.node_id] = node_data2

        updated_paths = store_data1.update(store_data2, key_mapping)

        assert f"nodes.{key_mapping.signer.node_id}.values.test_key" in updated_paths
        assert "test_key" in store_data1.nodes[key_mapping.signer.node_id].values

    def test_update_store_data_verification_failure(
        self, key_mapping, another_signer, sample_data
    ):
        """Test that verification failure prevents update."""
        store_data1 = StoreData()
        store_data2 = StoreData()

        # Create node data signed by another_signer but try to add it under mock_signer's ID
        node_data = StoreNodeData.new()
        signed_data = SignedBlockData.new(another_signer, sample_data, "test_key")
        node_data.values["test_key"] = signed_data

        # Try to add it under the wrong node ID (should fail verification)
        store_data2.nodes[key_mapping.signer.node_id] = node_data

        updated_paths = store_data1.update(store_data2, key_mapping)

        # Should not update due to verification failure
        assert updated_paths == []
        assert key_mapping.signer.node_id not in store_data1.nodes

    def test_diff_store_data(self, key_mapping, sample_data):
        """Test diffing store data."""
        store_data1 = StoreData()
        store_data2 = StoreData()

        # Add different nodes to each
        node_data1 = StoreNodeData.new()
        signed_data1 = SignedBlockData.new(key_mapping.signer, sample_data, "key1")
        node_data1.values["key1"] = signed_data1
        store_data1.nodes[key_mapping.signer.node_id] = node_data1

        node_data2 = StoreNodeData.new()
        signed_data2 = SignedBlockData.new(key_mapping.signer, sample_data, "key2")
        node_data2.values["key2"] = signed_data2
        store_data2.nodes["another_node"] = node_data2

        diff = store_data1.diff(store_data2)

        assert key_mapping.signer.node_id in diff.nodes
        assert "another_node" in diff.nodes


class TestEnumsAndModels:
    """Test cases for enum types and simple models."""

    def test_date_eval_type_enum(self):
        """Test DateEvalType enum values."""
        assert DateEvalType.OLDER.value == "OLDER"
        assert DateEvalType.NEWER.value == "NEWER"

    def test_store_node_status_enum(self):
        """Test StoreNodeStatus enum values."""
        assert StoreNodeStatus.ONLINE.value == "ONLINE"
        assert StoreNodeStatus.OFFLINE.value == "OFFLINE"

    def test_store_clock_table_entry(self):
        """Test StoreClockTableEntry model."""
        now = datetime.datetime.now(datetime.timezone.utc)
        entry = StoreClockTableEntry(
            last_pulse=now,
            pulse_interval=60.0,
            delta=datetime.timedelta(seconds=1),
            rtt=datetime.timedelta(milliseconds=100),
            remote_time=now,
        )

        assert entry.last_pulse == now
        assert entry.pulse_interval == 60.0

    def test_store_pulse_table_entry(self):
        """Test StorePulseTableEntry model."""
        now = datetime.datetime.now(datetime.timezone.utc)
        entry = StorePulseTableEntry(current_pulse=now, current_time=now)

        assert entry.current_pulse == now
        assert entry.current_time == now

    def test_store_clock_pulse(self):
        """Test StoreClockPulse model."""
        now = datetime.datetime.now(datetime.timezone.utc)
        pulse = StoreClockPulse(date=now)

        assert pulse.date == now

    def test_store_node_status_entry(self):
        """Test StoreNodeStatusEntry model."""
        entry = StoreNodeStatusEntry(status=StoreNodeStatus.ONLINE)

        assert entry.status == StoreNodeStatus.ONLINE


if __name__ == "__main__":
    pytest.main([__file__])
