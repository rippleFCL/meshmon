"""Test cases for StoreCtxView class."""

from unittest.mock import Mock

from pydantic import BaseModel

from src.meshmon.pulsewave.data import SignedBlockData
from src.meshmon.pulsewave.views import StoreCtxView


class SampleModel(BaseModel):
    """Test model for view testing."""

    name: str
    value: int = 0
    description: str = "test"


class TestStoreCtxView:
    """Test cases for StoreCtxView."""

    def test_initialization(self, sample_context_data, mock_signer, sample_test_path):
        """Test StoreCtxView initialization."""

        view = StoreCtxView(
            path=sample_test_path,
            context_data=sample_context_data,
            model=SampleModel,
            signer=mock_signer,
        )

        assert view.path == sample_test_path
        assert view.context_data == sample_context_data
        assert view.model == SampleModel
        assert view.signer == mock_signer

    def test_len_empty_context(
        self, sample_context_data, mock_signer, sample_test_path
    ):
        """Test __len__ with empty context data."""

        view = StoreCtxView(
            path=sample_test_path,
            context_data=sample_context_data,
            model=SampleModel,
            signer=mock_signer,
        )

        assert len(view) == 0

    def test_len_populated_context(
        self, populated_context_data, mock_signer, sample_test_path
    ):
        """Test __len__ with populated context data."""

        view = StoreCtxView(
            path=sample_test_path,
            context_data=populated_context_data,
            model=SampleModel,
            signer=mock_signer,
        )

        assert len(view) == 2

    def test_contains_existing_key(
        self, populated_context_data, mock_signer, sample_test_path
    ):
        """Test __contains__ for existing key."""

        view = StoreCtxView(
            path=sample_test_path,
            context_data=populated_context_data,
            model=SampleModel,
            signer=mock_signer,
        )

        assert "item1" in view
        assert "item2" in view

    def test_contains_nonexistent_key(
        self, sample_context_data, mock_signer, sample_test_path
    ):
        """Test __contains__ for non-existent key."""

        view = StoreCtxView(
            path=sample_test_path,
            context_data=sample_context_data,
            model=SampleModel,
            signer=mock_signer,
        )

        assert "nonexistent" not in view

    def test_get_existing_key(
        self, populated_context_data, mock_signer, sample_test_path
    ):
        """Test get() method for existing key."""

        view = StoreCtxView(
            path=sample_test_path,
            context_data=populated_context_data,
            model=SampleModel,
            signer=mock_signer,
        )

        result = view.get("item1")
        assert result is not None
        assert isinstance(result, SampleModel)
        assert result.name == "test1"
        assert result.value == 10

    def test_get_nonexistent_key(
        self, populated_context_data, mock_signer, sample_test_path
    ):
        """Test get() method for non-existent key."""

        view = StoreCtxView(
            path=sample_test_path,
            context_data=populated_context_data,
            model=SampleModel,
            signer=mock_signer,
        )

        result = view.get("nonexistent")
        assert result is None

    def test_iteration_empty_context(
        self, sample_context_data, mock_signer, sample_test_path
    ):
        """Test iteration over empty context."""

        view = StoreCtxView(
            path=sample_test_path,
            context_data=sample_context_data,
            model=SampleModel,
            signer=mock_signer,
        )

        items = list(view)
        assert len(items) == 0

    def test_iteration_populated_context(
        self, populated_context_data, mock_signer, sample_test_path
    ):
        """Test iteration over populated context."""

        view = StoreCtxView(
            path=sample_test_path,
            context_data=populated_context_data,
            model=SampleModel,
            signer=mock_signer,
        )

        items = list(view)
        assert len(items) == 2

        # Check that we get key-value tuples
        for key, value in items:
            assert isinstance(key, str)
            assert isinstance(value, SampleModel)
            assert key in ["item1", "item2"]

    def test_iteration_with_invalid_data(self, mock_signer, sample_test_path):
        """Test iteration when some data is invalid."""

        # Create context with one valid and one invalid entry
        context_data = Mock()

        valid_signed_block = Mock(spec=SignedBlockData)
        valid_signed_block.data = {"name": "valid", "value": 5}

        invalid_signed_block = Mock(spec=SignedBlockData)
        invalid_signed_block.data = {
            "invalid_field": "bad_data"
        }  # Missing required fields

        context_data.data = {
            "valid": valid_signed_block,
            "invalid": invalid_signed_block,
        }

        view = StoreCtxView(
            path=sample_test_path,
            context_data=context_data,
            model=SampleModel,
            signer=mock_signer,
        )

        # Should raise validation error when iterating over invalid data
        try:
            list(view)
            assert False, "Expected ValidationError"
        except Exception as e:
            assert "ValidationError" in str(type(e))

    def test_get_with_model_validation_error(self, mock_signer, sample_test_path):
        """Test get() method when model validation fails."""

        context_data = Mock()
        invalid_signed_block = Mock(spec=SignedBlockData)
        invalid_signed_block.data = {
            "invalid_field": "bad_data"
        }  # Missing required fields

        context_data.data = {"invalid": invalid_signed_block}

        view = StoreCtxView(
            path=sample_test_path,
            context_data=context_data,
            model=SampleModel,
            signer=mock_signer,
        )

        # Should raise validation error for invalid data
        try:
            view.get("invalid")
            assert False, "Expected ValidationError"
        except Exception as e:
            assert "ValidationError" in str(type(e))
