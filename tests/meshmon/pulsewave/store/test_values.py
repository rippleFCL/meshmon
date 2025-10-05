from unittest.mock import Mock, patch

from pydantic import BaseModel

from src.meshmon.pulsewave.data import DateEvalType, SignedBlockData


class TestModel(BaseModel):
    """Test model for store operations."""

    name: str
    value: int


class TestSharedStoreValues:
    """Test cases for SharedStore value operations."""

    def test_values_iterator_empty_node(self, shared_store):
        """Test values iterator for node with no values."""
        values = list(shared_store.values("nonexistent"))
        assert len(values) == 0

    def test_values_iterator_current_node_empty(self, shared_store):
        """Test values iterator defaults to current node when empty."""
        values = list(shared_store.values())
        assert len(values) == 0

    def test_get_value_nonexistent_node(self, shared_store):
        """Test getting value from non-existent node."""
        result = shared_store.get_value(TestModel, "test", "nonexistent")
        assert result is None

    def test_get_value_nonexistent_value(self, shared_store):
        """Test getting non-existent value."""
        result = shared_store.get_value(TestModel, "nonexistent", "test_node")
        assert result is None

    def test_get_value_current_node_default(self, shared_store):
        """Test getting value defaults to current node."""
        result = shared_store.get_value(TestModel, "nonexistent")
        assert result is None

    def test_set_value_calls_signed_block_data(self, filled_shared_store, mock_signer):
        """Test setting a value calls SignedBlockData.new correctly."""
        test_data = TestModel(name="test_item", value=456)

        with patch.object(SignedBlockData, "new") as mock_new:
            mock_signed_data = Mock()
            mock_new.return_value = mock_signed_data

            filled_shared_store.set_value("test_key", test_data)

            # Verify SignedBlockData.new was called correctly
            mock_new.assert_called_once_with(
                mock_signer, test_data, block_id="test_key", rep_type=DateEvalType.NEWER
            )

    def test_set_value_works_empty_store(self, shared_store, mock_signer):
        """Test setting a value calls SignedBlockData.new correctly."""
        test_data = TestModel(name="test_item", value=456)

        with patch.object(SignedBlockData, "new") as mock_new:
            mock_signed_data = Mock()
            mock_new.return_value = mock_signed_data

            shared_store.set_value("test_key", test_data)

            # Verify SignedBlockData.new was called correctly
            mock_new.assert_called_once_with(
                mock_signer, test_data, block_id="test_key", rep_type=DateEvalType.NEWER
            )

    def test_set_value_with_custom_eval_type(self, shared_store, mock_signer):
        """Test setting value with custom evaluation type."""
        test_data = TestModel(name="test", value=789)

        with patch.object(SignedBlockData, "new") as mock_new:
            shared_store.set_value("test_key", test_data, DateEvalType.OLDER)

            mock_new.assert_called_once_with(
                mock_signer, test_data, block_id="test_key", rep_type=DateEvalType.OLDER
            )

    def test_set_value_with_default_eval_type(self, shared_store, mock_signer):
        """Test setting value uses NEWER as default evaluation type."""
        test_data = TestModel(name="default", value=123)

        with patch.object(SignedBlockData, "new") as mock_new:
            shared_store.set_value("default_key", test_data)

            # Should use DateEvalType.NEWER by default
            mock_new.assert_called_once_with(
                mock_signer,
                test_data,
                block_id="default_key",
                rep_type=DateEvalType.NEWER,
            )

    def test_values_iterator_interface(self, shared_store):
        """Test that values iterator has proper interface."""
        values_iter = shared_store.values()

        # Should be iterable
        assert hasattr(values_iter, "__iter__")

        # Should be able to convert to list
        values_list = list(values_iter)
        assert isinstance(values_list, list)

    def test_values_iterator_with_node_id(self, shared_store):
        """Test values iterator with specific node_id."""
        values_iter = shared_store.values("specific_node")

        # Should be iterable
        assert hasattr(values_iter, "__iter__")

        # Should return empty list for non-existent node
        values_list = list(values_iter)
        assert isinstance(values_list, list)
        assert len(values_list) == 0
