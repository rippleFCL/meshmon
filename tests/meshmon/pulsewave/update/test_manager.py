"""
Tests for pulsewave update manager module.

Tests ClockPulseGenerator class.
"""

import datetime
from unittest.mock import Mock, patch

from src.meshmon.pulsewave.data import StoreClockPulse
from src.meshmon.pulsewave.update.manager import ClockPulseGenerator


class TestClockPulseGenerator:
    """Test cases for ClockPulseGenerator class."""

    def test_init(self, pulse_config, mock_shared_store):
        """Test ClockPulseGenerator initialization."""
        update_manager = Mock()

        # Mock threading to avoid actual threads
        with patch("src.meshmon.pulsewave.update.manager.Thread"):
            generator = ClockPulseGenerator(
                mock_shared_store, update_manager, pulse_config
            )

            assert generator.store == mock_shared_store
            assert generator.update_manager == update_manager
            assert generator.db_config == pulse_config

    def test_consistency_thread(self, pulse_config, mock_shared_store, fixed_datetime):
        """Test the consistency thread functionality."""
        update_manager = Mock()

        # Mock the consistency object
        consistency = Mock()
        mock_shared_store.get_consistency.return_value = consistency

        generator = ClockPulseGenerator(mock_shared_store, update_manager, pulse_config)

        # Mock time.sleep and datetime to control the loop
        with (
            patch("src.meshmon.pulsewave.update.manager.time.sleep") as mock_sleep,
            patch("src.meshmon.pulsewave.update.manager.datetime") as mock_datetime,
        ):
            mock_datetime.datetime.now.return_value = fixed_datetime
            mock_datetime.timezone = datetime.timezone

            # Mock sleep to raise exception after first iteration to exit loop
            mock_sleep.side_effect = [None, KeyboardInterrupt()]

            try:
                generator.consistency_thread()
            except KeyboardInterrupt:
                pass

            # Verify clock pulse was set
            assert isinstance(consistency.clock_pulse, StoreClockPulse)
            mock_sleep.assert_called_with(pulse_config.clock_pulse_interval)

    def test_consistency_thread_multiple_iterations(
        self, pulse_config, mock_shared_store, fixed_datetime
    ):
        """Test consistency thread runs multiple iterations."""
        update_manager = Mock()
        consistency = Mock()
        mock_shared_store.get_consistency.return_value = consistency

        generator = ClockPulseGenerator(mock_shared_store, update_manager, pulse_config)

        with (
            patch("src.meshmon.pulsewave.update.manager.time.sleep") as mock_sleep,
            patch("src.meshmon.pulsewave.update.manager.datetime") as mock_datetime,
        ):
            # Create different timestamps for each iteration
            timestamps = [
                fixed_datetime,
                fixed_datetime + datetime.timedelta(seconds=5),
                fixed_datetime + datetime.timedelta(seconds=10),
            ]
            mock_datetime.datetime.now.side_effect = timestamps
            mock_datetime.timezone = datetime.timezone

            # Run for 2 iterations then stop
            mock_sleep.side_effect = [None, None, KeyboardInterrupt()]

            try:
                generator.consistency_thread()
            except KeyboardInterrupt:
                pass

            # Verify multiple clock pulses were set
            assert consistency.clock_pulse is not None
            # Sleep should be called for each iteration
            assert mock_sleep.call_count == 3  # 2 successful + 1 that raises exception

    def test_consistency_thread_updates_store(
        self, pulse_config, mock_shared_store, fixed_datetime
    ):
        """Test that consistency thread updates the store's consistency data."""
        update_manager = Mock()
        consistency = Mock()
        mock_shared_store.get_consistency.return_value = consistency

        generator = ClockPulseGenerator(mock_shared_store, update_manager, pulse_config)

        with (
            patch("src.meshmon.pulsewave.update.manager.time.sleep") as mock_sleep,
            patch("src.meshmon.pulsewave.update.manager.datetime") as mock_datetime,
        ):
            mock_datetime.datetime.now.return_value = fixed_datetime
            mock_datetime.timezone = datetime.timezone
            mock_sleep.side_effect = [KeyboardInterrupt()]  # Exit after first iteration

            try:
                generator.consistency_thread()
            except KeyboardInterrupt:
                pass

            # Verify store's consistency was accessed
            mock_shared_store.get_consistency.assert_called()

            # Verify clock pulse was assigned with correct timestamp
            assert consistency.clock_pulse.date == fixed_datetime
