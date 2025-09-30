import typer
import keyring
import httpx
import asyncio
import logging
from asyncer import syncify
from functools import partial
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing_extensions import Annotated, Optional
from ..login.login import ZjuAsyncClient

from .command import course, resource, assignment, rollcall

KEYRING_SERVICE_NAME = "lazy"
KEYRING_STUDENTID_NAME = "studentid"
KEYRING_PASSWORD_NAME = "password"

logger = logging.getLogger(__name__)

# 初始化主app对象
app = typer.Typer(help="LAZY CLI - 学在浙大第三方客户端的命令行工具", no_args_is_help=True)

# --- 全局回调，检验登录状态 ---
@app.callback()
@partial(syncify, raise_sync_error=False)
async def main_callback(ctx: typer.Context):
    # 如果是login，whoami子命令，或查询--help时候，无需检查登录状态
    if ctx.invoked_subcommand in ["login", "whoami"] or "--help" in ctx.args:
        return

    async with ZjuAsyncClient() as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            task = progress.add_task(description="检查登录状态中...", total=2)
            # 如果会话存在且有效，则无需登录
            if client.load_session() and await client.is_valid_session():
                progress.update(task, description="登录有效", completed=2)
                return 

            logger.info("会话已失效，尝试使用凭据登录...")
            progress.advance(task)

            progress.update(task, description="会话失效！重新登录中...")
            
            studentid = keyring.get_password("lazy", "studentid")
            password = keyring.get_password("lazy", "password")

            if not studentid or not password:
                logger.error("未能找到登录凭据！")
                rprint("[red]未找到登录凭据，请重新登录[/red]")
                progress.advance(task)
                raise typer.Exit(code=1)
            
            if await client.login(studentid, password):
                client.save_session()
                progress.advance(task)
            else:
                rprint("[red]登录失败！[/red]请运行'login'命令尝试手动登录。")
                progress.advance(task)
                raise typer.Exit(code=1)

# --- 开发者检查测试 ---
@app.command()
@partial(syncify, raise_sync_error=False)
async def check(
    url: Annotated[str, typer.Argument()]
):
    """
    开发者网址测试检查工具，检验网页返回。
    """
    temp_client = ZjuAsyncClient()
    cookies = temp_client.load_cookies()

    client = ZjuAsyncClient(cookies=cookies)
    session = client.session

    try:
        response = await session.get(url)
        response.raise_for_status()
    except Exception as e:
        rprint(f"{e}")
    else:
        rprint(response.status_code)
        rprint(response.text)

# --- 手动登录 --- 
@app.command()
@partial(syncify, raise_sync_error=False)
async def login():
    """引导手动登录并自动更新登录凭据和本地会话。
    """    
    studentid = typer.prompt("请输入学号")
    password = typer.prompt("请输入密码", hide_input=True)

    client = ZjuAsyncClient()

    if await client.login(studentid, password):
        client.save_session()
        keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_STUDENTID_NAME, studentid)
        keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_PASSWORD_NAME, password)
        logger.info("已更新凭据与本地会话")
        print("登录成功，凭据和会话已更新")

    else:
        print("登录失败，请检查你的学号与密码是否正确。")
        raise typer.Exit(code=1)
    
# --- Who am I ? ---
@app.command()
def whoami():
    """
    Who am I ?
    """
    authorization_password = typer.prompt("请输入密码", hide_input=True)
    
    if authorization_password == keyring.get_password("lazy", "password"):
        rprint(f"{keyring.get_password("lazy", "studentid")}")
        return 
    
    rprint(f"[red]密码错误[/red]")

# --- 注册命令组 ---
# 课程命令组
app.add_typer(course.app, name="course", help="学在浙大课程相关命令，支持列举，搜索与查看课程章节等功能。")

# 资源命令组
app.add_typer(resource.app, name="resource", help="学在浙大云盘资源相关命令，可以查看，搜索，上传或下载云盘文件。")

# 任务命令组
app.add_typer(assignment.app, name="assignment", help="学在浙大作业任务相关命令，可以查看待完成的任务，提交作业等。")

# 签到命令组
app.add_typer(rollcall.app, name="rollcall", help="学在浙大签到相关任务，可以查看当前签到任务，完成指定的雷达签到任务。")