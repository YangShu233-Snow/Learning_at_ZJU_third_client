import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from ..monitor import merge_tasks, start_monitor_for_user, stop_monitor_for_user
from ..state import ServerState, UserSession

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _get_user(request: Request, token: str = Query(...)) -> UserSession:
    state: ServerState = request.app.state.server_state
    user = state.sessions.get(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token 无效")
    user.last_access = time.time()
    return user


class TaskOverride(BaseModel):
    interval: int | None = None
    enabled: bool | None = None


@router.get("")
async def list_tasks(request: Request, user: UserSession = Depends(_get_user)):  # noqa: B008
    state: ServerState = request.app.state.server_state
    merged = merge_tasks(state.system_tasks, user.overrides)
    results = []
    for t in merged.values():
        results.append({
            "task_id": t.task_id,
            "description": t.description,
            "interval": t.interval,
            "action": t.action,
            "enabled": t.enabled,
            "is_system": t.is_system,
            "has_override": t.task_id in user.overrides,
            "cache_status": "cached" if t.task_id in user.caches else "pending",
        })
    return {"tasks": results}


@router.put("/{task_id}")
async def update_task(request: Request, task_id: str, override: TaskOverride, user: UserSession = Depends(_get_user)):  # noqa: B008
    state: ServerState = request.app.state.server_state
    system_ids = {t.task_id for t in state.system_tasks}
    if task_id not in system_ids:
        raise HTTPException(status_code=404, detail="任务不存在")

    current = user.overrides.get(task_id, {})
    if override.interval is not None:
        current["interval"] = override.interval
    if override.enabled is not None:
        current["enabled"] = override.enabled
    user.overrides[task_id] = current

    await stop_monitor_for_user(user)
    user.tasks = merge_tasks(state.system_tasks, user.overrides)
    await start_monitor_for_user(state, user)

    return {"status": "ok", "task_id": task_id, "override": current}


@router.delete("/{task_id}")
async def reset_task(request: Request, task_id: str, user: UserSession = Depends(_get_user)):  # noqa: B008
    state: ServerState = request.app.state.server_state
    if task_id not in user.overrides:
        return {"status": "ok", "task_id": task_id, "message": "无个人覆写，无需重置"}

    del user.overrides[task_id]

    await stop_monitor_for_user(user)
    user.tasks = merge_tasks(state.system_tasks, user.overrides)
    await start_monitor_for_user(state, user)

    return {"status": "ok", "task_id": task_id, "message": "已重置为系统模板"}
