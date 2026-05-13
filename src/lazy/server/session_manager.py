import logging

import httpx

from ..core.login.login import ZjuAsyncClient

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
}


async def create_user_client(cookies: dict | None = None) -> ZjuAsyncClient:
    client = ZjuAsyncClient.__new__(ZjuAsyncClient)
    ZjuAsyncClient.__init__(client, cookies=cookies, trust_env=False)
    client.session = httpx.AsyncClient(
        trust_env=False,
        timeout=20.0,
        follow_redirects=True,
    )
    client.session.headers.update(_DEFAULT_HEADERS)
    if cookies:
        client.session.cookies.update(cookies)
    return client


async def login_and_save_cookies(client: ZjuAsyncClient, studentid: str, password: str) -> bool:
    return await client.login(studentid, password)
