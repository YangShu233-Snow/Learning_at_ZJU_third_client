import asyncio
import logging

from ..core.load_config import load_config
from .state import MonitorTask, ServerState, UserSession

logger = logging.getLogger(__name__)


def resolve_api_config(api_config_path: str) -> dict:
    category, api_name = api_config_path.split(".", 1)
    config = load_config.apiListConfig().load_config().get(category, {})
    return config.get("apis_config", {}).get(api_name, {})


async def run_user_task(user: UserSession, task: MonitorTask):
    logger.info(f"启动监控任务 {task.task_id} | 用户 {user.studentid} | 间隔 {task.interval}s")
    while task.enabled:
        try:
            api_config = resolve_api_config(task.api_config_path)
            url = api_config.get("url")
            params = api_config.get("params", {})

            if not url:
                logger.error(f"{task.task_id}: url 未配置")
                await asyncio.sleep(task.interval)
                continue

            response = await user.zju_client.get(url, params=params, follow_redirects=True)
            response.raise_for_status()
            raw_data = response.json()

            user.caches[task.task_id] = raw_data

            items = _extract_items(raw_data, task.id_field)
            if items:
                ids = {item[task.id_field] for item in items if task.id_field in item}
                old_ids = user.seen_ids.get(task.task_id, set())
                new_ids = ids - old_ids
                user.seen_ids[task.task_id] = ids
                if new_ids:
                    logger.info(f"用户 {user.studentid} | {task.task_id}: 发现 {len(new_ids)} 个新项目")

        except Exception as e:
            logger.warning(f"监控任务 {task.task_id} 失败 (用户 {user.studentid}): {e}")

        await asyncio.sleep(task.interval)


def _extract_items(data, id_field: str) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("rollcalls", "todos", "items", "data", "list", "uploads", "activities"):
            if key in data and isinstance(data[key], list):
                return data[key]
        for v in data.values():
            if isinstance(v, list):
                return v
    return []


async def start_monitor_for_user(state: ServerState, user: UserSession):
    if user.task_coros:
        for coro in user.task_coros.values():
            coro.cancel()
        user.task_coros.clear()

    for task in user.tasks.values():
        if not task.enabled:
            continue
        coro = asyncio.create_task(run_user_task(user, task))
        user.task_coros[task.task_id] = coro
        await asyncio.sleep(0)


async def stop_monitor_for_user(user: UserSession):
    for coro in user.task_coros.values():
        coro.cancel()
    user.task_coros.clear()


def merge_tasks(system_tasks: list[MonitorTask], overrides: dict[str, dict]) -> dict[str, MonitorTask]:
    result: dict[str, MonitorTask] = {}
    for t in system_tasks:
        override = overrides.get(t.task_id, {})
        merged = MonitorTask(
            task_id=t.task_id,
            api_config_path=t.api_config_path,
            interval=override.get("interval", t.interval),
            action=override.get("action", t.action),
            id_field=override.get("id_field", t.id_field),
            enabled=override.get("enabled", t.enabled),
            is_system=t.is_system,
            description=override.get("description", t.description),
        )
        result[t.task_id] = merged
    return result
