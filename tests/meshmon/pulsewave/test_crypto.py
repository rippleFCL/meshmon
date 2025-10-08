"""
Tests for the pulsewave cryptography module.

These tests verify that the cryptographic classes work correctly,
including Verifier, Signer, and KeyMapping functionality.
"""

import base64
import os
import tempfile
from unittest.mock import Mock, mock_open, patch

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from src.meshmon.pulsewave.crypto import KeyMapping, Signer, Verifier


class TestVerifier:
    """Test cases for Verifier class."""

    @pytest.fixture
    def ed25519_key_pair(self):
        """Generate an Ed25519 key pair for testing."""
        private_key = Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        return private_key, public_key

    @pytest.fixture
    def verifier(self, ed25519_key_pair):
        """Create a Verifier instance for testing."""
        _, public_key = ed25519_key_pair
        return Verifier("test_peer", public_key)

    def test_verifier_creation(self, ed25519_key_pair):
        """Test creating a Verifier instance."""
        _, public_key = ed25519_key_pair
        verifier = Verifier("test_node", public_key)

        assert verifier.node_id == "test_node"
        assert verifier.public_key == public_key

    def test_verify_valid_signature(self, ed25519_key_pair):
        """Test verifying a valid signature."""
        private_key, public_key = ed25519_key_pair
        verifier = Verifier("test_peer", public_key)

        message = b"Hello, World!"
        signature = private_key.sign(message)

        assert verifier.verify(message, signature) is True

    def test_verify_invalid_signature(self, verifier):
        """Test verifying an invalid signature."""
        message = b"Hello, World!"
        invalid_signature = b"invalid_signature_bytes"

        assert verifier.verify(message, invalid_signature) is False

    def test_verify_wrong_message(self, ed25519_key_pair):
        """Test verifying signature with wrong message."""
        private_key, public_key = ed25519_key_pair
        verifier = Verifier("test_peer", public_key)

        original_message = b"Original message"
        different_message = b"Different message"
        signature = private_key.sign(original_message)

        assert verifier.verify(different_message, signature) is False

    def test_decode_message_valid(self, ed25519_key_pair):
        """Test decoding a valid encoded message."""
        private_key, public_key = ed25519_key_pair
        verifier = Verifier("test_peer", public_key)

        content = "Hello, World!"
        content_bytes = content.encode("utf-8")
        signature = private_key.sign(content_bytes)

        b64_sig = base64.b64encode(signature).decode("utf-8")
        b64_content = base64.b64encode(content_bytes).decode("utf-8")
        encoded_message = f"{b64_sig}.{b64_content}"

        decoded = verifier.decode_message(encoded_message)
        assert decoded == content

    def test_decode_message_invalid_signature(self, verifier):
        """Test decoding message with invalid signature."""
        content = "Hello, World!"
        invalid_sig = base64.b64encode(b"invalid_signature").decode("utf-8")
        b64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        encoded_message = f"{invalid_sig}.{b64_content}"

        decoded = verifier.decode_message(encoded_message)
        assert decoded is None

    def test_by_id_existing_key(self):
        """Test loading verifier by ID with existing key file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test key file
            private_key = Ed25519PrivateKey.generate()
            public_key = private_key.public_key()

            key_path = os.path.join(temp_dir, "test_peer.pub")
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )

            with open(key_path, "wb") as f:
                f.write(public_bytes)

            # Load verifier
            verifier = Verifier.by_id("test_peer", temp_dir)

            assert verifier.node_id == "test_peer"
            assert isinstance(verifier.public_key, Ed25519PublicKey)

    def test_by_id_missing_key_file(self):
        """Test loading verifier by ID when key file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(FileNotFoundError):
                Verifier.by_id("nonexistent_peer", temp_dir)

    def test_by_id_invalid_key_type(self):
        """Test loading verifier with invalid key type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file with invalid key content
            key_path = os.path.join(temp_dir, "test_peer.pub")
            with open(key_path, "w") as f:
                f.write("invalid key content")

            with pytest.raises(ValueError):
                Verifier.by_id("test_peer", temp_dir)

    def test_save_new_key(self, verifier):
        """Test saving verifier public key to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            verifier.save("test_peer", temp_dir)

            key_path = os.path.join(temp_dir, "test_peer.pub")
            assert os.path.exists(key_path)

            # Verify we can load the saved key
            loaded_verifier = Verifier.by_id("test_peer", temp_dir)
            assert loaded_verifier.node_id == "test_peer"

    def test_save_existing_key(self, verifier):
        """Test that saving doesn't overwrite existing key file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            key_path = os.path.join(temp_dir, "test_peer.pub")

            # Create existing file
            with open(key_path, "w") as f:
                f.write("existing content")

            verifier.save("test_peer", temp_dir)

            # File should still contain original content
            with open(key_path, "r") as f:
                content = f.read()
            assert content == "existing content"


class TestSigner:
    """Test cases for Signer class."""

    @pytest.fixture
    def signer(self):
        """Create a Signer instance for testing."""
        private_key = Ed25519PrivateKey.generate()
        return Signer("test_signer", private_key)

    def test_signer_creation(self):
        """Test creating a Signer instance."""
        private_key = Ed25519PrivateKey.generate()
        signer = Signer("test_node", private_key)

        assert signer.node_id == "test_node"
        assert signer.private_key == private_key
        assert isinstance(signer.public_key, Ed25519PublicKey)

    def test_sign_message(self, signer):
        """Test signing a message."""
        message = b"Test message"
        signature = signer.sign(message)

        assert isinstance(signature, bytes)
        assert len(signature) > 0

        # Verify signature is valid
        signer.public_key.verify(signature, message)  # Should not raise

    def test_encode_message(self, signer):
        """Test encoding a message with signature."""
        content = "Hello, World!"
        encoded = signer.encode_message(content)

        # Should be in format "signature.content" (both base64)
        parts = encoded.split(".")
        assert len(parts) == 2

        # Both parts should be valid base64
        signature_bytes = base64.b64decode(parts[0])
        content_bytes = base64.b64decode(parts[1])

        assert content_bytes.decode("utf-8") == content
        assert isinstance(signature_bytes, bytes)

    def test_get_verifier(self, signer):
        """Test getting verifier from signer."""
        verifier = signer.get_verifier()

        assert isinstance(verifier, Verifier)
        assert verifier.node_id == signer.node_id
        assert verifier.public_key == signer.public_key

    def test_sign_and_verify_roundtrip(self, signer):
        """Test signing and verifying in roundtrip."""
        message = b"Test message for roundtrip"
        signature = signer.sign(message)
        verifier = signer.get_verifier()

        assert verifier.verify(message, signature) is True

    def test_encode_decode_message_roundtrip(self, signer):
        """Test encoding and decoding message in roundtrip."""
        original_content = "This is a test message with special chars: áéíóú 123!@#"
        encoded = signer.encode_message(original_content)
        verifier = signer.get_verifier()
        decoded = verifier.decode_message(encoded)

        assert decoded == original_content

    def test_by_id_existing_key(self):
        """Test loading signer by ID with existing key file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test key file
            private_key = Ed25519PrivateKey.generate()
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )

            key_path = os.path.join(temp_dir, "test_signer.key")
            with open(key_path, "wb") as f:
                f.write(private_bytes)

            # Load signer
            signer = Signer.by_id("test_signer", temp_dir)

            assert signer.node_id == "test_signer"
            assert isinstance(signer.private_key, Ed25519PrivateKey)

    def test_by_id_generate_new_key(self):
        """Test loading signer by ID generates new key when none exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            signer = Signer.by_id("new_signer", temp_dir)

            assert signer.node_id == "new_signer"
            assert isinstance(signer.private_key, Ed25519PrivateKey)

            # Key file should be created
            key_path = os.path.join(temp_dir, "new_signer.key")
            assert os.path.exists(key_path)

    def test_by_id_invalid_key_type(self):
        """Test loading signer with invalid key type."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a file with invalid key content
            key_path = os.path.join(temp_dir, "test_signer.key")
            with open(key_path, "w") as f:
                f.write("invalid key content")

            with pytest.raises(ValueError):
                Signer.by_id("test_signer", temp_dir)

    def test_by_id_default_key_dir(self):
        """Test that by_id uses default key directory."""
        with (
            patch("os.path.exists") as mock_exists,
            patch("builtins.open", mock_open()),
            patch("os.makedirs") as mock_makedirs,
            patch.object(Ed25519PrivateKey, "generate") as mock_generate,
        ):
            mock_exists.return_value = False  # No existing key
            mock_private_key = Mock(spec=Ed25519PrivateKey)
            mock_private_key.private_bytes.return_value = b"mock_key_bytes"
            mock_generate.return_value = mock_private_key

            Signer.by_id("test_peer")

            # Should use default directory
            mock_makedirs.assert_called_with("config/.private_keys", exist_ok=True)

    def test_empty_message_encoding(self, signer):
        """Test encoding empty message."""
        encoded = signer.encode_message("")
        verifier = signer.get_verifier()
        decoded = verifier.decode_message(encoded)

        assert decoded == ""

    def test_unicode_message_encoding(self, signer):
        """Test encoding unicode message."""
        unicode_content = "Hello 世界! 🌍 áéíóú"
        encoded = signer.encode_message(unicode_content)
        verifier = signer.get_verifier()
        decoded = verifier.decode_message(encoded)

        assert decoded == unicode_content


class TestKeyMapping:
    """Test cases for KeyMapping class."""

    @pytest.fixture
    def signer(self):
        """Create a signer for testing."""
        private_key = Ed25519PrivateKey.generate()
        return Signer("main_signer", private_key)

    @pytest.fixture
    def verifiers(self):
        """Create verifiers for testing."""
        verifier1 = Verifier("peer1", Ed25519PrivateKey.generate().public_key())
        verifier2 = Verifier("peer2", Ed25519PrivateKey.generate().public_key())
        return {"peer1": verifier1, "peer2": verifier2}

    @pytest.fixture
    def key_mapping(self, signer, verifiers):
        """Create a KeyMapping instance for testing."""
        return KeyMapping(signer, verifiers)

    def test_key_mapping_creation(self, signer, verifiers):
        """Test creating a KeyMapping instance."""
        key_mapping = KeyMapping(signer, verifiers)

        assert key_mapping.signer == signer
        assert key_mapping.verifiers == verifiers

    def test_contains_existing_peer(self, key_mapping):
        """Test checking if peer exists in mapping."""
        assert "peer1" in key_mapping
        assert "peer2" in key_mapping

    def test_contains_nonexistent_peer(self, key_mapping):
        """Test checking if nonexistent peer exists in mapping."""
        assert "nonexistent_peer" not in key_mapping

    def test_get_verifier_existing_peer(self, key_mapping, verifiers):
        """Test getting verifier for existing peer."""
        verifier = key_mapping.get_verifier("peer1")

        assert verifier == verifiers["peer1"]

    def test_get_verifier_nonexistent_peer(self, key_mapping):
        """Test getting verifier for nonexistent peer returns None."""
        verifier = key_mapping.get_verifier("nonexistent_peer")

        assert verifier is None

    def test_empty_verifiers_dict(self, signer):
        """Test KeyMapping with empty verifiers dict."""
        key_mapping = KeyMapping(signer, {})

        assert key_mapping.signer == signer
        assert key_mapping.verifiers == {}
        assert "any_peer" not in key_mapping
        assert key_mapping.get_verifier("any_peer") is None

    def test_key_mapping_with_many_verifiers(self, signer):
        """Test KeyMapping with many verifiers."""
        verifiers = {}
        for i in range(100):
            peer_id = f"peer_{i}"
            public_key = Ed25519PrivateKey.generate().public_key()
            verifiers[peer_id] = Verifier(peer_id, public_key)

        key_mapping = KeyMapping(signer, verifiers)

        assert len(key_mapping.verifiers) == 100
        assert "peer_50" in key_mapping
        assert key_mapping.get_verifier("peer_99") is not None

    def test_key_mapping_modification(self, key_mapping):
        """Test that KeyMapping verifiers can be modified after creation."""
        new_verifier = Verifier("new_peer", Ed25519PrivateKey.generate().public_key())
        key_mapping.verifiers["new_peer"] = new_verifier

        assert "new_peer" in key_mapping
        assert key_mapping.get_verifier("new_peer") == new_verifier


class TestCryptoIntegration:
    """Integration tests for crypto components working together."""

    def test_multi_peer_communication(self):
        """Test multiple peers can communicate with each other."""
        # Create three signers
        signer_a = Signer("peer_a", Ed25519PrivateKey.generate())
        signer_b = Signer("peer_b", Ed25519PrivateKey.generate())
        signer_c = Signer("peer_c", Ed25519PrivateKey.generate())

        # Create verifiers
        verifiers = {
            "peer_a": signer_a.get_verifier(),
            "peer_b": signer_b.get_verifier(),
            "peer_c": signer_c.get_verifier(),
        }

        # Create key mappings for each peer
        mapping_b = KeyMapping(signer_b, verifiers)
        mapping_c = KeyMapping(signer_c, verifiers)

        # Test that peer A can send to peer B and C
        message = "Hello from A"
        encoded = signer_a.encode_message(message)

        # Peer B should be able to verify message from A
        verifier_a_at_b = mapping_b.get_verifier("peer_a")
        assert verifier_a_at_b is not None
        decoded_at_b = verifier_a_at_b.decode_message(encoded)
        assert decoded_at_b == message

        # Peer C should be able to verify message from A
        verifier_a_at_c = mapping_c.get_verifier("peer_a")
        assert verifier_a_at_c is not None
        decoded_at_c = verifier_a_at_c.decode_message(encoded)
        assert decoded_at_c == message

    def test_message_tampering_detection(self):
        """Test that tampered messages are detected."""
        signer = Signer("sender", Ed25519PrivateKey.generate())
        verifier = signer.get_verifier()

        original_message = "Important message"
        encoded = signer.encode_message(original_message)

        # Tamper with the message by modifying a character in the content
        parts = encoded.split(".")
        tampered_content = base64.b64encode(b"Tampered message").decode("utf-8")
        tampered_encoded = f"{parts[0]}.{tampered_content}"

        # Verification should fail
        decoded = verifier.decode_message(tampered_encoded)
        assert decoded is None

    def test_signature_tampering_detection(self):
        """Test that tampered signatures are detected."""
        signer = Signer("sender", Ed25519PrivateKey.generate())
        verifier = signer.get_verifier()

        original_message = "Important message"
        encoded = signer.encode_message(original_message)

        # Tamper with the signature
        parts = encoded.split(".")
        tampered_sig = base64.b64encode(b"fake_signature_bytes").decode("utf-8")
        tampered_encoded = f"{tampered_sig}.{parts[1]}"

        # Verification should fail
        decoded = verifier.decode_message(tampered_encoded)
        assert decoded is None

    def test_file_based_key_persistence(self):
        """Test that keys can be saved and loaded from files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create signer and save keys
            signer1 = Signer.by_id("persistent_peer", temp_dir)
            message = "Test persistence"
            encoded = signer1.encode_message(message)

            # Load signer again (should load same key)
            signer2 = Signer.by_id("persistent_peer", temp_dir)
            verifier2 = signer2.get_verifier()

            # Should be able to verify message from first signer
            decoded = verifier2.decode_message(encoded)
            assert decoded == message

            # Both signers should have same keys
            assert signer1.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ) == signer2.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )

    def test_cross_platform_compatibility(self):
        """Test that encoded messages work across different instances."""
        # Create signer
        private_key = Ed25519PrivateKey.generate()
        signer = Signer("test_peer", private_key)

        # Create verifier from public key
        verifier = Verifier("test_peer", private_key.public_key())

        # Test various message types
        test_messages = [
            "",  # Empty
            "Simple message",  # ASCII
            "Message with números 123 and símbolos !@#$%",  # Mixed
            "Unicode: 你好世界 🌍 مرحبا العالم",  # Unicode
            "Very long message " * 100,  # Long message
        ]

        for original in test_messages:
            encoded = signer.encode_message(original)
            decoded = verifier.decode_message(encoded)
            assert decoded == original, f"Failed for message: {original[:50]}..."

    def test_verifier_by_id_invalid_key_type_in_file(self, tmp_path):
        """Test Verifier.by_id when file contains non-Ed25519 key."""
        from cryptography.hazmat.primitives.asymmetric import rsa

        # Create the test_peer.pub file with RSA key in tmp_path root
        key_path = tmp_path / "test_peer.pub"

        # Create an RSA key (invalid type)
        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        rsa_public = rsa_key.public_key()

        # Save as PEM
        pem = rsa_public.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        key_path.write_bytes(pem)

        # Should raise ValueError for invalid key type
        with pytest.raises(ValueError, match="not an Ed25519 public key"):
            Verifier.by_id("test_peer", str(tmp_path))

    def test_signer_by_id_invalid_key_type_in_file(self, tmp_path):
        """Test Signer.by_id when file contains non-Ed25519 key."""
        from cryptography.hazmat.primitives.asymmetric import rsa

        # Create the test_peer.key file with RSA key in tmp_path root
        key_path = tmp_path / "test_peer.key"

        # Create an RSA key (invalid type)
        rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        # Save as PEM
        pem = rsa_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        key_path.write_bytes(pem)

        # Should raise ValueError for invalid key type
        with pytest.raises(ValueError, match="not an Ed25519 private key"):
            Signer.by_id("test_peer", str(tmp_path))
