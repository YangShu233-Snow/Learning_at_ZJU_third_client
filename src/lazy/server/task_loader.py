import json
import logging
from pathlib import Path

from .state import MonitorTask

SERVER_DIR = Path.home() / ".lazy_server"
TASKS_TEMPLATE_PATH = SERVER_DIR / "tasks.json"

_DEFAULT_TASKS = {
    "system_tasks": [
        {
            "id": "rollcall_watch",
            "type": "poll",
            "api_config_path": "rollcall.rollcall",
            "interval": 30,
            "action": "cache",
            "id_field": "rollcall_id",
            "description": "监控进行中的点名",
        },
        {
            "id": "todo_watch",
            "type": "poll",
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
    if not TASKS_TEMPLATE_PATH.exists():
        SERVER_DIR.mkdir(exist_ok=True)
        TASKS_TEMPLATE_PATH.write_text(
            json.dumps(_DEFAULT_TASKS, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def load_system_tasks() -> list[MonitorTask]:
    ensure_tasks_template()
    try:
        data = json.loads(TASKS_TEMPLATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"读取任务模板失败: {e}")
        data = _DEFAULT_TASKS
    return [MonitorTask(**t) for t in data.get("system_tasks", [])]
