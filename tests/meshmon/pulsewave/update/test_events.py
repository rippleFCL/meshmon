"""
Tests for pulsewave update events module.

Tests LocalStores, LocalHandler, and RateLimitedHandler classes.
"""

from unittest.mock import Mock, patch

from src.meshmon.pulsewave.update.events import (
    LocalHandler,
    LocalStores,
    RateLimitedHandler,
)


class TestLocalStores:
    """Test cases for LocalStores class."""

    def test_init(self):
        """Test LocalStores initialization."""
        stores = LocalStores()
        assert stores.stores == {}
        assert stores.logger is not None

    def test_add_store(self, mock_shared_store, mock_signer):
        """Test adding a store to LocalStores."""
        stores = LocalStores()
        mock_shared_store.key_mapping.signer = mock_signer

        stores.add_store(mock_shared_store)

        assert mock_signer.node_id in stores.stores
        assert stores.stores[mock_signer.node_id] == mock_shared_store

    def test_iter(self, mock_shared_store, mock_signer):
        """Test iterating over stores."""
        stores = LocalStores()
        mock_shared_store.key_mapping.signer = mock_signer
        stores.add_store(mock_shared_store)

        items = list(stores)

        assert len(items) == 1
        assert items[0] == (mock_signer.node_id, mock_shared_store)


class TestLocalHandler:
    """Test cases for LocalHandler class."""

    def test_init(self):
        """Test LocalHandler initialization."""
        stores = LocalStores()
        handler = LocalHandler(stores)

        assert handler.stores == stores
        assert handler.logger is not None

    def test_bind(self, mock_shared_store):
        """Test binding handler to store."""
        stores = LocalStores()
        handler = LocalHandler(stores)
        update_manager = Mock()

        handler.bind(mock_shared_store, update_manager)

        assert handler.store == mock_shared_store

    def test_handle_update(self, mock_signer, another_signer):
        """Test handling update between local stores."""
        stores = LocalStores()

        # Create two mock stores
        store1 = Mock()
        store1.key_mapping.signer = mock_signer
        store1.dump.return_value = Mock()  # StoreData

        store2 = Mock()
        store2.key_mapping.signer = another_signer

        # Add stores
        stores.add_store(store1)
        stores.add_store(store2)

        # Create handler and bind to first store
        handler = LocalHandler(stores)
        handler.bind(store1, Mock())

        # Handle update
        handler.handle_update()

        # Verify data was sent to other store
        store1.dump.assert_called_once()
        store2.update_from_dump.assert_called_once()

    def test_handle_update_same_node(self, mock_signer):
        """Test that handler doesn't send to itself."""
        stores = LocalStores()

        store1 = Mock()
        store1.key_mapping.signer = mock_signer

        stores.add_store(store1)

        handler = LocalHandler(stores)
        handler.bind(store1, Mock())

        handler.handle_update()

        # Should not call update_from_dump on itself
        store1.update_from_dump.assert_not_called()


class TestRateLimitedHandler:
    """Test cases for RateLimitedHandler class."""

    def test_init(self):
        """Test RateLimitedHandler initialization."""
        inner_handler = Mock()
        handler = RateLimitedHandler(inner_handler, 0.1)

        assert handler.handler == inner_handler
        assert handler.min_interval == 0.1
        assert handler.trigger is not None
        assert handler.logger is not None

    def test_bind(self, mock_shared_store):
        """Test binding handler starts thread."""
        inner_handler = Mock()
        handler = RateLimitedHandler(inner_handler, 0.01)
        update_manager = Mock()

        # Mock threading to avoid actual threads in tests
        with patch("src.meshmon.pulsewave.update.events.Thread") as mock_thread:
            handler.bind(mock_shared_store, update_manager)

            # Verify inner handler was bound
            inner_handler.bind.assert_called_once_with(
                mock_shared_store, update_manager
            )

            # Verify thread was created and started
            mock_thread.assert_called_once()
            mock_thread.return_value.start.assert_called_once()

    def test_handle_update_sets_trigger(self):
        """Test that handle_update sets the trigger event."""
        inner_handler = Mock()
        handler = RateLimitedHandler(inner_handler, 0.1)

        handler.handle_update()

        assert handler.trigger.is_set()

    def test_handler_loop_rate_limiting(self):
        """Test that handler loop respects rate limiting."""
        inner_handler = Mock()
        handler = RateLimitedHandler(inner_handler, 0.01)

        # Mock time.sleep to avoid actual delays
        with patch("src.meshmon.pulsewave.update.events.time.sleep") as mock_sleep:
            # Set trigger and run one iteration
            handler.trigger.set()

            # Mock the loop to exit after one iteration
            with patch.object(handler.trigger, "wait", side_effect=[True, False]):
                try:
                    handler._handler_loop()
                except StopIteration:
                    # Expected when mock runs out of side_effects
                    pass

            # Verify sleep was called with correct interval
            mock_sleep.assert_called_with(0.01)
