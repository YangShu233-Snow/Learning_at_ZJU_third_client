import asyncio
import logging
from dataclasses import dataclass, field

from httpx import AsyncClient

from .credentials import EncryptedCredentialStore

logger = logging.getLogger(__name__)


@dataclass
class MonitorTask:
    task_id: str
    api_config_path: str
    interval: int
    action: str = "cache"
    id_field: str = "id"
    enabled: bool = True
    is_system: bool = True
    description: str = ""


class UserSession:
    def __init__(self, token: str, studentid: str, zju_client: AsyncClient):
        self.token = token
        self.studentid = studentid
        self.zju_client = zju_client
        self.tasks: dict[str, MonitorTask] = {}
        self.overrides: dict[str, dict] = {}
        self.caches: dict[str, dict | list] = {}
        self.seen_ids: dict[str, set[int]] = {}
        self.task_coros: dict[str, asyncio.Task] = {}
        self.last_access: float = 0

    async def close(self):
        for coro in self.task_coros.values():
            coro.cancel()
        await self.zju_client.aclose()


class ServerState:
    def __init__(self):
        self.sessions: dict[str, UserSession] = {}
        self.studentid_map: dict[str, str] = {}
        self.credential_store: EncryptedCredentialStore = EncryptedCredentialStore()
        self.system_tasks: list[MonitorTask] = field(default_factory=list)
        self.lock = asyncio.Lock()
        self._start_time: float = 0

    @property
    def uptime(self) -> float:
        import time
        return time.time() - self._start_time if self._start_time else 0
