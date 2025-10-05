"""
Tests for pulsewave update handlers module.

Tests ClockTableHandler, PulseTableHandler, and DataEventHandler classes.
"""

import datetime
from unittest.mock import Mock, patch

from src.meshmon.pulsewave.data import StorePulseTableEntry
from src.meshmon.pulsewave.update.handlers import (
    ClockTableHandler,
    DataUpdateHandler,
    PulseTableHandler,
    get_clock_table_handler,
    get_data_event_handler,
    get_pulse_table_handler,
)
from src.meshmon.pulsewave.update.update import RegexPathMatcher


class TestClockTableHandler:
    """Test cases for ClockTableHandler class."""

    def test_init(self, pulse_config):
        """Test ClockTableHandler initialization."""
        handler = ClockTableHandler(pulse_config)

        assert handler.db_config == pulse_config
        assert handler.logger is not None

    def test_bind(self, pulse_config, mock_shared_store):
        """Test binding handler to store."""
        handler = ClockTableHandler(pulse_config)
        update_manager = Mock()

        handler.bind(mock_shared_store, update_manager)

        assert handler.store == mock_shared_store
        assert handler.update_manager == update_manager

    def test_handle_update_with_pulse_data(
        self, pulse_config, mock_signer, fixed_datetime
    ):
        """Test handling update with pulse data."""
        # Create mock store with consistency data
        store = Mock()
        consistency = Mock()
        clock_table = Mock()
        pulse_table = Mock()

        # Mock pulse table data
        pulse_entry = StorePulseTableEntry(
            current_pulse=fixed_datetime, current_time=fixed_datetime
        )
        pulse_table.get.return_value = pulse_entry

        # Mock node consistency
        node_consistency = Mock()
        node_consistency.pulse_table = pulse_table

        store.get_consistency.side_effect = (
            lambda node=None: consistency if node is None else node_consistency
        )
        store.nodes = [mock_signer.node_id]
        consistency.clock_table = clock_table

        # Create handler
        handler = ClockTableHandler(pulse_config)
        update_manager = Mock()
        handler.bind(store, update_manager)

        # Mock datetime for consistent testing
        with patch("src.meshmon.pulsewave.update.handlers.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value = (
                fixed_datetime + datetime.timedelta(seconds=10)
            )
            mock_datetime.timezone = datetime.timezone

            handler.handle_update()

            # Verify clock table was updated
            clock_table.set.assert_called_once()
            update_manager.trigger_event.assert_called_once_with("instant_update")

    def test_handle_update_no_pulse_data(self, pulse_config, mock_signer):
        """Test handling update when no pulse data is available."""
        store = Mock()
        consistency = Mock()
        clock_table = Mock()

        # Mock no pulse table
        node_consistency = Mock()
        node_consistency.pulse_table = None

        store.get_consistency.side_effect = (
            lambda node=None: consistency if node is None else node_consistency
        )
        store.nodes = [mock_signer.node_id]
        consistency.clock_table = clock_table

        handler = ClockTableHandler(pulse_config)
        update_manager = Mock()
        handler.bind(store, update_manager)

        handler.handle_update()

        # Should not update clock table when no pulse data
        clock_table.set.assert_not_called()

    def test_get_clock_table_handler(self, pulse_config):
        """Test factory function for clock table handler."""
        matcher, handler = get_clock_table_handler(pulse_config)

        assert isinstance(handler, ClockTableHandler)
        assert isinstance(matcher, RegexPathMatcher)


class TestPulseTableHandler:
    """Test cases for PulseTableHandler class."""

    def test_init(self):
        """Test PulseTableHandler initialization."""
        handler = PulseTableHandler()
        assert handler.logger is not None

    def test_bind(self, mock_shared_store):
        """Test binding handler to store."""
        handler = PulseTableHandler()
        update_manager = Mock()

        handler.bind(mock_shared_store, update_manager)

        assert handler.store == mock_shared_store
        assert handler.update_manager == update_manager

    def test_handle_update_with_clock_pulse(self, mock_signer, fixed_datetime):
        """Test handling update with clock pulse data."""
        # Create mock store structure
        store = Mock()
        consistency = Mock()
        pulse_table = Mock()

        # Mock clock pulse data
        clock_pulse = Mock()
        clock_pulse.date = fixed_datetime

        # Mock node consistency
        node_consistency = Mock()
        node_consistency.clock_pulse = clock_pulse

        store.get_consistency.side_effect = (
            lambda node=None: consistency if node is None else node_consistency
        )
        store.nodes = [mock_signer.node_id]
        consistency.pulse_table = pulse_table
        pulse_table.get.return_value = None  # No existing pulse entry

        # Create handler
        handler = PulseTableHandler()
        update_manager = Mock()
        handler.bind(store, update_manager)

        # Mock datetime
        with patch("src.meshmon.pulsewave.update.handlers.datetime") as mock_datetime:
            mock_datetime.datetime.now.return_value = fixed_datetime
            mock_datetime.timezone = datetime.timezone

            handler.handle_update()

            # Verify pulse table was updated
            pulse_table.set.assert_called_once()
            update_manager.trigger_event.assert_called_once_with("instant_update")

    def test_handle_update_no_clock_pulse(self, mock_signer):
        """Test handling update when no clock pulse is available."""
        store = Mock()
        consistency = Mock()
        pulse_table = Mock()

        # Mock no clock pulse
        node_consistency = Mock()
        node_consistency.clock_pulse = None

        store.get_consistency.side_effect = (
            lambda node=None: consistency if node is None else node_consistency
        )
        store.nodes = [mock_signer.node_id]
        consistency.pulse_table = pulse_table

        handler = PulseTableHandler()
        update_manager = Mock()
        handler.bind(store, update_manager)

        handler.handle_update()

        # Should not update pulse table when no clock pulse
        pulse_table.set.assert_not_called()

    def test_handle_update_existing_pulse_same_time(self, mock_signer, fixed_datetime):
        """Test handling update when existing pulse has same time."""
        store = Mock()
        consistency = Mock()
        pulse_table = Mock()

        # Mock clock pulse data
        clock_pulse = Mock()
        clock_pulse.date = fixed_datetime

        # Mock existing pulse entry with same time
        existing_pulse = Mock()
        existing_pulse.current_pulse = fixed_datetime

        node_consistency = Mock()
        node_consistency.clock_pulse = clock_pulse

        store.get_consistency.side_effect = (
            lambda node=None: consistency if node is None else node_consistency
        )
        store.nodes = [mock_signer.node_id]
        consistency.pulse_table = pulse_table
        pulse_table.get.return_value = existing_pulse

        handler = PulseTableHandler()
        update_manager = Mock()
        handler.bind(store, update_manager)

        handler.handle_update()

        # Should not update when pulse time is the same
        pulse_table.set.assert_not_called()

    def test_get_pulse_table_handler(self):
        """Test factory function for pulse table handler."""
        matcher, handler = get_pulse_table_handler()

        assert isinstance(handler, PulseTableHandler)
        assert isinstance(matcher, RegexPathMatcher)


class TestDataEventHandler:
    """Test cases for DataEventHandler class."""

    def test_init(self):
        """Test DataEventHandler initialization."""
        handler = DataUpdateHandler()
        assert handler.logger is not None

    def test_bind(self, mock_shared_store):
        """Test binding handler to store."""
        handler = DataUpdateHandler()
        update_manager = Mock()

        handler.bind(mock_shared_store, update_manager)

        assert handler.store == mock_shared_store
        assert handler.update_manager == update_manager

    def test_handle_update(self, mock_shared_store):
        """Test handling data events."""
        handler = DataUpdateHandler()
        update_manager = Mock()
        handler.bind(mock_shared_store, update_manager)

        handler.handle_update()

        update_manager.trigger_event.assert_called_once_with("update")

    def test_get_data_event_handler(self):
        """Test factory function for data event handler."""
        matcher, handler = get_data_event_handler()

        assert isinstance(handler, DataUpdateHandler)
        assert isinstance(matcher, RegexPathMatcher)

        # Test that matcher works with expected patterns
        assert matcher.matches("nodes.node1.values.key1")
        assert matcher.matches("nodes.node2.contexts.context1")
        assert not matcher.matches("nodes.node1.invalid.key1")
