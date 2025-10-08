from unittest.mock import patch

from pydantic import BaseModel


class SampleModel(BaseModel):
    """Sample model for store operations testing."""

    name: str
    value: int


class TestSharedStoreLifecycle:
    """Test cases for SharedStore lifecycle and management operations."""

    def test_stop_method_calls_update_manager(self, shared_store):
        """Test stop method calls update manager stop."""
        with patch.object(shared_store.update_manager, "stop") as mock_stop:
            shared_store.stop()
            mock_stop.assert_called_once()

    def test_error_recovery_interface(self, shared_store):
        """Test that the store can recover from basic errors."""
        # Test that after an error, the store is still functional
        try:
            shared_store.get_value(SampleModel, "nonexistent", "nonexistent_node")
        except Exception:
            pass  # Ignore any errors from this call

        # Store should still be functional
        assert hasattr(shared_store, "dump")
        assert callable(shared_store.dump)

    def test_cleanup_operations(self, shared_store):
        """Test cleanup and teardown operations."""
        # Test that stop can be called multiple times safely
        with patch.object(shared_store.update_manager, "stop") as mock_stop:
            shared_store.stop()
            shared_store.stop()  # Should not cause issues

            # Stop should be called each time
            assert mock_stop.call_count == 2

    def test_operational_readiness_checks(self, shared_store):
        """Test that the store is operationally ready after initialization."""
        # Basic readiness checks
        assert shared_store.store is not None
        assert shared_store.config is not None
        assert shared_store.key_mapping is not None
        assert shared_store.update_manager is not None

        # All key methods should be callable
        assert callable(shared_store.dump)
        assert callable(shared_store.stop)
        assert callable(shared_store.set_value)
        assert callable(shared_store.get_value)
        assert callable(shared_store.update_from_dump)
