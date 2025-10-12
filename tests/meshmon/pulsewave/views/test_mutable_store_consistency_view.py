"""Test cases for MutableStoreConsistencyView class."""

from unittest.mock import Mock, patch

from src.meshmon.pulsewave.data import (
    SignedBlockData,
    StoreClockPulse,
    StoreClockTableEntry,
    StoreNodeStatusEntry,
    StorePulseTableEntry,
)
from src.meshmon.pulsewave.views import MutableStoreConsistencyView, MutableStoreCtxView


class TestMutableStoreConsistencyView:
    """Test cases for MutableStoreConsistencyView."""

    def test_initialization(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test MutableStoreConsistencyView initialization."""
        view = MutableStoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        assert view.consistency_data == mock_consistency_data
        assert view.path == sample_test_path
        assert view.signer == mock_signer
        assert view.update_handler == mock_update_manager

    def test_inherits_from_store_consistency_view(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test that MutableStoreConsistencyView inherits from StoreConsistencyView."""
        view = MutableStoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        # Should have parent class properties
        assert hasattr(view, "clock_pulse")  # Both getter and setter

    def test_clock_table_property_returns_mutable(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test clock_table property returns MutableStoreCtxView."""
        view = MutableStoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        clock_table = view.clock_table

        assert isinstance(clock_table, MutableStoreCtxView)
        assert clock_table.path == f"{sample_test_path}.clock_table"
        assert clock_table.context_data == mock_consistency_data.clock_table
        assert clock_table.model == StoreClockTableEntry
        assert clock_table.signer == mock_signer
        assert clock_table.update_handler == mock_update_manager

    def test_node_status_table_property_returns_mutable(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test node_status_table property returns MutableStoreCtxView."""
        view = MutableStoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        node_status_table = view.node_status_table

        assert isinstance(node_status_table, MutableStoreCtxView)
        assert node_status_table.path == f"{sample_test_path}.node_status_table"
        assert node_status_table.context_data == mock_consistency_data.node_status_table
        assert node_status_table.model == StoreNodeStatusEntry
        assert node_status_table.signer == mock_signer
        assert node_status_table.update_handler == mock_update_manager

    def test_pulse_table_property_returns_mutable(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test pulse_table property returns MutableStoreCtxView."""
        view = MutableStoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        pulse_table = view.pulse_table

        assert isinstance(pulse_table, MutableStoreCtxView)
        assert pulse_table.path == f"{sample_test_path}.pulse_table"
        assert pulse_table.context_data == mock_consistency_data.pulse_table
        assert pulse_table.model == StorePulseTableEntry
        assert pulse_table.signer == mock_signer
        assert pulse_table.update_handler == mock_update_manager

    def test_clock_pulse_getter_delegates_to_parent(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test clock_pulse getter delegates to parent class."""
        # Create mock signed clock pulse data
        mock_signed_pulse = Mock(spec=SignedBlockData)
        mock_signed_pulse.data = {"date": "2023-10-01T12:00:00Z"}
        mock_consistency_data.clock_pulse = mock_signed_pulse

        view = MutableStoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        clock_pulse = view.clock_pulse

        assert clock_pulse is not None
        assert isinstance(clock_pulse, StoreClockPulse)

    @patch("src.meshmon.pulsewave.views.SignedBlockData")
    def test_clock_pulse_setter(
        self,
        mock_signed_block_cls,
        mock_consistency_data,
        mock_signer,
        mock_update_manager,
        sample_test_path,
    ):
        """Test clock_pulse setter functionality."""
        mock_signed_data = Mock()
        mock_signed_block_cls.new.return_value = mock_signed_data

        view = MutableStoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        # Create a test clock pulse
        from datetime import datetime

        test_pulse = StoreClockPulse(date=datetime.fromisoformat("2023-10-01T12:00:00"))

        view.clock_pulse = test_pulse

        # Should create signed block data
        mock_signed_block_cls.new.assert_called_once_with(
            mock_signer,
            test_pulse,
            path="nodes.test_node.contexts.test_context.clock_pulse",
            block_id="clock_pulse",
        )

        # Should store the signed data
        assert mock_consistency_data.clock_pulse == mock_signed_data

        # Should trigger update
        mock_update_manager.trigger_update.assert_called_once_with(
            [f"{sample_test_path}.clock_pulse"]
        )

    def test_clock_pulse_setter_none_consistency_data(
        self, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test clock_pulse setter when consistency_data is None."""
        view = MutableStoreConsistencyView(
            path=sample_test_path,
            consistency_data=None,  # type: ignore
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        from datetime import datetime

        test_pulse = StoreClockPulse(date=datetime.fromisoformat("2023-10-01T12:00:00"))

        # Should raise ValueError
        try:
            view.clock_pulse = test_pulse
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "Consistency data not found for the node" in str(e)

    def test_mutable_properties_independence(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test that mutable table properties return independent views."""
        view = MutableStoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        clock_table1 = view.clock_table
        clock_table2 = view.clock_table

        # Should return new instances each time (not cached)
        assert clock_table1 is not clock_table2
        assert clock_table1.path == clock_table2.path
        assert clock_table1.context_data == clock_table2.context_data
        assert clock_table1.update_handler == clock_table2.update_handler

    def test_clock_pulse_getter_with_none_data(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test clock_pulse getter when clock_pulse data is None."""
        mock_consistency_data.clock_pulse = None

        view = MutableStoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        clock_pulse = view.clock_pulse
        assert clock_pulse is None
