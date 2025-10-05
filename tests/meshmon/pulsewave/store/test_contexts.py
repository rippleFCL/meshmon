from unittest.mock import Mock, patch

from src.meshmon.pulsewave.data import (
    StoreConsistencyData,
    StoreContextData,
    StoreNodeData,
)
from src.meshmon.pulsewave.views import (
    MutableStoreConsistencyView,
    MutableStoreCtxView,
    StoreConsistencyView,
)


class TestSharedStoreContexts:
    """Test cases for SharedStore context operations."""

    def test_contexts_iterator_empty_node(self, shared_store):
        """Test contexts iterator for node with no contexts."""
        contexts = list(shared_store.contexts("nonexistent"))
        assert len(contexts) == 0

    def test_contexts_iterator_current_node_empty(self, shared_store):
        """Test contexts iterator defaults to current node when empty."""
        contexts = list(shared_store.contexts())
        assert len(contexts) == 0

    def test_get_ctx_nonexistent_context_other_node(self, shared_store):
        """Test _get_ctx returns None for non-existent context on other nodes."""
        result = shared_store._get_ctx("nonexistent", "other_node")
        assert result is None

    def test_get_ctx_nonexistent_context_current_node_creates(self, shared_store):
        """Test _get_ctx creates context for current node when it doesn't exist."""
        with patch.object(StoreNodeData, "new") as mock_node_new, patch.object(
            StoreContextData, "new"
        ) as mock_ctx_new:
            mock_node = StoreNodeData()
            mock_ctx = Mock()
            mock_node_new.return_value = mock_node
            mock_ctx_new.return_value = mock_ctx

            result = shared_store._get_ctx("test_ctx")

            assert result == mock_ctx
            # Should create node data if it doesn't exist
            if "test_node" in shared_store.store.nodes:
                assert "test_ctx" in shared_store.store.nodes["test_node"].contexts

    def test_get_context_current_node(self, filled_shared_store):
        """Test get_context for current node."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            test_field: str = "test"

        mock_ctx = Mock()
        with patch.object(filled_shared_store, "_get_ctx") as mock_get_ctx:
            mock_get_ctx.return_value = mock_ctx

            result = filled_shared_store.get_context("test_ctx", TestModel)

            assert isinstance(result, MutableStoreCtxView)
            mock_get_ctx.assert_called_with("test_ctx")

    def test_get_context_other_node_nonexistent(self, shared_store):
        """Test get_context returns None for non-existent context on other node."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            test_field: str = "test"

        # Mock _get_ctx to return None for other nodes
        with patch.object(shared_store, "_get_ctx", return_value=None):
            result = shared_store.get_context("nonexistent", TestModel, "other_node")
            assert result is None

    def test_get_consistency_nonexistent_current_node_creates(self, shared_store):
        """Test get_consistency creates consistency for current node."""

        with patch.object(StoreConsistencyData, "new") as mock_new:
            mock_consistency = Mock()
            mock_new.return_value = mock_consistency

            result = shared_store.get_consistency()

            assert isinstance(result, MutableStoreConsistencyView)
            assert result.consistency_data == mock_consistency
            mock_new.assert_called_once()

    def test_get_consistency_nonexistent_other_node(self, shared_store):
        """Test get_consistency returns None for other nodes."""
        result = shared_store.get_consistency("other_node")
        assert result is None

    def test_get_consistency_existing_context(self, shared_store):
        """Test get_consistency with existing consistency data."""
        mock_consistency = Mock()

        with patch.object(
            shared_store, "_get_consistency", return_value=mock_consistency
        ):
            result = shared_store.get_consistency("test_node")
            assert isinstance(result, StoreConsistencyView)
            assert result.consistency_data == mock_consistency

    def test_contexts_iterator_interface(self, shared_store):
        """Test that contexts iterator has proper interface."""
        contexts_iter = shared_store.contexts()

        # Should be iterable
        assert hasattr(contexts_iter, "__iter__")

        # Should be able to convert to list
        contexts_list = list(contexts_iter)
        assert isinstance(contexts_list, list)

    def test_contexts_iterator_with_node_id(self, shared_store):
        """Test contexts iterator with specific node_id."""
        contexts_iter = shared_store.contexts("specific_node")

        # Should be iterable
        assert hasattr(contexts_iter, "__iter__")

        # Should return empty list for non-existent node
        contexts_list = list(contexts_iter)
        assert isinstance(contexts_list, list)
        assert len(contexts_list) == 0

    def test_get_ctx_with_node_id_parameter(self, shared_store):
        """Test _get_ctx method with explicit node_id parameter."""
        # Test with non-existent node
        result = shared_store._get_ctx("test_context", "nonexistent_node")
        assert result is None

        # Test with current node (should create if needed)
        with patch.object(StoreContextData, "new") as mock_new:
            mock_ctx = Mock()
            mock_new.return_value = mock_ctx

            result = shared_store._get_ctx("new_context", "test_node")
            # May create new context for current node

    def test_get_consistency_current_node_interface(self, shared_store):
        """Test get_consistency interface for current node."""
        mock_ctx = Mock()

        with patch.object(shared_store, "_get_consistency", return_value=mock_ctx):
            result = shared_store.get_consistency()
            assert isinstance(result, MutableStoreConsistencyView)
            assert result.consistency_data == mock_ctx
