import logging
import sys
from functools import partial
from typing import Optional

import keyring
import typer
from asyncer import syncify
from lxml import etree
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn
from typing_extensions import Annotated

from .command import assignment, config, course, log, resource, rollcall
from .state import state

KEYRING_SERVICE_NAME = "lazy"
KEYRING_STUDENTID_NAME = "studentid"
KEYRING_PASSWORD_NAME = "password"
KEYRING_LAZ_STUDENTID_NAME = "laz_studentid"

logger = logging.getLogger(__name__)

# 初始化主app对象
app = typer.Typer(help="LAZY CLI - 学在浙大第三方客户端的命令行工具", no_args_is_help=True)

# --- 全局回调，检验登录状态 ---
@app.callback()
@partial(syncify, raise_sync_error=False)
async def main_callback(
    ctx: typer.Context,
    no_proxy: Annotated[Optional[bool], typer.Option(
        "--no-proxy",
        help="启用此选项，禁用 lazy 使用系统代理"
    )] = False
):

    # 如果是login，whoami子命令，或查询--help时候，无需检查登录状态
    if "--help" in sys.argv or "-h" in sys.argv:
        return 
    
    if ctx.invoked_subcommand in ["login", "whoami", "config"]:
        return

    state.trust_env = not no_proxy

    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(description="检查登录状态中...", total=2)
        
        # 如果会话存在且有效，则无需登录
        cookies = CredentialManager().load_cookies()
        async with ZjuAsyncClient(
            cookies=cookies,
            trust_env=state.trust_env
        ) as client:
            if cookies and await client.is_valid_session():
                progress.update(task, description="登录有效", completed=2)
                return 

            logger.info("会话已失效，尝试使用凭据登录...")
            progress.advance(task)

            progress.update(task, description="会话失效！重新登录中...")
            
            studentid = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_STUDENTID_NAME)
            password = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_PASSWORD_NAME)
            
            if not studentid or not password:
                logger.error("未能找到登录凭据！")
                rprint("[red]未找到登录凭据，请尝试手动登录！[/red]")
                progress.advance(task)
                raise typer.Exit(code=1)
            
            if await client.login(studentid, password):
                if CredentialManager().save_cookies(dict(client.session.cookies)):
                    progress.advance(task)
                else:
                    rprint("Cookies保存失败！")
                    logger.error("Cookies保存失败！")
                    raise typer.Exit(code=1)
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
    cookies = CredentialManager().load_cookies()
    async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as temp_client:
        try:
            response = await temp_client.session.get(url)
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

    if not password.isascii():
        rprint("[red]密码应仅包含英文、数字与半角标点符号！[/red]")
        raise typer.Exit(code=1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        async with ZjuAsyncClient(trust_env=state.trust_env) as client:
            task = progress.add_task(description="登录中...", total=1)

            if await client.login(studentid, password):
                if CredentialManager().save_cookies(dict(client.session.cookies)):
                    keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_STUDENTID_NAME, studentid)
                    keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_PASSWORD_NAME, password)
                    logger.info("已更新凭据与本地会话")
                    progress.advance(task)
                    rprint("[green]登录成功！[/green]")
                else:
                    rprint("Cookies保存失败！")
                    logger.error("Cookies保存失败！")
                    raise typer.Exit(code=1)
                
                # 更新学在浙大studentid
                response = await client.session.get(url="https://courses.zju.edu.cn/user/index")
                html = etree.HTML(response.text)
                laz_studentid = html.xpath(r'//span[@id="userId"]/@value')

                if not laz_studentid:
                    logger.error("学在浙大ID获取失败！")
                    rprint("[red]学在浙大ID获取失败，请将此问题上报给开发者！[/red]")
                    raise typer.Exit(code=1)
                
                keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_LAZ_STUDENTID_NAME, laz_studentid[0])
            else:
                rprint("登录失败，请检查你的学号与密码是否正确。")
                raise typer.Exit(code=1)
    
# --- Who am I ? ---
@app.command()
def whoami():
    """
    Who am I ?
    """
    authorization_password = typer.prompt("请输入密码", hide_input=True)
    
    if authorization_password == keyring.get_password("lazy", "password"):
        rprint(f"{keyring.get_password('lazy', 'studentid')}")
        return 
    
    rprint("[red]密码错误[/red]")

@app.command("whomai", hidden=True)
@app.command("lazy", hidden=True)
@app.command("hachimi", hidden=True)
def easter_egg(ctx: typer.Context):
    if ctx.command.name == "whomai":
        print("Who am I ???")

    if ctx.command.name == "lazy":
        print("not lazy, laz yes!")

    if ctx.command.name == "hachimi":
        print("哈基米哦南北绿豆~")

# --- 注册命令组 ---
# 课程命令组
app.add_typer(course.app, name="course", help="管理学在浙大课程信息与章节")

# 资源命令组
app.add_typer(resource.app, name="resource", help="管理学在浙大云盘资源")

# 任务命令组
app.add_typer(assignment.app, name="assignment", help="管理学在浙大活动任务")

# 签到命令组
app.add_typer(rollcall.app, name="rollcall", help="处理学在浙大签到任务")

# 配置命令组
app.add_typer(config.app, name="config", help="配置相关命令组")

# 日志命令组
app.add_typer(log.app, name="log", help="日志相关命令组")