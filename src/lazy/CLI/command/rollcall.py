import asyncio
import logging
import uuid
from functools import partial
from textwrap import dedent
from typing import Annotated

import typer
from asyncer import syncify
from rich import print as rprint
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from ...core.load_config import load_config
from ...core.login.login import CredentialManager, ZjuAsyncClient
from ...core.zjuAPI import zju_api
from ..state import state
from .subcommand import rollcall_config

logger = logging.getLogger(__name__)

app = typer.Typer(help="""
    处理学在浙大签到任务
    """,
    no_args_is_help=True
)

# --- 数字签到并发全局事件 ---
number_found_event = asyncio.Event()
# --- 数字签到并发全局事件 ---

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

async def answer_radar_rollcall(rollcall_id: int, site: str):
    device_id = generate_device_id()
    latitude, longitude = site.split(',')
    rollcall_data = {
        "accuracy": 64,
        "altitude": None,
        "altitudeAccuracy": None,
        "deviceId": device_id,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "speed": None
    }
    cookies = CredentialManager().load_cookies()
    if not cookies:
        rprint("Cookies不存在！")
        logger.error("Cookies不存在！")
        raise typer.Exit(code=1)
        

    async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
        raw_rollcall_answer_list = await zju_api.rollcallAnswerRadarAPIFits(
            client.session, rollcall_id, rollcall_data
        ).put_api_data()
    
    raw_rollcall_answer = raw_rollcall_answer_list[0]
    
    if not raw_rollcall_answer or not isinstance(raw_rollcall_answer, dict):
        print(f"{rollcall_id} 签到失败！")
    
    elif raw_rollcall_answer.get("status_name") == "on_call_fine":
        rprint("[bold green]签到成功！[/bold green] ✅")
        rprint(f"  - 纬度: {latitude}")
        rprint(f"  - 经度: {longitude}")

    elif raw_rollcall_answer.get("error_code") == "radar_out_of_rollcall_scope":
        distance = raw_rollcall_answer.get('distance', '未知')
        rprint("[bold yellow]签到失败：不在范围内！[/bold yellow] ❌")
        rprint(f"  - 你选择的地点距离签到点约 [cyan]{distance}米[/cyan]。")

    else:
        rprint("[bold red]签到失败！请将此问题上报开发者！[/bold red] 收到未知的API响应:")
        rprint(raw_rollcall_answer)

# --- 数字点名并发worker ---
async def check_code_worker(
    client: ZjuAsyncClient,
    rollcall_id: int,
    device_id: str,
    code_int: int,
    semaphore: asyncio.Semaphore,
    progress: Progress,
    task_id: TaskID
) -> str | None:
    global number_found_event
    if number_found_event.is_set():
        return None
    
    code_str = str(code_int).zfill(4)

    async with semaphore:
        if number_found_event.is_set():
            progress.update(task_id, advance=1)
            return None

        rollcall_data = {
            "deviceId": device_id,
            "numberCode": code_str
        }
        
        try:
            api = zju_api.rollcallAnswerNumberAPIFits(client.session, rollcall_id, rollcall_data)
            response_list = await api.put_api_data()
            response = response_list[0]
            
            if response and isinstance(response, dict): 
                # 找到了!
                number_found_event.set() # 通知所有其他协程停止
                progress.update(task_id, description=f"[bold green]🎉 找到了! 签到码: {code_str} 🎉[/bold green]")
                return code_str
            return None # [False] 或其他错误，继续
        
        except asyncio.CancelledError:
            return None # 任务被取消
        except Exception:
            return None # 忽略单个请求的错误，继续爆破
        finally:
            if not number_found_event.is_set():
                progress.update(task_id, advance=1) # 更新进度条

async def answer_number_rollcall(rollcall_id: int, number_code: str|None):
    if number_code:
        code_str = number_code.zfill(4)
    device_id = generate_device_id()
    cookies = CredentialManager().load_cookies()
    if not cookies:
        rprint("Cookies不存在！")
        logger.error("Cookies不存在！")
        raise typer.Exit(code=1)

    async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
        if number_code:
            rollcall_data = {
                "deviceId": device_id,
                "numberCode": code_str
            }

            raw_rollcall_answer_list = await zju_api.rollcallAnswerNumberAPIFits(
                client.session, rollcall_id, rollcall_data
            ).put_api_data()

            raw_rollcall_answer = raw_rollcall_answer_list[0]

            if raw_rollcall_answer and isinstance(raw_rollcall_answer, dict):
                    rprint(f"[bold green]签到成功！[/bold green] ✅ (代码: {code_str})")
            else:
                    rprint(f"[bold red]签到失败！[/bold red] ❌ (代码: {code_str} 错误或无效)")

        else:
            # --- 并发爆破 ---
            global number_found_event
            number_found_event.clear()

            # 最大并发数
            CONCURRENCY_LIMIT = 100
            semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("({task.completed} / {task.total})"),
                TimeElapsedColumn(),
                transient=True # 签到结束后自动消失
            ) as progress:
                
                bruteforce_task_id = progress.add_task(
                    f"并发爆破 [cyan](n={CONCURRENCY_LIMIT})[/cyan]...", 
                    total=10000
                )
                
                # 创建 10000 个任务
                tasks = [
                    asyncio.create_task(
                        check_code_worker(client, rollcall_id, device_id, i, semaphore, progress, bruteforce_task_id)
                    ) for i in range(10000)
                ]
                
                # 等待所有任务完成 (或被 found_event 提前终止)
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # --- 进度条结束，报告结果 ---
            found_code = None
            for res in results:
                if isinstance(res, str): # 成功的 worker 会返回
                    found_code = res
                    break
            
            if found_code:
                rprint(f"[bold green]✅ 爆破成功！ 签到码是: {found_code}[/bold green]")
            else:
                rprint("[bold red]❌ 爆破失败。未找到签到码。[/bold red]")

# --- 注册签到任务查看命令 ---
@app.command(
        "ls",
        hidden=True,
        help="Alias for 'list'",
        epilog=dedent("""
            EXAMPLES:
              
              $ lazy rollcall list
                (查看当前正在进行的签到任务) 
        """))
@app.command(
        "list",
        help="查看学在浙大签到任务",
        epilog=dedent("""
            EXAMPLES:
              
              $ lazy rollcall list
                (查看当前正在进行的签到任务) 
        """))
@partial(syncify, raise_sync_error=False)
async def list_rollcall():
    """
    查看学在浙大正在进行的签到任务。
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(description="请求数据中...", total=2)
        cookies = CredentialManager().load_cookies()
        if not cookies:
            rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)

        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            raw_rollcalls_list = (await zju_api.rollcallListAPIFits(client.session).get_api_data())[0]
        
        rollcalls_list: list[dict] = raw_rollcalls_list.get("rollcalls", [])

        progress.update(task, description="渲染数据中...", completed=1)

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

        rollcall_list_table.add_column("签到任务ID", style="cyan", ratio=2)
        rollcall_list_table.add_column("课程名称", style="bright_yellow", ratio=4)
        rollcall_list_table.add_column("签到发起者", ratio=2)
        rollcall_list_table.add_column("签到属性", ratio=2)

        for rollcall in rollcalls_list:
            rollcall_course_title = rollcall.get("course_title", "null")
            rollcall_initiator = rollcall.get("created_by_name", "null")
            rollcall_id = str(rollcall.get("rollcall_id", "null"))
            rollcall_is_radar = rollcall.get("is_radar", False)

            rollcall_description = "雷达点名" if rollcall_is_radar else "非雷达点名"

            rollcall_list_table.add_row(
                rollcall_id,
                rollcall_course_title,
                rollcall_initiator,
                rollcall_description
            )
        
        progress.advance(task)
        rprint(rollcall_list_table)

# --- 注册签到任务应答命令 ---
@app.command(
        "as",
        help="Alias for 'answer'",
        hidden=True,
        epilog=dedent("""
            EXAMPLES: 
                      
              $ lazy rollcall answer 114514 -s your_site
                (以"your_site"配置项完成ID为"114514"的雷达点名任务)
                      
              $ lazy rollcall answer 114514 -n 2333
                (以"2333"应答ID为"114514"的数字点名任务)
        """),
        no_args_is_help=True)
@app.command(
        "answer",
        help="应答指定签到任务",
        epilog=dedent("""
            EXAMPLES: 
                      
              $ lazy rollcall answer 114514 -s your_site
                (以"your_site"配置项完成ID为"114514"的雷达点名任务)
                      
              $ lazy rollcall answer 114514 -n 2333
                (以"2333"应答ID为"114514"的数字点名任务)
        """),
        no_args_is_help=True)
@partial(syncify, raise_sync_error=False)
async def answer_rollcall(
    rollcall_id: Annotated[int, typer.Argument(help="签到任务id")],
    
    site: Annotated[str | None, typer.Option(
        "--site", "-s", 
        help="雷达点名：签到定位配置"
    )] = None,
    
    number: Annotated[str | None, typer.Option(
        "--number", "-n", 
        help="数字点名：提供4位数字 (如 0001)"
    )] = None,
    
    bruteforce: Annotated[bool, typer.Option(
        "--bruteforce", "-b", 
        help="数字点名：启用并发爆破 (0000-9999)"
    )] = False
):  
    """
    应答学在浙大签到任务

    以 -s 指定已配置地点应答雷达点名任务

    以 -n 指定签到码应答数字点名任务

    以 -b 启用对数字点名的爆破
    """
    
    modes = [site is not None, number is not None, bruteforce]
    
    if sum(modes) == 0:
        rprint("[bold red]错误：[/bold red] 请指定一种签到模式。")
        rprint("  - [cyan]lazy rollcall answer <ID> --site <地点>[/cyan]")
        rprint("  - [cyan]lazy rollcall answer <ID> --number <代码>[/cyan]")
        rprint("  - [cyan]lazy rollcall answer <ID> --bruteforce[/cyan]")
        raise typer.Exit(code=1)
        
    if sum(modes) > 1:
        rprint("[bold red]错误：[/bold red] 请不要同时使用 --site, --number, 或 --bruteforce。")
        raise typer.Exit(code=1)

    # --- 调度 ---
    if site:
        rprint("[bold blue]检测到 --site, 启动 [雷达] 签到...[/bold blue]")
        site = get_site_coordinate(site)
        await answer_radar_rollcall(rollcall_id, site)
    
    elif number:
        rprint("[bold blue]检测到 --number, 启动 [数字(单次)] 签到...[/bold blue]")
        await answer_number_rollcall(rollcall_id, number)
    
    elif bruteforce:
        rprint("[bold blue]检测到 --bruteforce, 启动 [数字(爆破)] 签到...[/bold blue]")
        await answer_number_rollcall(rollcall_id, None)

# --- 配置命令组 ---
app.add_typer(rollcall_config.app, name="config", help="管理签到定位配置")
