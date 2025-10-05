"""Test SharedStore interface and API surface."""


class TestSharedStoreInterface:
    """Test cases for SharedStore method interface and API."""

    def test_dump_method_exists(self, shared_store):
        """Test that dump method exists and is callable."""
        assert hasattr(shared_store, "dump")
        assert callable(shared_store.dump)

    def test_stop_method_exists(self, shared_store):
        """Test that stop method exists and is callable."""
        assert hasattr(shared_store, "stop")
        assert callable(shared_store.stop)

    def test_overloaded_methods_exist(self, shared_store):
        """Test that overloaded methods exist."""
        methods = ["get_value", "set_value", "get_context", "get_consistency"]
        for method_name in methods:
            assert hasattr(shared_store, method_name)
            assert callable(getattr(shared_store, method_name))

    def test_update_from_dump_method_exists(self, shared_store):
        """Test that update_from_dump method exists and is callable."""
        assert hasattr(shared_store, "update_from_dump")
        assert callable(shared_store.update_from_dump)

    def test_set_value_method_exists(self, shared_store):
        """Test that set_value method exists and is callable."""
        assert hasattr(shared_store, "set_value")
        assert callable(shared_store.set_value)

    def test_iterator_methods_exist(self, shared_store):
        """Test that iterator methods exist."""
        iterator_methods = ["values", "contexts"]
        for method_name in iterator_methods:
            assert hasattr(shared_store, method_name)
            assert callable(getattr(shared_store, method_name))

    def test_get_methods_accept_parameters(self, shared_store):
        """Test that get methods accept the expected parameters."""
        from pydantic import BaseModel

        class TestModel(BaseModel):
            test_field: str = "test"

        # These should not raise exceptions when called with proper arguments
        try:
            shared_store.get_value(TestModel, "test_key")
        except Exception as e:
            # Should not raise TypeError about arguments, only about implementation details
            assert "argument" not in str(e).lower()

        try:
            shared_store.get_context("test_context", TestModel)
        except Exception as e:
            assert "argument" not in str(e).lower()

    def test_values_contexts_accept_node_parameter(self, shared_store):
        """Test that values and contexts methods accept optional node parameter."""
        # Should not raise TypeError about arguments
        list(shared_store.values())
        list(shared_store.values("test_node"))

        list(shared_store.contexts())
        list(shared_store.contexts("test_node"))

    def test_private_method_access(self, shared_store):
        """Test that private methods exist and are accessible."""
        private_methods = ["_get_ctx"]
        for method_name in private_methods:
            assert hasattr(shared_store, method_name)
            assert callable(getattr(shared_store, method_name))
