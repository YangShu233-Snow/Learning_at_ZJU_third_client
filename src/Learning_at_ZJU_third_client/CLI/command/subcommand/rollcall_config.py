import typer
from typing import List, Annotated, Optional
from load_config import load_config
from printlog.print_log import print_log

app = typer.Typer(help="""
    签到定位配置相关命令组
""")

@app.command("list")
def list_config():
    rollcall_site_config = load_config.rollcallSiteConfig().load_config()
    coordinates_config: dict = rollcall_site_config.get("coordinates", {})

    for coordinates_name, coordinates in coordinates_config.items():
        latitude, longtitude = coordinates

        print(f"{coordinates_name}: ({latitude}, {longtitude})")

    return 

@app.command("add")
def add_config(
    name: Annotated[str, typer.Option("--name", "-n", help="配置项名称")],
    latitude: Annotated[float, typer.Option("--latitude", "-L", help="纬度")],
    longtitude: Annotated[float, typer.Option("--longtitude", "-l", help="经度")],
    force: Annotated[Optional[bool], typer.Option("--force", "-f", help="启用此选项，强制替换对应配置项")] = False
):
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
        print_log("Error", f"{e}", "CLI.command.subcommand.rollcall_config.remove_config")
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