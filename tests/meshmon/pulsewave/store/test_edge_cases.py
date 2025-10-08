"""Test SharedStore edge cases and error handling."""

from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel


class StoreTestModel(BaseModel):
    """Test model for store operations."""

    value: str
    count: int


class TestSharedStoreSecretValidation:
    """Test cases for secret validation in consistency contexts."""

    def test_get_consistency_context_with_new_secret(self, shared_store):
        """Test getting consistency context with a new secret."""
        # Mock ConsistencyContextView to avoid crypto operations
        with patch("src.meshmon.pulsewave.store.ConsistencyContextView") as mock_view:
            mock_view.return_value = Mock()

            view = shared_store.get_consistency_context(
                "secret_ctx", StoreTestModel, secret="my_secret"
            )

            assert view is not None
            # Secret should be added
            assert "secret_ctx" in shared_store.secret_store

    def test_get_consistency_context_with_matching_secret(self, shared_store):
        """Test getting consistency context with matching secret."""
        # Add secret first
        shared_store.secret_store.add_secret("test_ctx", "correct_secret")

        # Mock ConsistencyContextView to avoid crypto operations
        with patch("src.meshmon.pulsewave.store.ConsistencyContextView") as mock_view:
            mock_view.return_value = Mock()

            view = shared_store.get_consistency_context(
                "test_ctx", StoreTestModel, secret="correct_secret"
            )

            assert view is not None

    def test_get_consistency_context_with_wrong_secret(self, shared_store):
        """Test getting consistency context with wrong secret raises error."""
        # Add secret first
        shared_store.secret_store.add_secret("protected_ctx", "correct_secret")

        # Try to access with wrong secret
        with pytest.raises(ValueError, match="Invalid secret for context"):
            shared_store.get_consistency_context(
                "protected_ctx", StoreTestModel, secret="wrong_secret"
            )

    def test_get_consistency_context_without_secret(self, shared_store):
        """Test getting consistency context without secret when none is required."""
        # Mock ConsistencyContextView to avoid crypto operations
        with patch("src.meshmon.pulsewave.store.ConsistencyContextView") as mock_view:
            mock_view.return_value = Mock()

            view = shared_store.get_consistency_context("no_secret_ctx", StoreTestModel)

            assert view is not None


class TestSharedStoreConsistencyContextsIterator:
    """Test cases for all_consistency_contexts iterator."""

    def test_all_consistency_contexts_empty(self, shared_store):
        """Test all_consistency_contexts when no contexts exist."""
        contexts = list(shared_store.all_consistency_contexts())

        assert len(contexts) == 0

    def test_all_consistency_contexts_with_contexts(self, shared_store):
        """Test all_consistency_contexts returns all context names."""
        # Create consistency data with contexts
        from src.meshmon.pulsewave.data import (
            StoreConsistencyData,
            StoreConsistentContextData,
        )

        # Directly create consistency to avoid signing issues
        node_data = shared_store._get_node()
        consistency = Mock(spec=StoreConsistencyData)
        consistency.consistent_contexts = {
            "ctx1": Mock(spec=StoreConsistentContextData),
            "ctx2": Mock(spec=StoreConsistentContextData),
            "ctx3": Mock(spec=StoreConsistentContextData),
        }
        node_data.consistency = consistency

        contexts = list(shared_store.all_consistency_contexts())

        assert len(contexts) == 3
        assert "ctx1" in contexts
        assert "ctx2" in contexts
        assert "ctx3" in contexts

    def test_all_consistency_contexts_no_consistency_data(self, shared_store):
        """Test all_consistency_contexts when node has no consistency data."""
        # Force node to exist but with no consistency data
        node_data = shared_store._get_node()
        node_data.consistency = None

        contexts = list(shared_store.all_consistency_contexts())

        assert len(contexts) == 0


class TestSharedStoreGetContextEdgeCases:
    """Test edge cases for get_context method."""

    def test_get_context_other_node_with_context(self, shared_store):
        """Test getting context from other node when it exists."""
        # Create node with context
        from src.meshmon.pulsewave.data import StoreContextData, StoreNodeData

        node_data = StoreNodeData.new()
        mock_ctx = Mock(spec=StoreContextData)
        node_data.contexts["existing_ctx"] = mock_ctx
        shared_store.store.nodes["other_node"] = node_data

        with patch("src.meshmon.pulsewave.store.StoreCtxView") as mock_view:
            mock_view.return_value = Mock()

            result = shared_store.get_context(
                "existing_ctx", StoreTestModel, node_id="other_node"
            )

            assert result is not None

    def test_get_context_other_node_no_context(self, shared_store):
        """Test getting context from other node when context doesn't exist."""
        # Create node but no context
        from src.meshmon.pulsewave.data import StoreNodeData

        shared_store.store.nodes["other_node"] = StoreNodeData.new()

        result = shared_store.get_context(
            "missing_ctx", StoreTestModel, node_id="other_node"
        )

        assert result is None

    def test_get_context_current_node_creates_context(self, shared_store):
        """Test getting context for current node creates it if missing."""
        # Mock StoreContextData.new to avoid signing
        from src.meshmon.pulsewave.data import StoreContextData

        with patch.object(StoreContextData, "new") as mock_new:
            mock_ctx = Mock(spec=StoreContextData)
            mock_new.return_value = mock_ctx

            with patch("src.meshmon.pulsewave.store.MutableStoreCtxView") as mock_view:
                mock_view.return_value = Mock()

                result = shared_store.get_context("new_ctx", StoreTestModel)

                # Should return MutableStoreCtxView
                assert result is not None
                # Context should be created
                node_data = shared_store._get_node()
                assert "new_ctx" in node_data.contexts


class TestSharedStoreGetConsistencyEdgeCases:
    """Test edge cases for get_consistency method."""

    def test_get_consistency_other_node_not_found(self, shared_store):
        """Test getting consistency for non-existent node returns None."""
        result = shared_store.get_consistency(node_id="nonexistent_node")

        assert result is None

    def test_get_consistency_other_node_no_consistency(self, shared_store):
        """Test getting consistency from other node when it doesn't exist."""
        # Create node but no consistency
        from src.meshmon.pulsewave.data import StoreNodeData

        shared_store.store.nodes["other_node"] = StoreNodeData.new()

        # Force consistency to be None
        shared_store.store.nodes["other_node"].consistency = None

        result = shared_store.get_consistency(node_id="other_node")

        assert result is None

    def test_get_consistency_current_node_creates_consistency(self, shared_store):
        """Test getting consistency for current node creates it if missing."""
        # Force current node to have no consistency
        node_data = shared_store._get_node()
        node_data.consistency = None

        # Mock StoreConsistencyData.new to avoid signing
        from src.meshmon.pulsewave.data import StoreConsistencyData

        with patch.object(StoreConsistencyData, "new") as mock_new:
            mock_consistency = Mock(spec=StoreConsistencyData)
            mock_new.return_value = mock_consistency

            with patch(
                "src.meshmon.pulsewave.store.MutableStoreConsistencyView"
            ) as mock_view:
                mock_view.return_value = Mock()

                result = shared_store.get_consistency()

                # Should return MutableStoreConsistencyView
                assert result is not None
                # Consistency should be created
                node_data = shared_store._get_node()
                assert node_data.consistency is not None


class TestSharedStoreContextsIteratorEdgeCases:
    """Test edge cases for contexts iterator."""

    def test_contexts_with_nonexistent_node(self, shared_store):
        """Test contexts iterator with non-existent node."""
        contexts = list(shared_store.contexts(node_id="nonexistent"))

        assert len(contexts) == 0

    def test_contexts_current_node_empty(self, shared_store):
        """Test contexts iterator for current node with no contexts."""
        contexts = list(shared_store.contexts())

        # Should be empty since no contexts created yet
        assert len(contexts) == 0

    def test_contexts_with_contexts(self, shared_store):
        """Test contexts iterator returns context names."""
        # Create contexts directly in the store
        from src.meshmon.pulsewave.data import StoreContextData

        node_data = shared_store._get_node()
        node_data.contexts["ctx1"] = Mock(spec=StoreContextData)
        node_data.contexts["ctx2"] = Mock(spec=StoreContextData)

        contexts = list(shared_store.contexts())

        assert len(contexts) == 2
        assert "ctx1" in contexts
        assert "ctx2" in contexts

    def test_contexts_with_specific_node(self, shared_store):
        """Test contexts iterator for specific node."""
        # Create a specific node with contexts
        from src.meshmon.pulsewave.data import StoreContextData, StoreNodeData

        node_data = StoreNodeData.new()
        node_data.contexts["node_ctx1"] = Mock(spec=StoreContextData)
        node_data.contexts["node_ctx2"] = Mock(spec=StoreContextData)
        shared_store.store.nodes["specific_node"] = node_data

        contexts = list(shared_store.contexts(node_id="specific_node"))

        assert len(contexts) == 2
        assert "node_ctx1" in contexts
        assert "node_ctx2" in contexts


class TestSharedStoreValuesIteratorEdgeCases:
    """Test edge cases for values iterator."""

    def test_values_with_values(self, shared_store):
        """Test values iterator returns value IDs."""
        # Create values directly in the store
        from src.meshmon.pulsewave.data import SignedBlockData

        node_data = shared_store._get_node()
        node_data.values["val1"] = Mock(spec=SignedBlockData)
        node_data.values["val2"] = Mock(spec=SignedBlockData)

        values = list(shared_store.values())

        assert len(values) == 2
        assert "val1" in values
        assert "val2" in values

    def test_values_with_specific_node(self, shared_store):
        """Test values iterator for specific node."""
        # Create a specific node with values
        from src.meshmon.pulsewave.data import SignedBlockData, StoreNodeData

        node_data = StoreNodeData.new()
        node_data.values["node_val1"] = Mock(spec=SignedBlockData)
        node_data.values["node_val2"] = Mock(spec=SignedBlockData)
        shared_store.store.nodes["specific_node"] = node_data

        values = list(shared_store.values(node_id="specific_node"))

        assert len(values) == 2
        assert "node_val1" in values
        assert "node_val2" in values


class TestSharedStoreGetValueEdgeCases:
    """Test edge cases for get_value method."""

    def test_get_value_node_without_value(self, shared_store):
        """Test get_value when node exists but value doesn't."""
        # Create node
        _ = shared_store._get_node()

        result = shared_store.get_value("nonexistent", StoreTestModel)

        assert result is None

    def test_get_value_other_node_without_value(self, shared_store):
        """Test get_value for other node when value doesn't exist."""
        # Create other node
        from src.meshmon.pulsewave.data import StoreNodeData

        shared_store.store.nodes["other_node"] = StoreNodeData.new()

        result = shared_store.get_value(
            "test_value", StoreTestModel, node_id="other_node"
        )

        assert result is None

    def test_get_value_success(self, shared_store):
        """Test getting a value that exists."""
        # Create a value in the store
        from src.meshmon.pulsewave.data import SignedBlockData

        node_data = shared_store._get_node()
        test_data = {"value": "hello", "count": 42}
        mock_signed = Mock(spec=SignedBlockData)
        mock_signed.data = test_data
        node_data.values["test_val"] = mock_signed

        result = shared_store.get_value("test_val", StoreTestModel)

        assert result is not None
        assert result.value == "hello"
        assert result.count == 42
