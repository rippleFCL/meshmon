"""
Tests for pulsewave update core module.

Tests IncrementalUpdater, DedupeQueue, path matchers, UpdateController, and UpdateManager.
"""

from unittest.mock import Mock, patch

from src.meshmon.pulsewave.data import StoreData
from src.meshmon.pulsewave.update.update import (
    DedupeQueue,
    ExactPathMatcher,
    IncrementalUpdater,
    RegexPathMatcher,
    UpdateController,
    UpdateManager,
)


class TestIncrementalUpdater:
    """Test cases for IncrementalUpdater class."""

    def test_init(self):
        """Test IncrementalUpdater initialization."""
        updater = IncrementalUpdater()
        assert isinstance(updater.end_data, StoreData)
        assert updater.end_data.nodes == {}

    def test_diff_excludes_node(self, sample_store_data, key_mapping):
        """Test that diff excludes specified node."""
        updater = IncrementalUpdater()
        updater.update(sample_store_data, key_mapping)

        diff = updater.diff(sample_store_data, key_mapping.signer.node_id)

        assert key_mapping.signer.node_id not in diff.nodes

    def test_diff_returns_copy(self, sample_store_data, key_mapping):
        """Test that diff returns a copy of the input data."""
        updater = IncrementalUpdater()

        diff = updater.diff(sample_store_data, "nonexistent_node")

        # Should return a model copy
        assert diff is not sample_store_data
        assert diff.nodes == sample_store_data.nodes

    def test_update(self, sample_store_data, key_mapping):
        """Test updating with new data."""
        updater = IncrementalUpdater()

        updater.update(sample_store_data, key_mapping)

        assert key_mapping.signer.node_id in updater.end_data.nodes

    def test_clear(self, sample_store_data, key_mapping):
        """Test clearing updater state."""
        updater = IncrementalUpdater()
        updater.update(sample_store_data, key_mapping)

        updater.clear()

        assert updater.end_data.nodes == {}

    def test_multiple_updates(self, sample_store_data, key_mapping):
        """Test multiple updates accumulate data."""
        updater = IncrementalUpdater()

        # First update
        updater.update(sample_store_data, key_mapping)
        first_count = len(updater.end_data.nodes)

        # Second update with same data
        updater.update(sample_store_data, key_mapping)

        # Should still have the same data
        assert len(updater.end_data.nodes) == first_count


class TestDedupeQueue:
    """Test cases for DedupeQueue class."""

    def test_init(self):
        """Test DedupeQueue initialization."""
        queue = DedupeQueue()
        assert queue.queue == set()
        assert not queue.has_items.is_set()
        assert queue.empty

    def test_add_items(self):
        """Test adding items to queue."""
        queue = DedupeQueue()

        queue.add(["item1", "item2", "item1"])  # Duplicate item1

        assert queue.has_items.is_set()
        assert not queue.empty
        assert len(queue.queue) == 2  # Deduped

    def test_add_multiple_calls(self):
        """Test multiple add calls accumulate items."""
        queue = DedupeQueue()

        queue.add(["item1", "item2"])
        queue.add(["item2", "item3"])  # item2 is duplicate

        assert len(queue.queue) == 3  # item1, item2, item3

    def test_pop_all(self):
        """Test popping all items from queue."""
        queue = DedupeQueue()
        queue.add(["item1", "item2"])

        items = queue.pop_all()

        assert "item1" in items
        assert "item2" in items
        assert len(items) == 2
        assert queue.empty
        assert not queue.has_items.is_set()

    def test_pop_all_empty_queue(self):
        """Test popping from empty queue."""
        queue = DedupeQueue()

        items = queue.pop_all()

        assert items == []
        assert queue.empty

    def test_wait_for_items(self):
        """Test waiting for items."""
        queue = DedupeQueue()

        # Should return False immediately when empty
        assert not queue.wait_for_items(timeout=0.01)

        # Add items and should return True
        queue.add(["item1"])
        assert queue.wait_for_items(timeout=0.01)

    def test_wait_for_items_after_pop(self):
        """Test waiting after items are popped."""
        queue = DedupeQueue()
        queue.add(["item1"])
        queue.pop_all()

        # Should return False after items are popped
        assert not queue.wait_for_items(timeout=0.01)

    def test_empty_property(self):
        """Test empty property reflects queue state."""
        queue = DedupeQueue()

        assert queue.empty

        queue.add(["item1"])
        assert not queue.empty

        queue.pop_all()
        assert queue.empty


class TestPathMatchers:
    """Test cases for path matcher classes."""

    def test_regex_path_matcher_single_pattern(self):
        """Test RegexPathMatcher with single pattern."""
        matcher = RegexPathMatcher([r"nodes\.\w+\.values\.\w+"])

        assert matcher.matches("nodes.node1.values.key1")
        assert matcher.matches("nodes.node2.values.key2")
        assert not matcher.matches("nodes.node1.contexts.context1")
        assert not matcher.matches("invalid.path")

    def test_regex_path_matcher_multiple_patterns(self):
        """Test RegexPathMatcher with multiple patterns."""
        matcher = RegexPathMatcher(
            [r"nodes\.\w+\.values\.\w+", r"nodes\.\w+\.contexts\.\w+"]
        )

        assert matcher.matches("nodes.node1.values.key1")
        assert matcher.matches("nodes.node2.contexts.context1")
        assert not matcher.matches("nodes.node1.invalid.key1")
        assert not matcher.matches("invalid.path")

    def test_regex_path_matcher_complex_patterns(self):
        """Test RegexPathMatcher with more complex patterns."""
        # Pattern from actual clock table handler
        matcher = RegexPathMatcher(
            [r"^nodes\.([\w-]+)\.consistency\.pulse_table\.test_node$"]
        )

        assert matcher.matches("nodes.node-1.consistency.pulse_table.test_node")
        assert matcher.matches("nodes.node_2.consistency.pulse_table.test_node")
        assert not matcher.matches("nodes.node1.consistency.pulse_table.other_node")

    def test_exact_path_matcher(self):
        """Test ExactPathMatcher functionality."""
        matcher = ExactPathMatcher("nodes.node1.values.key1")

        assert matcher.matches("nodes.node1.values.key1")
        assert not matcher.matches("nodes.node1.values.key2")
        assert not matcher.matches("different.path")
        assert not matcher.matches("nodes.node1.values.key11")  # Partial match

    def test_exact_path_matcher_empty_path(self):
        """Test ExactPathMatcher with empty path."""
        matcher = ExactPathMatcher("")

        assert matcher.matches("")
        assert not matcher.matches("any.path")


class TestUpdateController:
    """Test cases for UpdateController class."""

    def test_init(self):
        """Test UpdateController initialization."""
        controller = UpdateController()
        assert controller.handlers == []
        assert controller.handler_cache == {}

    def test_add_handler(self):
        """Test adding handlers to controller."""
        controller = UpdateController()
        matcher = Mock()
        handler = Mock()

        controller.add(matcher, handler)

        assert len(controller.handlers) == 1
        assert controller.handlers[0] == (matcher, handler)

    def test_add_multiple_handlers(self):
        """Test adding multiple handlers."""
        controller = UpdateController()
        matcher1, handler1 = Mock(), Mock()
        matcher2, handler2 = Mock(), Mock()

        controller.add(matcher1, handler1)
        controller.add(matcher2, handler2)

        assert len(controller.handlers) == 2
        assert (matcher1, handler1) in controller.handlers
        assert (matcher2, handler2) in controller.handlers

    def test_add_clears_cache(self):
        """Test that adding handler clears cache."""
        controller = UpdateController()
        controller.handler_cache["test"] = [Mock()]

        controller.add(Mock(), Mock())

        assert controller.handler_cache == {}

    def test_handle_with_cache(self, mock_shared_store):
        """Test handling events with cache."""
        controller = UpdateController()
        handler = Mock()

        # Pre-populate cache
        controller.handler_cache["test_event"] = [handler]

        controller.handle("test_event", mock_shared_store, Mock())

        handler.handle_update.assert_called_once()

    def test_handle_with_matching(self, mock_shared_store):
        """Test handling events with pattern matching."""
        controller = UpdateController()
        matcher = Mock()
        matcher.matches.return_value = True
        handler = Mock()

        controller.add(matcher, handler)

        controller.handle("test_event", mock_shared_store, Mock())

        matcher.matches.assert_called_once_with("test_event")
        handler.handle_update.assert_called_once()

    def test_handle_no_matching(self, mock_shared_store):
        """Test handling events with no matching handlers."""
        controller = UpdateController()
        matcher = Mock()
        matcher.matches.return_value = False
        handler = Mock()

        controller.add(matcher, handler)

        controller.handle("test_event", mock_shared_store, Mock())

        matcher.matches.assert_called_once_with("test_event")
        handler.handle_update.assert_not_called()

    def test_handle_cache_update(self, mock_shared_store):
        """Test that cache is updated after matching."""
        controller = UpdateController()
        matcher = Mock()
        matcher.matches.return_value = True
        handler = Mock()

        controller.add(matcher, handler)

        controller.handle("test_event", mock_shared_store, Mock())

        assert "test_event" in controller.handler_cache
        assert controller.handler_cache["test_event"] == [handler]

    def test_handle_multiple_matching_handlers(self, mock_shared_store):
        """Test handling with multiple matching handlers."""
        controller = UpdateController()

        matcher1, handler1 = Mock(), Mock()
        matcher2, handler2 = Mock(), Mock()
        matcher1.matches.return_value = True
        matcher2.matches.return_value = True

        controller.add(matcher1, handler1)
        controller.add(matcher2, handler2)

        controller.handle("test_event", mock_shared_store, Mock())

        handler1.handle_update.assert_called_once()
        handler2.handle_update.assert_called_once()


class TestUpdateManager:
    """Test cases for UpdateManager class."""

    def test_init(self, pulse_config, mock_shared_store):
        """Test UpdateManager initialization."""
        # Mock threading to avoid actual threads
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            assert manager.db_config == pulse_config
            assert manager.store == mock_shared_store
            assert isinstance(manager.event_queue, DedupeQueue)
            assert isinstance(manager.update_queue, DedupeQueue)
            assert isinstance(manager.event_controller, UpdateController)
            assert isinstance(manager.update_controller, UpdateController)

    def test_add_handler(self, pulse_config, mock_shared_store):
        """Test adding update handlers."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            matcher = Mock()
            handler = Mock()

            manager.add_handler(matcher, handler)

            handler.bind.assert_called_once_with(mock_shared_store, manager)
            assert len(manager.update_controller.handlers) == 1

    def test_add_event_handler(self, pulse_config, mock_shared_store):
        """Test adding event handlers."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            matcher = Mock()
            handler = Mock()

            manager.add_event_handler(matcher, handler)

            handler.bind.assert_called_once_with(mock_shared_store, manager)
            assert len(manager.event_controller.handlers) == 1

    def test_trigger_update(self, pulse_config, mock_shared_store):
        """Test triggering updates."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            manager.trigger_update(["path1", "path2"])

            assert not manager.idle.is_set()
            # Items should be in update queue
            items = manager.update_queue.pop_all()
            assert "path1" in items
            assert "path2" in items

    def test_trigger_event(self, pulse_config, mock_shared_store):
        """Test triggering events."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            manager.trigger_event("test_event")

            # Event should be in queue
            events = manager.event_queue.pop_all()
            assert "test_event" in events

    def test_wait_until_idle(self, pulse_config, mock_shared_store):
        """Test waiting until manager is idle."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Manager starts idle
            manager.idle.set()

            # Should return True when already idle
            assert manager.wait_until_idle(timeout=0.01)

            # Clear idle state
            manager.idle.clear()

            # Should return False when not idle and timeout
            assert not manager.wait_until_idle(timeout=0.01)

    def test_multiple_triggers(self, pulse_config, mock_shared_store):
        """Test multiple triggers accumulate in queues."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Multiple update triggers
            manager.trigger_update(["path1"])
            manager.trigger_update(["path2"])

            # Multiple event triggers
            manager.trigger_event("event1")
            manager.trigger_event("event2")

            # All should be in their respective queues
            updates = manager.update_queue.pop_all()
            events = manager.event_queue.pop_all()

            assert "path1" in updates
            assert "path2" in updates
            assert "event1" in events
            assert "event2" in events

    def test_event_loop_execution(self, pulse_config, mock_shared_store):
        """Test event_loop method executes correctly."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Add handler
            handler = Mock()
            matcher = Mock()
            matcher.matches.return_value = True
            manager.add_event_handler(matcher, handler)

            # Add event to queue
            manager.trigger_event("test_event")
            manager.idle.set()  # Allow event processing

            # Execute event loop once
            manager.event_loop()

            # Verify handler was called
            handler.handle_update.assert_called_once()

    def test_update_loop_execution(self, pulse_config, mock_shared_store):
        """Test update_loop method executes correctly."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Add handler
            handler = Mock()
            matcher = Mock()
            matcher.matches.return_value = True
            manager.add_handler(matcher, handler)

            # Add update to queue
            manager.trigger_update(["test_path"])

            # Execute update loop once
            manager.update_loop()

            # Verify handler was called and idle state set
            handler.handle_update.assert_called_once()
            assert manager.idle.is_set()

    def test_looped_executor(self, pulse_config, mock_shared_store):
        """Test looped_executor runs function in infinite loop."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            # Mock function to track calls
            mock_func = Mock()
            # Make it raise exception after 2 calls to exit loop
            mock_func.side_effect = [None, None, KeyboardInterrupt()]

            # Test looped executor
            try:
                manager.looped_executor(mock_func)
            except KeyboardInterrupt:
                pass

            # Should be called multiple times
            assert mock_func.call_count == 3

    def test_update_loop_continuous_processing(self, pulse_config, mock_shared_store):
        """Test update_loop processes items until queue is empty."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            handler = Mock()
            matcher = Mock()
            matcher.matches.return_value = True

            # Handler will add more items on first call
            def add_more_items():
                if handler.handle_update.call_count == 1:
                    manager.trigger_update(["additional_path"])

            handler.handle_update.side_effect = add_more_items
            manager.add_handler(matcher, handler)

            # Initial trigger
            manager.trigger_update(["initial_path"])

            # Run update loop
            manager.update_loop()

            # Should process both initial and additional items
            assert handler.handle_update.call_count == 2
            assert manager.idle.is_set()

    def test_event_loop_waits_for_idle_state(self, pulse_config, mock_shared_store):
        """Test event_loop respects idle state."""
        with patch("src.meshmon.pulsewave.update.update.Thread"):
            manager = UpdateManager(pulse_config, mock_shared_store)

            handler = Mock()
            matcher = Mock()
            matcher.matches.return_value = True
            manager.add_event_handler(matcher, handler)

            # Add event but don't set idle
            manager.trigger_event("test_event")
            manager.idle.clear()

            # Mock idle.wait to return immediately (timeout)
            with patch.object(manager.idle, "wait", return_value=False):
                manager.event_loop()

                # Handler should not be called since idle.wait() failed
                handler.handle_update.assert_not_called()
