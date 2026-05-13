import logging

from ..core.login.login import ZjuAsyncClient

logger = logging.getLogger(__name__)


async def create_user_client(cookies: dict | None = None, trust_env: bool = False) -> ZjuAsyncClient:
    client = ZjuAsyncClient.__new__(ZjuAsyncClient)
    ZjuAsyncClient.__init__(client, cookies=cookies, trust_env=trust_env)
    client.session = await client._init_session()
    return client


async def login_and_save_cookies(client: ZjuAsyncClient, studentid: str, password: str) -> bool:
    return await client.login(studentid, password)
