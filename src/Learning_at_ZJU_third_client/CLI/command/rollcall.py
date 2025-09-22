import typer
import uuid
from requests.exceptions import HTTPError
from typing import Annotated, List, Dict
from rich.table import Table
from rich.text import Text
from rich import print as rprint
from zjuAPI import zju_api
from load_config import load_config
from printlog.print_log import print_log

from .subcommand import rollcall_config
from ..state import state

app = typer.Typer(help="""
    学在浙大签到相关命令组
    """
)

def get_site_coordinate(site: str):
    rollcall_site_config: dict = load_config.rollcallSiteConfig().load_config()
    site_coordinate: list = rollcall_site_config.get("coordinates", {}).get(site)

    if site_coordinate:
        return ','.join(map(str, site_coordinate))
    
    print(f"{site} 地点不存在！")
    raise typer.Exit(code=1)
    
def generate_device_id()->str:
    rollcall_site_config: dict = load_config.rollcallSiteConfig().load_config()
    device_id = rollcall_site_config.get("device_id")

    if device_id:
        return device_id
    
    device_id = str(uuid.uuid4())
    rollcall_site_config["device_id"] = device_id
    load_config.rollcallSiteConfig().update_config(rollcall_site_config)

    return device_id

@app.command("list")
def list_rollcall():
    raw_rollcalls_list = zju_api.rollcallListAPIFits(state.client.session).get_api_data()[0]
    rollcalls_list: List[dict] = raw_rollcalls_list.get("rollcalls", [])

    if not rollcalls_list:
        print("暂时还没有签到任务哦~")
        return 

    rollcall_list_table = Table(
        title=f"签到任务 共 {len(rollcalls_list)} 个",
        border_style="bright_black",
        show_header=True,
        header_style="bold magenta",
        expand=True
    )

    rollcall_list_table.add_column("签到任务ID")
    rollcall_list_table.add_column("课程名称")
    rollcall_list_table.add_column("签到发起者")
    rollcall_list_table.add_column("签到属性")

    for rollcall in rollcalls_list:
        rollcall_course_title = rollcall.get("course_title", "null")
        rollcall_initiator = rollcall.get("created_by_name", "null")
        rollcall_id = rollcall.get("rollcall_id", "null")
        rollcall_is_radar = rollcall.get("is_radar", False)

        if rollcall_is_radar:
            rollcall_description = "雷达点名"
        else:
            rollcall_description = "非雷达点名"

        rollcall_list_table.add_row(
            rollcall_id,
            rollcall_course_title,
            rollcall_initiator,
            rollcall_description
        )

    rprint(rollcall_list_table)

@app.command("answer")
def answer_rollcall(
    rollcall_id: Annotated[int, typer.Argument(help="签到任务id")],
    site: Annotated[str, typer.Option("--site", "-s", help="签到定位配置", callback=get_site_coordinate)]
):  
    device_id = generate_device_id()
    latitude, longitude = site.split(',')
    rollcall_data = {
        "accuracy": 64,
        "altitude": None,
        "altitudeAccuracy": None,
        "deviceId": device_id,
        "latitude": latitude,
        "longitude": longitude,
        "speed": None
    }
    raw_rollcall_answer = zju_api.rollcallAnswerAPIFits(state.client.session, rollcall_id, rollcall_data).put_api_data()[0]
    
    if raw_rollcall_answer:
        print(f"签到成功！\n签到纬度: {latitude}\n签到经度: {longitude}")
    else:
        print(f"{rollcall_id} 签到失败！")

    return 

# --- 配置命令组 ---
app.add_typer(rollcall_config.app, name="config", help="签到定位配置相关命令组")