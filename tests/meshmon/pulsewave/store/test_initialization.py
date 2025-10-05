# Test SharedStore initialization and basic properties


class TestSharedStoreInitialization:
    """Test cases for SharedStore initialization and basic properties."""

    def test_shared_store_initialization(self, shared_store, pulse_config):
        """Test SharedStore initialization."""
        assert shared_store.config == pulse_config
        assert hasattr(shared_store, "key_mapping")
        assert hasattr(shared_store, "store")

    def test_nodes_property(self, shared_store):
        """Test nodes property returns key mapping verifier keys."""
        nodes = shared_store.nodes
        assert isinstance(nodes, list)
        assert "test_node" in nodes
        assert "other_node" in nodes

    def test_initialization_creates_empty_store(self, shared_store):
        """Test that initialization creates a store instance."""
        assert hasattr(shared_store, "store")
        assert shared_store.store is not None

    def test_key_mapping_is_accessible(self, shared_store):
        """Test that key mapping is properly accessible."""
        assert hasattr(shared_store, "key_mapping")
        assert shared_store.key_mapping is not None

    def test_config_is_stored(self, shared_store, pulse_config):
        """Test that configuration is properly stored."""
        assert shared_store.config == pulse_config
        assert shared_store.config.update_rate_limit == 1
        assert shared_store.config.clock_pulse_interval == 5
