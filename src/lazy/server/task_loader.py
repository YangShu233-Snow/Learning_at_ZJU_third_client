import dataclasses
import json
import logging
from pathlib import Path

from .state import MonitorTask

SERVER_DIR = Path.home() / ".lazy_server"
TASKS_TEMPLATE_PATH = SERVER_DIR / "tasks.json"

_TASK_FIELDS = {f.name for f in dataclasses.fields(MonitorTask)}

_DEFAULT_TASKS = {
    "system_tasks": [
        {
            "task_id": "rollcall_watch",
            "api_config_path": "rollcall.rollcall",
            "interval": 30,
            "action": "cache",
            "id_field": "rollcall_id",
            "description": "监控进行中的点名",
        },
        {
            "task_id": "todo_watch",
            "api_config_path": "assignment.todo",
            "interval": 60,
            "action": "cache",
            "id_field": "id",
            "description": "监控待办任务",
        },
    ]
}

logger = logging.getLogger(__name__)


def ensure_tasks_template():
    if TASKS_TEMPLATE_PATH.exists():
        try:
            existing = json.loads(TASKS_TEMPLATE_PATH.read_text(encoding="utf-8"))
            tasks = existing.get("system_tasks", [])
            if any("id" in t and "task_id" not in t for t in tasks):
                logger.info("检测到旧格式 tasks.json，正在覆盖...")
                TASKS_TEMPLATE_PATH.write_text(
                    json.dumps(_DEFAULT_TASKS, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        except Exception:
            TASKS_TEMPLATE_PATH.write_text(
                json.dumps(_DEFAULT_TASKS, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    else:
        SERVER_DIR.mkdir(exist_ok=True)
        TASKS_TEMPLATE_PATH.write_text(
            json.dumps(_DEFAULT_TASKS, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _normalize_task(t: dict) -> dict:
    if "id" in t and "task_id" not in t:
        t["task_id"] = t.pop("id")
    return {k: v for k, v in t.items() if k in _TASK_FIELDS}


def load_system_tasks() -> list[MonitorTask]:
    ensure_tasks_template()
    try:
        data = json.loads(TASKS_TEMPLATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"读取任务模板失败: {e}")
        data = _DEFAULT_TASKS
    return [MonitorTask(**_normalize_task(t)) for t in data.get("system_tasks", [])]
