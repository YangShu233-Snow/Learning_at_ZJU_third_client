import json
from datetime import datetime

from rich.text import Text


def print_with_json(status: bool, description: str|None = None, result = None):
    text = {
        "status": status,
        "description": description,
        "result": result
    }
    print(json.dumps(text, ensure_ascii=False))

def transform_time(time: str|None)->str:
    if time:
        time_local = datetime.fromisoformat(time.replace('Z', '+00:00')).astimezone()
        return time_local.strftime('%Y-%m-%d %H:%M:%S')
    return "null"


def make_jump_url(course_id: int, material_id: int, material_type: str)->str:
    if material_type == "material":
        return ""
    
    if material_type == "online_video" or material_type == "homework":
        return f"https://courses.zju.edu.cn/course/{course_id}/learning-activity/full-screen#/{material_id}"

    return f"https://courses.zju.edu.cn/course/{course_id}/learning-activity/full-screen#/{material_type}/{material_id}"

def get_status_text(start_status: bool, close_status: bool)->Text:
    if close_status:
        return Text("🔴 已结束", style="red")
    
    if start_status:
        return Text("🟢 进行中", style="green")
    
    return Text("⚪️ 未开始", style="dim")