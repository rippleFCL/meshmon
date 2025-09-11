# import statements
import base64
import os
import logging
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger("distmon.crypto")


class Verifier:
    def __init__(self, peer_id: str, public_key: Ed25519PublicKey):
        self.vid = peer_id
        self.public_key = public_key

    @classmethod
    def by_id(cls, peer_id: str, key_dir):
        logger.debug(f"Loading public key for peer: {peer_id}")
        os.makedirs(key_dir, exist_ok=True)
        key_path = os.path.join(key_dir, f"{peer_id}.pub")
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                public_bytes = f.read()
            public_key = serialization.load_pem_public_key(public_bytes)
            if not isinstance(public_key, Ed25519PublicKey):
                logger.error(f"Invalid key type for {peer_id}: not Ed25519")
                raise ValueError("The loaded key is not an Ed25519 public key.")
            logger.debug(f"Successfully loaded public key for peer: {peer_id}")
        else:
            logger.warning(f"Public key file not found: {key_path}")
            raise FileNotFoundError(f"Public key file not found: {key_path}")
        return cls(peer_id, public_key)

    def decode_message(self, message: str) -> str | None:
        b64_sig, b64_content = message.split(".")
        content = base64.b64decode(b64_content)
        sig = base64.b64decode(b64_sig)
        if not self.verify(content, sig):
            return None
        return content.decode("utf-8")

    def verify(self, message: bytes, signature: bytes) -> bool:
        """
        Verify the signature of the raw message using the public key.
        """
        try:
            self.public_key.verify(signature, message)
            logger.debug(f"Signature verification successful for peer: {self.vid}")
            return True
        except InvalidSignature:
            logger.debug(f"Signature verification failed for peer: {self.vid}")
            return False

    def save(self, peer_id: str, key_dir: str):
        os.makedirs(key_dir, exist_ok=True)
        key_path = os.path.join(key_dir, f"{peer_id}.pub")
        with open(key_path, "wb") as f:
            f.write(
                self.public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )


class Signer:
    def __init__(self, peer_id: str, private_key: Ed25519PrivateKey):
        self.sid = peer_id
        self.private_key = private_key
        self.public_key = private_key.public_key()

    @classmethod
    def by_id(cls, peer_id: str, net_id: str, key_dir: str = "config/.private_keys"):
        logger.debug(f"Loading private key for peer: {peer_id}")
        os.makedirs(key_dir, exist_ok=True)
        key_path = os.path.join(key_dir, f"{peer_id}_{net_id}.key")
        if os.path.exists(key_path):
            logger.debug(f"Found existing private key for {peer_id}")
            with open(key_path, "rb") as f:
                private_bytes = f.read()
            private_key = serialization.load_pem_private_key(
                private_bytes, password=None
            )
            if not isinstance(private_key, Ed25519PrivateKey):
                logger.error(f"Invalid key type for {peer_id}: not Ed25519")
                raise ValueError("The loaded key is not an Ed25519 private key.")
        else:
            logger.info(f"Generating new private key for {peer_id}")
            private_key = Ed25519PrivateKey.generate()
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            with open(key_path, "wb") as f:
                f.write(private_bytes)
            logger.debug(f"Saved new private key for {peer_id}")
        return cls(peer_id, private_key)

    def encode_message(self, content: str) -> str:
        sig = self.sign(content.encode("utf-8"))
        b64_sig = base64.b64encode(sig).decode("utf-8")
        b64_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        return f"{b64_sig}.{b64_content}"

    def sign(self, message: bytes) -> bytes:
        """
        Sign the raw message with the private key (Ed25519 expects raw message input).
        """
        return self.private_key.sign(message)

    def get_verifier(self) -> Verifier:
        return Verifier(self.sid, self.public_key)


class KeyMapping:
    def __init__(self, signer: Signer, verifiers: dict[str, Verifier]):
        self.signer = signer
        self.verifiers = verifiers

    def __contains__(self, peer_id: str) -> bool:
        return peer_id in self.verifiers

    def get_verifier(self, peer_id: str) -> Verifier | None:
        return self.verifiers.get(peer_id)
