import typer
import keyring
from typing_extensions import Annotated, Optional
from login.login import ZjuClient
from printlog.print_log import print_log

from .state import state
from .command import course, resource, assignment, exam

KEYRING_SERVICE_NAME = "lazy"
KEYRING_STUDENTID_NAME = "studentid"
KEYRING_PASSWORD_NAME = "password"

# 初始化主app对象
app = typer.Typer(help="LAZY CLI - 学在浙大第三方客户端的命令行工具")

# --- 全局回调，检验登录状态 ---
@app.callback()
def main_callback(ctx: typer.Context):
    # 如果使用的是login命令，则无需检查登录状态
    if ctx.invoked_subcommand == "login":
        return 
    
    client = ZjuClient()

    # 如果会话存在且有效，则无需登录
    if client.load_session() and client.is_valid_session():
        state.client = client
        return 

    print_log("Info", "会话已失效，尝试使用凭据登录...", "CLI.CLI_Typer.main_callback")
    studentid = keyring.get_password("lazy", "studentid")
    password = keyring.get_password("lazy", "password")

    if not studentid or not password:
        print_log("Error", "未能找到登录凭据！", "CLI.CLI_Typer.main_callback")
        print("未找到登录凭据，请重新登录")
        raise typer.Exit(code=1)
    
    if client.login(studentid, password):
        client.save_session()
        state.client = client
    else:
        print("登录失败！请运行'login'命令尝试手动登录。")
        raise typer.Exit(code=1)

# --- 手动登录 --- 
@app.command()
def login():
    """引导手动登录并自动更新登录凭据和本地会话
    """    
    studentid = typer.prompt("请输入学号")
    password = typer.prompt("请输入密码", hide_input=True)

    client = ZjuClient()

    if client.login(studentid, password):
        client.save_session()
        keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_STUDENTID_NAME, studentid)
        keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_PASSWORD_NAME, password)
        print_log("Info", "已更新凭据与本地会话", "CLI.CLI_Typer.login")
        print("登录成功，凭据和会话已更新")

    else:
        print("登录失败，请检查你的学号与密码是否正确。")
        raise typer.Exit(code=1)
    
# --- 注册命令组 ---
# 课程命令组
app.add_typer(course.app, name="course", help="学在浙大课程相关命令，支持列举，搜索与查看课程章节等功能。")

# 资源命令组
app.add_typer(resource.app, name="resource", help="学在浙大云盘资源相关命令，可以查看，搜索，上传或下载云盘文件。")

# 任务命令组
app.add_typer(assignment.app, name="assignment", help="学在浙大作业任务相关命令，可以查看待完成的任务，提交作业等。")

# 测试命令组
app.add_typer(exam.app, name="exam", help="学在浙大测试相关命令，可以查看测试的基本信息。")