"""
Integration tests for the pulsewave update system.

These tests verify that the update components work together correctly,
including the critical event_loop and update_loop functions that run in threads.
"""

import datetime
from unittest.mock import Mock, patch

from src.meshmon.pulsewave.data import StoreConsistencyData
from src.meshmon.pulsewave.update.events import (
    LocalHandler,
    LocalStores,
    RateLimitedHandler,
)
from src.meshmon.pulsewave.update.handlers import (
    get_clock_table_handler,
    get_data_update_handler,
    get_pulse_table_handler,
)
from src.meshmon.pulsewave.update.manager import ClockPulseGenerator
from src.meshmon.pulsewave.update.update import UpdateManager


class TestUpdateLoopExecution:
    """Test the critical loop functions that execute in threads."""

    def test_update_loop_processes_updates(self, pulse_config, mock_shared_store):
        """Test that update_loop actually processes updates and calls handlers."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Create a mock handler that we can verify gets called
            handler = Mock()
            matcher = Mock()
            matcher.matches.return_value = True

            manager.add_handler(matcher, handler)

            # Add some updates to the queue
            manager.update_queue.add(["nodes.test_node.values.key1"])
            manager.update_queue.add(["nodes.test_node.contexts.context1"])

            # Run the update loop synchronously (one iteration)
            manager.update_loop()

            # Controller invokes each matching handler once per cycle
            assert handler.handle_update.call_count == 1

            # Verify idle is set after processing
            assert manager.idle.is_set()

    def test_event_loop_processes_events(self, pulse_config, mock_shared_store):
        """Test that event_loop actually processes events and calls handlers."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Create a mock event handler
            event_handler = Mock()
            event_matcher = Mock()
            event_matcher.matches.return_value = True

            manager.add_event_handler(event_matcher, event_handler)

            # Add events to the queue
            manager.event_queue.add(["instant_update"])
            manager.event_queue.add(["data_changed"])

            # Set idle so event loop doesn't wait
            manager.idle.set()

            # Run the event loop synchronously (one iteration)
            manager.event_loop()

            # Controller invokes each matching handler once per cycle
            assert event_handler.handle_update.call_count == 1

    def test_update_loop_waits_for_items(self, pulse_config, mock_shared_store):
        """Test that update_loop waits for items in the queue."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Mock wait_for_items to return False (timeout)
            with patch.object(
                manager.update_queue, "wait_for_items", return_value=False
            ) as mock_wait:
                # This should exit the loop without processing anything
                manager.update_loop()

                # Verify wait_for_items was called
                mock_wait.assert_called_once()

    def test_update_loop_processes_multiple_batches(
        self, pulse_config, mock_shared_store
    ):
        """Test that update_loop processes multiple batches until queue is empty."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            handler = Mock()
            matcher = Mock()
            matcher.matches.return_value = True
            manager.add_handler(matcher, handler)

            # Add multiple batches to the queue
            manager.update_queue.add(["batch1_path1", "batch1_path2"])
            manager.update_queue.add(["batch2_path1"])

            # Run update loop to process all batches
            manager.update_loop()

            # Controller invokes handler once per cycle despite multiple paths
            assert handler.handle_update.call_count == 1

    def test_event_loop_waits_for_idle(self, pulse_config, mock_shared_store):
        """Test that event_loop waits for idle state before processing."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            event_handler = Mock()
            event_matcher = Mock()
            event_matcher.matches.return_value = True
            manager.add_event_handler(event_matcher, event_handler)

            # Add an event to the queue
            manager.event_queue.add(["test_event"])

            # Clear idle state (simulating active updates)
            manager.idle.clear()

            # Mock idle.wait to return immediately (simulating it becomes idle)
            with patch.object(manager.idle, "wait", return_value=True) as mock_wait:
                manager.event_loop()

                # Verify it waited for idle
                mock_wait.assert_called_once()

                # Verify event was processed
                event_handler.handle_update.assert_called_once()


class TestUpdateSystemIntegration:
    """Integration tests for the update system."""

    def test_end_to_end_update_flow_with_loop_execution(
        self, pulse_config, mock_signer, fixed_datetime
    ):
        """Test complete update flow from trigger to handler execution via loops."""
        # Create store with real consistency data
        store = Mock()
        consistency = StoreConsistencyData.new(mock_signer)
        store.get_consistency.return_value = consistency
        store.nodes = []

        # Mock threading to avoid actual threads
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            # Create update manager
            manager = UpdateManager(pulse_config, store)

            # Create and add a data event handler - these are real handlers, not mocks
            matcher, handler = get_data_update_handler()
            manager.add_handler(matcher, handler)

            # Mock the handler's handle_update method to track calls
            with patch.object(
                handler, "handle_update", wraps=handler.handle_update
            ) as mock_handle:
                # Trigger an update that should match the pattern
                manager.trigger_update(["nodes.test_node.values.test_key"])

                # Verify update is in queue
                assert not manager.update_queue.empty

                # Run the update loop to process the update
                manager.update_loop()

                # Verify the handler's method was called
                mock_handle.assert_called_once()

            # Verify idle state is set after processing
            assert manager.idle.is_set()

    def test_real_handlers_integration_via_loops(self, pulse_config, mock_shared_store):
        """Test that the real handler factory functions work with the loop system."""
        # Set up mock store to avoid datetime calculation issues
        mock_shared_store.nodes = []  # Empty nodes list to avoid complex calculations

        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Add all the real handlers from factory functions
            clock_matcher, clock_handler = get_clock_table_handler(pulse_config)
            pulse_matcher, pulse_handler = get_pulse_table_handler()
            data_matcher, data_handler = get_data_update_handler()

            manager.add_handler(clock_matcher, clock_handler)
            manager.add_handler(pulse_matcher, pulse_handler)
            manager.add_handler(data_matcher, data_handler)

            # Mock the handle_update methods to track calls only
            with (
                patch.object(clock_handler, "handle_update") as mock_clock,
                patch.object(pulse_handler, "handle_update") as mock_pulse,
                patch.object(data_handler, "handle_update") as mock_data,
            ):
                node_id = pulse_config.current_node.node_id
                # Trigger updates that match each handler's patterns
                manager.trigger_update(
                    [f"nodes.{node_id}.consistency.pulse_table.{node_id}"]
                )  # clock handler
                manager.trigger_update(
                    [f"nodes.{node_id}.consistency.clock_pulse"]
                )  # pulse handler
                manager.trigger_update(
                    [f"nodes.{node_id}.values.some_key"]
                )  # data handler

                # Run the update loop to process all updates
                manager.update_loop()

                # Verify each handler was called by the update loop
                mock_clock.assert_called_once()
                mock_pulse.assert_called_once()
                mock_data.assert_called_once()

                # Verify idle state is set after processing
                assert manager.idle.is_set()

    def test_event_loop_with_real_local_handler(
        self, pulse_config, mock_shared_store, mock_signer, another_signer
    ):
        """Test event_loop processing with real LocalHandler."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Set up LocalStores
            stores = LocalStores()

            # Create LocalHandler as an event handler
            local_handler = LocalHandler(stores)

            # Create a matcher that matches any event (for testing purposes)
            event_matcher = Mock()
            event_matcher.matches.return_value = True

            # Add event handler - this will call bind() internally
            manager.add_event_handler(event_matcher, local_handler)

            # Mock the handle_update method to track calls - don't need to test what it does
            with patch.object(local_handler, "handle_update") as mock_handle:
                # Trigger an event and set idle
                manager.trigger_event("sync_request")
                manager.idle.set()

                # Run event loop once
                manager.event_loop()

                # Verify the event loop called the LocalHandler
                mock_handle.assert_called_once()

                # Verify the matcher was used to check the event
                event_matcher.matches.assert_called_once_with("sync_request")

    def test_clock_synchronization_setup(
        self, pulse_config, mock_signer, another_signer, fixed_datetime
    ):
        """Test setting up clock synchronization between nodes."""
        # Create mock store
        store = Mock()
        consistency = StoreConsistencyData.new(mock_signer)
        store.get_consistency.return_value = consistency
        store.nodes = [another_signer.node_id]

        # Mock threading
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, store)

            # Add clock table handler
            matcher, handler = get_clock_table_handler(pulse_config)
            manager.add_handler(matcher, handler)

            # Add pulse table handler
            pulse_matcher, pulse_handler = get_pulse_table_handler()
            manager.add_handler(pulse_matcher, pulse_handler)

            # Verify handlers are registered
            assert len(manager.update_controller.handlers) == 2

    def test_rate_limited_local_updates(self, mock_signer, another_signer):
        """Test rate-limited local store updates."""
        # Create local stores
        stores = LocalStores()

        store1 = Mock()
        store1.key_mapping.signer = mock_signer
        store1.dump.return_value = Mock()  # StoreData

        store2 = Mock()
        store2.key_mapping.signer = another_signer

        stores.add_store(store1)
        stores.add_store(store2)

        # Create rate limited handler
        local_handler = LocalHandler(stores)
        rate_limited = RateLimitedHandler(local_handler, 0.01)

        # Bind to store1
        rate_limited.bind(store1, Mock())

        # Trigger update
        rate_limited.handle_update()

        # Verify trigger is set
        assert rate_limited.trigger.is_set()

    def test_multiple_handler_coordination(
        self, pulse_config, mock_signer, fixed_datetime
    ):
        """Test coordination between multiple handlers."""
        store = Mock()
        consistency = StoreConsistencyData.new(mock_signer)
        store.get_consistency.return_value = consistency
        store.nodes = [mock_signer.node_id]

        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, store)

            # Add multiple handlers
            clock_matcher, clock_handler = get_clock_table_handler(pulse_config)
            pulse_matcher, pulse_handler = get_pulse_table_handler()
            data_matcher, data_handler = get_data_update_handler()

            manager.add_handler(clock_matcher, clock_handler)
            manager.add_handler(pulse_matcher, pulse_handler)
            manager.add_handler(data_matcher, data_handler)

            # Verify all handlers are registered
            assert len(manager.update_controller.handlers) == 3

    def test_clock_pulse_generator_integration(
        self, pulse_config, mock_signer, fixed_datetime
    ):
        """Test clock pulse generator with update manager."""
        store = Mock()
        consistency = StoreConsistencyData.new(mock_signer)
        store.get_consistency.return_value = consistency

        with patch("src.meshmon.pulsewave.update.update.Thread"), patch(
            "src.meshmon.pulsewave.update.manager.Thread"
        ):
            manager = UpdateManager(pulse_config, store)

            # Create clock pulse generator
            generator = ClockPulseGenerator(store, manager, pulse_config)

            # Verify they're connected
            assert generator.store == store
            assert generator.update_manager == manager

    def test_event_vs_update_queues(self, pulse_config, mock_shared_store):
        """Test that events and updates use separate queues."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Trigger both events and updates
            manager.trigger_event("test_event")
            manager.trigger_update(["test_update"])

            # They should be in separate queues
            events = manager.event_queue.pop_all()
            updates = manager.update_queue.pop_all()

            assert "test_event" in events
            assert "test_update" in updates
            assert len(events) == 1
            assert len(updates) == 1

    def test_handler_triggering_chain(self, pulse_config, mock_signer, fixed_datetime):
        """Test handlers triggering other events."""
        store = Mock()
        consistency = Mock()
        pulse_table = Mock()

        # Mock clock pulse that will trigger pulse table handler
        clock_pulse = Mock()
        clock_pulse.date = fixed_datetime

        node_consistency = Mock()
        node_consistency.clock_pulse = clock_pulse

        store.get_consistency.side_effect = (
            lambda node=None: consistency if node is None else node_consistency
        )
        store.nodes = [mock_signer.node_id]
        consistency.pulse_table = pulse_table
        pulse_table.get.return_value = None  # No existing pulse

        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, store)

            # Add pulse table handler
            matcher, handler = get_pulse_table_handler()
            manager.add_handler(matcher, handler)

            # Mock datetime for consistent testing
            with patch(
                "src.meshmon.pulsewave.update.handlers.datetime"
            ) as mock_datetime:
                mock_datetime.datetime.now.return_value = fixed_datetime
                mock_datetime.timezone = datetime.timezone

                # Simulate handler execution
                handler.handle_update()

                # Should trigger instant_update event
                # (This would normally be captured by event handlers)
                pulse_table.set.assert_called_once()

    def test_store_synchronization_scenario(self, mock_signer, another_signer):
        """Test a realistic store synchronization scenario."""
        # Create two stores that should sync with each other
        stores = LocalStores()

        # Store 1 - source of update
        store1 = Mock()
        store1.key_mapping.signer = mock_signer
        store1.dump.return_value = Mock()

        # Store 2 - receiver of update
        store2 = Mock()
        store2.key_mapping.signer = another_signer

        stores.add_store(store1)
        stores.add_store(store2)

        # Create local handler for synchronization
        local_handler = LocalHandler(stores)
        local_handler.bind(store1, Mock())

        # Simulate an update occurring in store1
        local_handler.handle_update()

        # Verify store1 data was sent to store2
        store1.dump.assert_called_once()
        store2.update_from_dump.assert_called_once()

        # Verify store1 didn't send to itself
        store1.update_from_dump.assert_not_called()

    def test_full_pipeline_with_rate_limiting(
        self, pulse_config, mock_signer, another_signer
    ):
        """Test full update pipeline with rate limiting."""
        # Set up stores
        stores = LocalStores()

        store1 = Mock()
        store1.key_mapping.signer = mock_signer
        store1.dump.return_value = Mock()

        store2 = Mock()
        store2.key_mapping.signer = another_signer

        stores.add_store(store1)
        stores.add_store(store2)

        # Set up update manager with handlers
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, store1)

            # Add data event handler that will trigger updates
            matcher, handler = get_data_update_handler()
            manager.add_handler(matcher, handler)

            # Create rate-limited local synchronization
            local_handler = LocalHandler(stores)
            rate_limited = RateLimitedHandler(local_handler, 0.01)
            rate_limited.bind(store1, manager)

            # Trigger a data update
            manager.trigger_update(["nodes.test_node.values.test_key"])

            # The system should be set up to:
            # 1. Process the update through the data handler
            # 2. Potentially trigger local synchronization
            # 3. Rate limit the synchronization

            # Verify components are connected
            assert len(manager.update_controller.handlers) == 1
            assert rate_limited.handler == local_handler
            assert rate_limited.min_interval == 0.01

    def test_event_loop_processing(self, pulse_config, mock_shared_store):
        """Test the critical event_loop method processes events correctly."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Add a mock event handler
            handler = Mock()
            matcher = Mock()
            matcher.matches.return_value = True
            manager.add_event_handler(matcher, handler)

            # Trigger an event
            manager.trigger_event("test_event")

            # Manually run the event loop once (synchronously)
            # First ensure we're idle so the event loop can proceed
            manager.idle.set()

            # Run the event loop
            manager.event_loop()

            # Verify the handler was called
            handler.handle_update.assert_called_once()
            matcher.matches.assert_called_once_with("test_event")

    def test_update_loop_processing(self, pulse_config, mock_shared_store):
        """Test the critical update_loop method processes updates correctly."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Add a mock update handler
            handler = Mock()
            matcher = Mock()
            matcher.matches.return_value = True
            manager.add_handler(matcher, handler)

            # Trigger an update
            manager.trigger_update(["nodes.test_node.values.test_key"])

            # Manually run the update loop once (synchronously)
            manager.update_loop()

            # Verify the handler was called
            handler.handle_update.assert_called_once()
            matcher.matches.assert_called_once_with("nodes.test_node.values.test_key")

            # Verify manager is set to idle after processing
            assert manager.idle.is_set()

    def test_event_loop_waits_for_idle(self, pulse_config, mock_shared_store):
        """Test that event_loop waits for idle state before processing."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Add a mock event handler
            handler = Mock()
            matcher = Mock()
            matcher.matches.return_value = True
            manager.add_event_handler(matcher, handler)

            # Trigger an event but don't set idle
            manager.trigger_event("test_event")
            manager.idle.clear()

            # Mock the idle wait to return False (timeout)
            with patch.object(manager.idle, "wait", return_value=False):
                # This should block and not process the event
                manager.event_loop()

                # Handler should not be called because idle.wait() returned False
                handler.handle_update.assert_not_called()

    def test_update_loop_multiple_batches(self, pulse_config, mock_shared_store):
        """Test update_loop processes multiple batches correctly."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Add a mock update handler
            handler = Mock()
            matcher = Mock()
            matcher.matches.return_value = True
            manager.add_handler(matcher, handler)

            # Trigger multiple updates
            manager.trigger_update(["path1"])
            manager.trigger_update(["path2"])

            # Simulate handler triggering more updates during processing
            def trigger_more_updates():
                if handler.handle_update.call_count == 1:
                    # First call triggers more updates
                    manager.trigger_update(["path3"])

            handler.handle_update.side_effect = trigger_more_updates

            # Run the update loop
            manager.update_loop()

            # With caching, controller will call handler twice across cycles (initial + after new path)
            assert handler.handle_update.call_count == 2
            # Verify all paths were processed
            actual_paths = [call[0][0] for call in matcher.matches.call_args_list]
            expected_paths = ["path1", "path2", "path3"]
            for path in expected_paths:
                assert path in actual_paths

    def test_event_loop_processes_all_queued_events(
        self, pulse_config, mock_shared_store
    ):
        """Test event_loop processes all events in the queue."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Add mock event handlers
            handler1 = Mock()
            handler2 = Mock()
            matcher1 = Mock()
            matcher2 = Mock()

            # First matcher matches event1, second matches event2
            matcher1.matches.side_effect = lambda x: x == "event1"
            matcher2.matches.side_effect = lambda x: x == "event2"

            manager.add_event_handler(matcher1, handler1)
            manager.add_event_handler(matcher2, handler2)

            # Trigger multiple events
            manager.trigger_event("event1")
            manager.trigger_event("event2")
            manager.trigger_event("event1")  # Duplicate should be deduped

            # Set idle and run event loop
            manager.idle.set()
            manager.event_loop()

            # Both handlers should be called appropriately
            handler1.handle_update.assert_called()
            handler2.handle_update.assert_called()

            # Check that events were processed (deduped to 2 unique events)
            total_matches = len(matcher1.matches.call_args_list) + len(
                matcher2.matches.call_args_list
            )
            assert total_matches == 4  # Each matcher checks both events

    def test_update_loop_idle_state_management(self, pulse_config, mock_shared_store):
        """Test update_loop manages idle state correctly."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Add handler that tracks when it's called
            handler = Mock()
            matcher = Mock()
            matcher.matches.return_value = True
            manager.add_handler(matcher, handler)

            # Initially should be idle
            manager.idle.set()
            initial_idle_state = manager.idle.is_set()

            # Trigger update (this clears idle in trigger_update)
            manager.trigger_update(["test_path"])
            after_trigger_idle_state = manager.idle.is_set()

            # Run update loop
            manager.update_loop()
            after_loop_idle_state = manager.idle.is_set()

            # Verify idle state transitions
            assert initial_idle_state is True
            assert after_trigger_idle_state is False  # Cleared by trigger_update
            assert after_loop_idle_state is True  # Set by update_loop completion

    def test_concurrent_event_and_update_processing(
        self, pulse_config, mock_shared_store
    ):
        """Test that events and updates can be processed independently."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Add handlers for both events and updates
            event_handler = Mock()
            update_handler = Mock()
            event_matcher = Mock()
            update_matcher = Mock()

            event_matcher.matches.return_value = True
            update_matcher.matches.return_value = True

            manager.add_event_handler(event_matcher, event_handler)
            manager.add_handler(update_matcher, update_handler)

            # Trigger both
            manager.trigger_event("test_event")
            manager.trigger_update(["test_path"])

            # Process events (requires idle state)
            manager.idle.set()
            manager.event_loop()

            # Process updates (manages its own idle state)
            manager.update_loop()

            # Both should have been processed
            event_handler.handle_update.assert_called_once()
            update_handler.handle_update.assert_called_once()
