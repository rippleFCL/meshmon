"""Test cases for StoreConsistencyView class."""

from unittest.mock import Mock

from src.meshmon.pulsewave.data import (
    SignedBlockData,
    StoreClockPulse,
    StoreClockTableEntry,
    StoreNodeStatusEntry,
    StorePulseTableEntry,
)
from src.meshmon.pulsewave.views import StoreConsistencyView, StoreCtxView


class TestStoreConsistencyView:
    """Test cases for StoreConsistencyView."""

    def test_initialization(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test StoreConsistencyView initialization."""
        view = StoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        assert view.consistency_data == mock_consistency_data
        assert view.path == sample_test_path
        assert view.signer == mock_signer
        assert view.update_handler == mock_update_manager

    def test_clock_table_property(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test clock_table property returns StoreCtxView."""
        view = StoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        clock_table = view.clock_table

        assert isinstance(clock_table, StoreCtxView)
        assert clock_table.path == f"{sample_test_path}.clock_table"
        assert clock_table.context_data == mock_consistency_data.clock_table
        assert clock_table.model == StoreClockTableEntry
        assert clock_table.signer == mock_signer

    def test_node_status_table_property(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test node_status_table property returns StoreCtxView."""
        view = StoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        node_status_table = view.node_status_table

        assert isinstance(node_status_table, StoreCtxView)
        assert node_status_table.path == f"{sample_test_path}.node_status_table"
        assert node_status_table.context_data == mock_consistency_data.node_status_table
        assert node_status_table.model == StoreNodeStatusEntry
        assert node_status_table.signer == mock_signer

    def test_pulse_table_property(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test pulse_table property returns StoreCtxView."""
        view = StoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        pulse_table = view.pulse_table

        assert isinstance(pulse_table, StoreCtxView)
        assert pulse_table.path == f"{sample_test_path}.pulse_table"
        assert pulse_table.context_data == mock_consistency_data.pulse_table
        assert pulse_table.model == StorePulseTableEntry
        assert pulse_table.signer == mock_signer

    def test_clock_pulse_property_none_consistency_data(
        self, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test clock_pulse property when consistency_data is None."""
        view = StoreConsistencyView(
            path=sample_test_path,
            consistency_data=None,  # type: ignore
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        clock_pulse = view.clock_pulse
        assert clock_pulse is None

    def test_clock_pulse_property_none_clock_pulse(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test clock_pulse property when clock_pulse is None."""
        mock_consistency_data.clock_pulse = None

        view = StoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        clock_pulse = view.clock_pulse
        assert clock_pulse is None

    def test_clock_pulse_property_with_data(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test clock_pulse property with actual clock pulse data."""
        # Create mock signed clock pulse data
        mock_signed_pulse = Mock(spec=SignedBlockData)
        mock_signed_pulse.data = {"date": "2023-10-01T12:00:00Z"}
        mock_consistency_data.clock_pulse = mock_signed_pulse

        view = StoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        clock_pulse = view.clock_pulse

        assert clock_pulse is not None
        assert isinstance(clock_pulse, StoreClockPulse)

    def test_properties_with_none_consistency_data(
        self, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test all properties when consistency_data is None."""
        view = StoreConsistencyView(
            path=sample_test_path,
            consistency_data=None,  # type: ignore
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        assert view.clock_table is None
        assert view.node_status_table is None
        assert view.pulse_table is None
        assert view.clock_pulse is None

    def test_table_properties_independence(
        self, mock_consistency_data, mock_signer, mock_update_manager, sample_test_path
    ):
        """Test that table properties return independent views."""
        view = StoreConsistencyView(
            path=sample_test_path,
            consistency_data=mock_consistency_data,
            signer=mock_signer,
            update_handler=mock_update_manager,
        )

        clock_table1 = view.clock_table
        clock_table2 = view.clock_table

        # Should return new instances each time (not cached)
        assert clock_table1 is not clock_table2
        assert clock_table1.path == clock_table2.path  # type: ignore
        assert clock_table1.context_data == clock_table2.context_data  # type: ignore
