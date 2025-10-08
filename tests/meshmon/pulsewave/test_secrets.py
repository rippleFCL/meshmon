"""
Tests for the pulsewave secrets module.

These tests verify that the SecretContainer class works correctly for
managing secrets in a thread-safe manner.
"""

import threading

from src.meshmon.pulsewave.secrets import SecretContainer


class TestSecretContainer:
    """Test cases for SecretContainer."""

    def test_init(self):
        """Test SecretContainer initialization."""
        container = SecretContainer()
        assert isinstance(container.secrets, dict)
        assert len(container.secrets) == 0
        assert isinstance(container.lock, threading.Lock)

    def test_add_secret(self):
        """Test adding a secret."""
        container = SecretContainer()
        container.add_secret("key1", "value1")

        assert "key1" in container.secrets
        assert container.secrets["key1"] == "value1"

    def test_get_secret_existing(self):
        """Test getting an existing secret."""
        container = SecretContainer()
        container.add_secret("key1", "value1")

        result = container.get_secret("key1")
        assert result == "value1"

    def test_get_secret_nonexistent(self):
        """Test getting a non-existent secret returns None."""
        container = SecretContainer()
        result = container.get_secret("nonexistent")
        assert result is None

    def test_validate_secret_correct(self):
        """Test validating a secret with correct value."""
        container = SecretContainer()
        container.add_secret("key1", "value1")

        assert container.validate_secret("key1", "value1") is True

    def test_validate_secret_incorrect(self):
        """Test validating a secret with incorrect value."""
        container = SecretContainer()
        container.add_secret("key1", "value1")

        assert container.validate_secret("key1", "wrong_value") is False

    def test_validate_secret_nonexistent(self):
        """Test validating a non-existent secret returns False."""
        container = SecretContainer()
        assert container.validate_secret("nonexistent", "value") is False

    def test_contains_existing(self):
        """Test __contains__ for existing secret."""
        container = SecretContainer()
        container.add_secret("key1", "value1")

        assert "key1" in container

    def test_contains_nonexistent(self):
        """Test __contains__ for non-existent secret."""
        container = SecretContainer()
        assert "key1" not in container

    def test_overwrite_secret(self):
        """Test overwriting an existing secret."""
        container = SecretContainer()
        container.add_secret("key1", "value1")
        container.add_secret("key1", "value2")

        assert container.get_secret("key1") == "value2"

    def test_multiple_secrets(self):
        """Test managing multiple secrets."""
        container = SecretContainer()
        container.add_secret("key1", "value1")
        container.add_secret("key2", "value2")
        container.add_secret("key3", "value3")

        assert len(container.secrets) == 3
        assert container.get_secret("key1") == "value1"
        assert container.get_secret("key2") == "value2"
        assert container.get_secret("key3") == "value3"

    def test_thread_safety(self):
        """Test that operations are thread-safe."""
        container = SecretContainer()
        errors = []

        def add_secrets():
            try:
                for i in range(100):
                    container.add_secret(f"key{i}", f"value{i}")
            except Exception as e:
                errors.append(e)

        def read_secrets():
            try:
                for i in range(100):
                    container.get_secret(f"key{i}")
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for _ in range(5):
            t1 = threading.Thread(target=add_secrets)
            t2 = threading.Thread(target=read_secrets)
            threads.extend([t1, t2])

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Check no errors occurred
        assert len(errors) == 0
