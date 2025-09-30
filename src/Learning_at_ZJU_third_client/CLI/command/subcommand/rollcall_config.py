import typer
import logging
from typing import List, Annotated, Optional
from ....load_config import load_config

logger = logging.getLogger(__name__)

app = typer.Typer(help="""
    签到定位配置相关命令组
    """,
    no_args_is_help=True
)

def is_latitude_valid(latitude: float)->float:
    if latitude > 90 or latitude < -90:
        print(f"纬度数据 {latitude} 有误！")
        raise typer.Exit(code=1)
    
    return latitude

def is_longtitude_valid(longtitude: float)->float:
    if longtitude > 180 or longtitude < -180:
        print(f"经度数据 {longtitude} 有误！")
        raise typer.Exit(code=1)
    
    return longtitude

@app.command("list")
def list_config():
    """
    列举配置项
    """
    rollcall_site_config = load_config.rollcallSiteConfig().load_config()
    coordinates_config: dict = rollcall_site_config.get("coordinates", {})

    for coordinates_name, coordinates in coordinates_config.items():
        latitude, longtitude = coordinates

        print(f"{coordinates_name}: ({latitude}, {longtitude})")

    return 

@app.command("add")
def add_config(
    name: Annotated[str, typer.Option("--name", "-n", help="配置项名称")],
    latitude: Annotated[float, typer.Option("--latitude", "-L", help="纬度", callback=is_latitude_valid)],
    longtitude: Annotated[float, typer.Option("--longtitude", "-l", help="经度", callback=is_longtitude_valid)],
    force: Annotated[Optional[bool], typer.Option("--force", "-f", help="启用此选项，强制替换对应配置项")] = False
):
    """
    添加配置项，配置项的名称不可重复，重复名称的新配置项会覆盖旧配置项
    """
    rollcall_site_config = load_config.rollcallSiteConfig().load_config()
    coordinates_config: dict = rollcall_site_config.get("coordinates", {})

    if name in coordinates_config and not force:
        print(f"{name} 已存在配置当中！")
        return
    
    coordinates_config[name] = [latitude, longtitude]
    rollcall_site_config["coordinates"] = coordinates_config
    load_config.rollcallSiteConfig().update_config(rollcall_site_config)
    print("更新成功")

    return 

@app.command("remove")
def remove_config(
    name: Annotated[str, typer.Argument(help="配置项名称")],
    force: Annotated[Optional[bool], typer.Option("--force", "-f", help="启用此选项，跳过二次确认")] = False
):
    """
    删除配置项
    """
    rollcall_site_config = load_config.rollcallSiteConfig().load_config()
    coordinates_config: dict = rollcall_site_config.get("coordinates", {})

    if name not in coordinates_config:
        print(f"{name} 不存在！")
        return
    
    latitude, longtitude = coordinates_config[name]

    if not force:
        print(f"本次要删除:\n  {name}: {latitude, longtitude}")
        delete = typer.confirm("你确定要删除它们吗?")

        if not delete:
            print("已取消")
            raise typer.Exit()
    
    try:
        del coordinates_config[name]
    except Exception as e:
        logger.error(f"{e}")
        print("删除失败！")
        raise typer.Exit(code=1)
    
    rollcall_site_config["coordinates"] = coordinates_config
    load_config.rollcallSiteConfig().update_config(rollcall_site_config)

    return

@app.command("init")
def init_config(
    force: Annotated[Optional[bool], typer.Option("--force", "-f", help="强制初始化配置文件，跳过二次确认")] = False
):
    """
    初始化签到配置文件，第一次使用签到命令，或者签到配置文件出现损坏时候调用。
    """
    # 检查文件是否正常
    rollcall_site_config = load_config.rollcallSiteConfig().load_config()
    
    if not force:
        if "device_id" in rollcall_site_config and "coordinates" in rollcall_site_config and type(rollcall_site_config.get("coordinates")) == dict:
            confirmation = typer.confirm("签到配置文件正常，你确定要初始化它吗？")
            if not confirmation:
                return

    default_config = {
        "device_id": "",
        "coordinates": {}
    }

    load_config.rollcallSiteConfig().update_config(default_config)
    print("配置文件初始化完成！")