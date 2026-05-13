import logging
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from ..core.printlog.print_log import setup_global_logging
from .monitor import start_monitor_for_user, stop_monitor_for_user
from .routers import auth, data, health, tasks
from .session_manager import create_user_client
from .state import ServerState, UserSession
from .task_loader import load_system_tasks

logger = logging.getLogger(__name__)

SERVER_STATE = ServerState()


def get_server_state() -> ServerState:
    return SERVER_STATE


@asynccontextmanager
async def lifespan(app: FastAPI):
    state: ServerState = app.state.server_state
    state._start_time = time.time()
    state.system_tasks = load_system_tasks()

    logger.info(f"加载了 {len(state.system_tasks)} 个系统任务模板")
    logger.info("LAZY SERVER 启动中...")

    for studentid in state.credential_store.list_users():
        try:
            creds = state.credential_store.get(studentid)
            if not creds:
                continue
            cookies = creds.get("cookies")
            client = await create_user_client(cookies=cookies, trust_env=state.trust_env)
            is_valid = False
            if cookies:
                is_valid = await client.is_valid_session()
            if not is_valid:
                password = creds.get("password", "")
                if password and await client.login(studentid, password):
                    is_valid = True
                    state.credential_store.update_cookies(studentid, dict(client.session.cookies))

            if is_valid:
                from .auth import generate_token
                token = generate_token()
                user = UserSession(token=token, studentid=studentid, zju_client=client.session)
                user.tasks = {t.task_id: t for t in state.system_tasks}
                state.sessions[token] = user
                state.studentid_map[studentid] = token
                await start_monitor_for_user(state, user)
                logger.info(f"恢复用户 {studentid} 成功")
            else:
                await client.session.aclose()
                logger.warning(f"用户 {studentid} session 恢复失败，需重新登录")
        except Exception as e:
            logger.error(f"恢复用户 {studentid} 失败: {e}")

    logger.info(f"LAZY SERVER 启动完成，当前在线用户: {len(state.sessions)}")
    yield
    logger.info("LAZY SERVER 关闭中...")
    for _token, user in list(state.sessions.items()):
        await stop_monitor_for_user(user)
        await user.close()
    logger.info("LAZY SERVER 已关闭")


app = FastAPI(
    title="LAZY SERVER",
    description="学在浙大第三方服务端代理",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.server_state = SERVER_STATE

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(data.router)
app.include_router(health.router)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="LAZY SERVER - 学在浙大第三方服务端")
    parser.add_argument("--proxy", action="store_true", help="启用系统代理（环境变量 HTTP_PROXY/HTTPS_PROXY）")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="监听端口 (默认: 8765)")
    args = parser.parse_args()

    SERVER_STATE.trust_env = args.proxy

    setup_global_logging()
    if args.proxy:
        logger.info("系统代理已启用")
    uvicorn.run(
        "lazy.server.app:app",
        host=args.host,
        port=args.port,
        reload=False,
        log_level="info",
    )
