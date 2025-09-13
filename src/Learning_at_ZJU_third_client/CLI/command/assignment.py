import typer
from typing_extensions import Optional, Annotated, List
from rich import print as rprint
from rich.text import Text
from rich.panel import Panel
from rich.console import Group
from rich.progress import Progress, SpinnerColumn, TextColumn
from datetime import datetime, timezone
from pathlib import Path

from zjuAPI import zju_api
from upload import submit
from load_config import load_config
from printlog.print_log import print_log
from ..state import state

# assignment 命令组
app = typer.Typer(help="""
                  学在浙大作业任务相关命令，可以查看待完成的任务，提交作业等。

                  暂时不支持对测试与考试的提交。
                  """)

def is_todo_show_amount_valid(amount: int):
    if amount <= 0:
        print("显示数量应为正数！")
        raise typer.Exit(code=1)
    
    return amount

def make_jump_url(course_id: int, material_id: int, material_type: str):
    if material_type == "material":
        return ""
    
    if material_type == "online_video" or material_type == "homework":
        return f"https://courses.zju.edu.cn/course/{course_id}/learning-activity/full-screen#/{material_id}"

    return f"https://courses.zju.edu.cn/course/{course_id}/learning-activity/full-screen#/{material_type}/{material_id}"

@app.command("view")
def view_assignment(
    activity_id: Annotated[int, typer.Argument(help="任务id")]
):
    pass

@app.command("todo")
def todo_assignment(
    amount: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示待办任务数量", callback=is_todo_show_amount_valid)] = 5,
    page_index: Annotated[Optional[int], typer.Option("--page", "-p", help="待办任务页面索引")] = 1,
    reverse: Annotated[Optional[bool], typer.Option("--reverse", "-r", help="以任务截止时间降序排列")] = False
):
    """
    列举待办事项清单，默认以任务截止时间作为排序依据，越早截止，排序越靠前。

    并不建议将显示数量指定太大，大量输出会淹没你的显示窗口。实际上你可以通过 "--page" 参数实现翻页。
    """
    type_map = {
        "material": "资料",
        "online_video": "视频",
        "homework": "作业",
        "questionnaire": "问卷",
        "exam": "测试"
    }
    todo_panel_list = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        
        task = progress.add_task(description="获取待办事项信息中...", total=1)
        
        raw_todo_list: dict = zju_api.assignmentTodoListAPIFits(state.client.session).get_api_data()[0]

        progress.advance(task, advance=1)

        task = progress.add_task(description="加载内容中...", total=1)

        todo_list: List[dict] = raw_todo_list.get("todo_list", [])
        
        if type(todo_list) != list:
            print_log("Error", f"todo_list存在错误，请将此日志上报给开发者！", "CLI.command.assignment.todo_assignment")
            print("待办事项清单解析存在异常！")
            raise typer.Exit(code=1)
        
        # 总任务数量
        total = len(todo_list)

        if total == 0:
            print("当前没有待办任务哦~")
            return 
        
        total_pages = int(total / amount) + 1
        if page_index > total_pages:
            print(f"页面索引超限！共 {total} 页，你都索引到第 {page_index} 页啦！")
            raise typer.Exit(code=1)

        # 依照截止时间排序
        todo_list = sorted(todo_list, key=lambda todo: datetime.fromisoformat(todo.get("end_time", "1900-01-01T00:00:00Z").replace('Z', '+00:00')), reverse=reverse)

        start = amount * (page_index - 1)
        todo_list = todo_list[start:]

        for index, todo in enumerate(todo_list):
            if index > amount - 1:
                amount = index
                break

            title = todo.get("title", "null")
            course_name = todo.get("course_name", "null")
            course_id = todo.get("course_id", "null")
            todo_id = todo.get("id", "null")
            end_time = datetime.fromisoformat(todo.get("end_time", "1900-01-01T00:00:00Z").replace('Z', '+00:00'))
            todo_type = type_map.get(todo.get("type", "null"), todo.get("type", "null"))

            # 创建标题内容
            title_text = Text.assemble(
                (title, "bold bright_magenta"),
                "\n",
                (f"{course_name} {course_id}", "dim")
            )

            # 创建时间描述文本
            time_to_ddl = end_time - datetime.now(timezone.utc)
            if time_to_ddl.days < 1:
                remaining_time_text = f" ({time_to_ddl.seconds // 3600} 小时 {time_to_ddl.seconds % 3600 // 60} 分钟)"
                style = "red"
            elif time_to_ddl.days < 3:
                remaining_time_text = f" ({time_to_ddl.days} 天 {time_to_ddl.seconds // 3600} 小时)"
                style = "yellow"
            elif time_to_ddl.days < 7:
                remaining_time_text = f" ({time_to_ddl.days} 天 {time_to_ddl.seconds // 3600} 小时)"
                style = "blue"
            else:
                remaining_time_text = f" ({time_to_ddl.days} 天)"
                style = "green"

            end_time_text = Text.assemble(
                ("截止时间: ", "cyan"),
                (end_time.strftime("%Y-%m-%d %H:%M:%S"), "bright_white"),
                (remaining_time_text, style)
            )

            # 构建跳转链接文本
            url_jump = make_jump_url(course_id, todo_id, todo.get("type", "null"))
            url_jump_text = Text.assemble(
                ("跳转链接: ", "cyan"),
                (url_jump, "bright_white")
            )

            # 组装panel
            content_renderables = []
            content_renderables.append(title_text)
            content_renderables.append(end_time_text)
            content_renderables.append(url_jump_text)

            panel_title = f"[white][{todo_type}][/white]"
            panel_sub_title = f"[white][ID: {todo_id}][/white]"

            todo_panel = Panel(
                Group(*content_renderables),
                title=panel_title,
                subtitle=panel_sub_title,
                border_style="bright_black",
                expand=True,
                padding=(1, 2)
            )

            todo_panel_list.append(todo_panel)
        else:
            amount = index + 1

        progress.advance(task, advance=1)

    rprint(*todo_panel_list)

    print(f"本页共 {amount} 个结果，第 {page_index}/{total_pages} 页")