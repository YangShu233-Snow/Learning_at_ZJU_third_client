import json
import logging
from pathlib import Path

from cryptography.fernet import Fernet

SERVER_DIR = Path.home() / ".lazy_server"
MASTER_KEY_PATH = SERVER_DIR / "master.key"
CREDENTIALS_PATH = SERVER_DIR / "credentials.enc"

logger = logging.getLogger(__name__)


def _ensure_server_dir():
    SERVER_DIR.mkdir(exist_ok=True)


def _load_or_create_master_key() -> bytes:
    if MASTER_KEY_PATH.exists():
        return MASTER_KEY_PATH.read_bytes()
    key = Fernet.generate_key()
    MASTER_KEY_PATH.write_bytes(key)
    MASTER_KEY_PATH.chmod(0o600)
    return key


class EncryptedCredentialStore:
    def __init__(self):
        _ensure_server_dir()
        self._fernet = Fernet(_load_or_create_master_key())

    def _encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def _decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()

    def save(self, studentid: str, password: str, cookies: dict | None = None):
        entries = self._load_all()
        entries[studentid] = {
            "password": self._encrypt(password),
        }
        if cookies is not None:
            entries[studentid]["cookies"] = self._encrypt(json.dumps(cookies))
        CREDENTIALS_PATH.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")

    def get(self, studentid: str) -> dict | None:
        entries = self._load_all()
        raw = entries.get(studentid)
        if not raw:
            return None
        result = {"studentid": studentid}
        if "password" in raw:
            result["password"] = self._decrypt(raw["password"])
        if "cookies" in raw:
            result["cookies"] = json.loads(self._decrypt(raw["cookies"]))
        return result

    def update_cookies(self, studentid: str, cookies: dict):
        entries = self._load_all()
        if studentid not in entries:
            return
        entries[studentid]["cookies"] = self._encrypt(json.dumps(cookies))
        CREDENTIALS_PATH.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")

    def list_users(self) -> list[str]:
        return list(self._load_all().keys())

    def remove(self, studentid: str):
        entries = self._load_all()
        entries.pop(studentid, None)
        CREDENTIALS_PATH.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")

    def _load_all(self) -> dict:
        if not CREDENTIALS_PATH.exists():
            CREDENTIALS_PATH.write_text("{}", encoding="utf-8")
            return {}
        try:
            return json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("凭据文件损坏，重置为空")
            CREDENTIALS_PATH.write_text("{}", encoding="utf-8")
            return {}
