"""Test cases for MutableStoreCtxView class."""

from unittest.mock import Mock, patch

from pydantic import BaseModel

from src.meshmon.pulsewave.data import DateEvalType
from src.meshmon.pulsewave.views import MutableStoreCtxView


class SampleModel(BaseModel):
    """Test model for view testing."""

    name: str
    value: int = 0
    description: str = "test"


class TestMutableStoreCtxView:
    """Test cases for MutableStoreCtxView."""

    def test_initialization(
        self, sample_context_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test MutableStoreCtxView initialization."""

        view = MutableStoreCtxView(
            path=sample_test_path,
            context_data=sample_context_data,
            model=SampleModel,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        assert view.path == sample_test_path
        assert view.context_data == sample_context_data
        assert view.model == SampleModel
        assert view.signer == mock_signer
        assert view.update_handler == mock_update_manager

    def test_inherits_from_store_ctx_view(
        self, sample_context_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test that MutableStoreCtxView inherits StoreCtxView functionality."""

        view = MutableStoreCtxView(
            path=sample_test_path,
            context_data=sample_context_data,
            model=SampleModel,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        # Should have all parent class methods
        assert hasattr(view, "get")
        assert hasattr(view, "__len__")
        assert hasattr(view, "__contains__")
        assert hasattr(view, "__iter__")

    @patch("src.meshmon.pulsewave.views.SignedBlockData")
    def test_set_method_basic(
        self,
        mock_signed_block_cls,
        sample_context_data,
        mock_signer,
        mock_update_manager,
        sample_test_path,
    ):
        """Test set() method basic functionality."""

        # Mock SignedBlockData.new
        mock_signed_data = Mock()
        mock_signed_block_cls.new.return_value = mock_signed_data

        view = MutableStoreCtxView(
            path=sample_test_path,
            context_data=sample_context_data,
            model=SampleModel,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        test_data = SampleModel(name="test_item", value=42)

        view.set("test_key", test_data)

        # Should create signed block data
        mock_signed_block_cls.new.assert_called_once_with(
            mock_signer, test_data, block_id="test_key", rep_type=DateEvalType.NEWER
        )

        # Should store the signed data
        assert sample_context_data.data["test_key"] == mock_signed_data

        # Should trigger update
        mock_update_manager.trigger_update.assert_called_once_with(
            [f"{sample_test_path}.test_key"]
        )

    @patch("src.meshmon.pulsewave.views.SignedBlockData")
    def test_set_method_custom_rep_type(
        self,
        mock_signed_block_cls,
        sample_context_data,
        mock_signer,
        mock_update_manager,
        sample_test_path,
    ):
        """Test set() method with custom rep_type."""

        mock_signed_data = Mock()
        mock_signed_block_cls.new.return_value = mock_signed_data

        view = MutableStoreCtxView(
            path=sample_test_path,
            context_data=sample_context_data,
            model=SampleModel,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        test_data = SampleModel(name="test_item", value=42)

        view.set("test_key", test_data, DateEvalType.OLDER)

        # Should use custom rep_type
        mock_signed_block_cls.new.assert_called_once_with(
            mock_signer, test_data, block_id="test_key", rep_type=DateEvalType.OLDER
        )

    @patch("src.meshmon.pulsewave.views.logger")
    def test_set_method_restricted_key(
        self,
        mock_logger,
        sample_context_data,
        mock_signer,
        mock_update_manager,
        sample_test_path,
    ):
        """Test set() method with restricted keys."""

        # Set allowed keys restriction
        sample_context_data.allowed_keys = ["allowed_key"]

        view = MutableStoreCtxView(
            path=sample_test_path,
            context_data=sample_context_data,
            model=SampleModel,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        test_data = SampleModel(name="test_item", value=42)

        # Try to set a non-allowed key
        view.set("forbidden_key", test_data)

        # Should log warning and not set data
        mock_logger.warning.assert_called_once()
        assert "forbidden_key" not in sample_context_data.data
        mock_update_manager.trigger_update.assert_not_called()

    def test_allowed_keys_property_getter(
        self, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test allowed_keys property getter."""

        # Create context with allowed keys
        context_data = Mock()
        context_data.allowed_keys = ["key1", "key2", "key3"]
        context_data.data = {}

        view = MutableStoreCtxView(
            path=sample_test_path,
            context_data=context_data,
            model=SampleModel,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        allowed = view.allowed_keys

        # Should return a copy
        assert allowed == ["key1", "key2", "key3"]
        assert allowed is not context_data.allowed_keys  # Should be a copy

    def test_allowed_keys_property_setter(
        self, sample_context_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test allowed_keys property setter."""

        view = MutableStoreCtxView(
            path=sample_test_path,
            context_data=sample_context_data,
            model=SampleModel,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        new_keys = ["new_key1", "new_key2"]
        view.allowed_keys = new_keys

        # Should set allowed keys
        assert sample_context_data.allowed_keys == new_keys

        # Should trigger update
        mock_update_manager.trigger_update.assert_called_once_with(
            [f"{sample_test_path}.allowed_keys"]
        )

    def test_set_allowed_key_success(
        self, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test set() method with allowed key succeeds."""

        # Create context with allowed keys
        context_data = Mock()
        context_data.allowed_keys = ["allowed_key"]
        context_data.data = {}

        view = MutableStoreCtxView(
            path=sample_test_path,
            context_data=context_data,
            model=SampleModel,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        test_data = SampleModel(name="test_item", value=42)

        with patch(
            "src.meshmon.pulsewave.views.SignedBlockData"
        ) as mock_signed_block_cls:
            mock_signed_data = Mock()
            mock_signed_block_cls.new.return_value = mock_signed_data

            view.set("allowed_key", test_data)

            # Should succeed and store data
            assert context_data.data["allowed_key"] == mock_signed_data
            mock_update_manager.trigger_update.assert_called_once()

    def test_inherited_methods_work(
        self, populated_context_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test that inherited methods from StoreCtxView work correctly."""

        view = MutableStoreCtxView(
            path=sample_test_path,
            context_data=populated_context_data,
            model=SampleModel,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        # Test inherited functionality
        assert len(view) == 2
        assert "item1" in view
        assert "item2" in view

        result = view.get("item1")
        assert result is not None
        assert result.name == "test1"

        # Test iteration
        items = list(view)
        assert len(items) == 2
