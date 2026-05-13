import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..auth import generate_token
from ..monitor import merge_tasks, start_monitor_for_user, stop_monitor_for_user
from ..session_manager import create_user_client, login_and_save_cookies
from ..state import ServerState, UserSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthRequest(BaseModel):
    studentid: str
    password: str


class AuthResponse(BaseModel):
    token: str
    studentid: str


async def _authenticate(body: AuthRequest, state: ServerState, is_new: bool) -> AuthResponse:
    studentid = body.studentid.strip()
    password = body.password

    stored = state.credential_store.get(studentid)
    if is_new and stored:
        raise HTTPException(status_code=409, detail="该学号已注册")
    if not is_new and not stored:
        raise HTTPException(status_code=404, detail="该学号未注册")

    existing_token = state.studentid_map.get(studentid)
    if existing_token and existing_token in state.sessions:
        old_session = state.sessions[existing_token]
        await stop_monitor_for_user(old_session)
        await old_session.close()
        del state.sessions[existing_token]
        del state.studentid_map[studentid]

    cookies = stored.get("cookies") if stored else None
    client = await create_user_client(cookies=cookies)
    is_logged_in = False

    if cookies:
        valid = await client.is_valid_session()
        if valid:
            is_logged_in = True

    if not is_logged_in:
        if not await login_and_save_cookies(client, studentid, password):
            await client.session.aclose()
            raise HTTPException(status_code=401, detail="学号或密码错误")
        state.credential_store.update_cookies(studentid, dict(client.session.cookies))

    token = generate_token()
    user = UserSession(token=token, studentid=studentid, zju_client=client.session)
    user.tasks = merge_tasks(state.system_tasks, user.overrides)
    state.sessions[token] = user
    state.studentid_map[studentid] = token

    await start_monitor_for_user(state, user)

    return AuthResponse(token=token, studentid=studentid)


@router.post("/register", response_model=AuthResponse)
async def register(request: Request, body: AuthRequest):
    state: ServerState = request.app.state.server_state
    return await _authenticate(body, state, is_new=True)


@router.post("/login", response_model=AuthResponse)
async def login(request: Request, body: AuthRequest):
    state: ServerState = request.app.state.server_state
    return await _authenticate(body, state, is_new=False)
