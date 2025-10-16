import threading


class SecretContainer:
    def __init__(self):
        self.secrets: dict[str, str] = {}
        self.lock = threading.Lock()

    def add_secret(self, key: str, value: str):
        with self.lock:
            self.secrets[key] = value

    def get_secret(self, key: str) -> str | None:
        with self.lock:
            return self.secrets.get(key)

    def delete_secret(self, key: str):
        with self.lock:
            if key in self.secrets:
                del self.secrets[key]

    def validate_secret(self, key: str, value: str) -> bool:
        with self.lock:
            if key not in self.secrets:
                return False
            return self.secrets[key] == value

    def __contains__(self, key: str) -> bool:
        with self.lock:
            return key in self.secrets
