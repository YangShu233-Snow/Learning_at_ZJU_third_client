import typer
from typing_extensions import Optional, Annotated, List
from rich import print as rprint
from rich.align import Align
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich.padding import Padding
from rich.console import Group
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from datetime import datetime, timezone
from pathlib import Path
from lxml import html
from lxml.html import HtmlElement

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

def make_jump_url(course_id: int, material_id: int, material_type: str)->str:
    if material_type == "material":
        return ""
    
    if material_type == "online_video" or material_type == "homework":
        return f"https://courses.zju.edu.cn/course/{course_id}/learning-activity/full-screen#/{material_id}"

    return f"https://courses.zju.edu.cn/course/{course_id}/learning-activity/full-screen#/{material_type}/{material_id}"

def transform_resource_size(resource_size: int)->str:
    resource_size_KB = resource_size / 1024
    resource_size_MB = resource_size_KB / 1024
    resource_size_GB = resource_size_MB / 1024

    if resource_size_GB >= 0.5:
        return f"{resource_size_GB:.2f}GB"
    
    if resource_size_MB >= 0.5:
        return f"{resource_size_MB:.2f}MB"
    
    if resource_size_KB >= 0.5:
        return f"{resource_size_KB:.2f}KB"
    
    return f"{resource_size:.2f}B"

def extract_comment(raw_content: str)->str:
    if not raw_content or not raw_content.strip():
        return ""
    
    doc: HtmlElement = html.fromstring(raw_content)
    plain_text = doc.text_content()

    return plain_text

def extract_uploads(uploads_list: List[dict])->List[Table]:
    content_renderables = []
    content_renderables.append("[cyan]附件: [/cyan]")

    for upload in uploads_list:
        file_name = upload.get("name", "null")
        file_id = upload.get("id", "null")
        file_size = transform_resource_size(upload.get("size", 0))

        upload_table = Table(show_header=False, box=None, padding=(0, 1), show_edge=False, expand=True)
        upload_table.add_column("Name", no_wrap=True)
        upload_table.add_column("Info", justify="right")

        upload_table.add_row(
            f"{file_name}",
            f"大小: {file_size} | 文件ID: {file_id}"
        )
        
        content_renderables.append(upload_table)

    return content_renderables

def view_exam(exam_id: int, type_map: dict):
    pass

def view_classroom(classroom_id: int, type_map: dict):
    pass

def view_activity(activity_id: int, type_map: dict):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        
        task = progress.add_task(description="请求数据中...", total=1)
        # --- 请求阶段 ---
        # 请求预览数据
        raw_activity_read: dict = zju_api.assignmentPreviewAPIFits(state.client.session, activity_id).post_api_data()[0]
        student_id = raw_activity_read.get("created_for_id")
        if not student_id:
            print_log("Error", f"{activity_id} 缺少'created_for_id'参数，请将此问题上报给开发者！", "CLI.command.assignment.view_assignment")
            print(f"{activity_id} 返回存在问题！")
            raise typer.Exit(code=1)

        # 请求主体数据
        raw_activity = zju_api.assignmentViewAPIFits(state.client.session, activity_id).get_api_data()[0]
        activity_completion_criterion_key: str = raw_activity.get("completion_criterion_key", "none")
        activity_highest_score: int = raw_activity.get("highest_score", 0) if raw_activity.get("highest_score", 0) is not None else "N/A"
        activity_description = extract_comment(raw_activity.get("data", {}).get("description", ""))
        activity_content = extract_comment(raw_activity.get("data", {}).get("content", ""))

        activity_description_text = Text.assemble(
            activity_description
        )
        activity_description_block = Padding(activity_description_text, (0, 0, 0, 2))

        # 判断是否获取提交列表（必须是提交完成的任务且有提交记录）
        if activity_completion_criterion_key == "submitted":
            if raw_activity.get("user_submit_count") and raw_activity.get("user_submit_count") > 0:
                raw_submission_list = zju_api.assignmentSubmissionListAPIFits(state.client.session, activity_id, student_id).get_api_data()[0]
            else:
                raw_submission_list = {}
        else:
            raw_submission_list = {}
        
        progress.advance(task, advance=1)

        task = progress.add_task(description="渲染内容中...", total=1)

        # 解析返回内容
        # 任务名称
        activity_title = raw_activity.get("title", "null")
        activity_type = type_map.get(raw_activity.get("type", "null"), raw_activity.get("type", "null"))

        # 开放时间
        activity_start_time = raw_activity.get("start_time", "1900-01-01T00:00:00Z")
        if activity_start_time:
            activity_start_time = datetime.fromisoformat(activity_start_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
        else:
            activity_start_time = "null"
        
        # 截止日期
        activity_end_time = raw_activity.get("end_time", "1900-01-01T00:00:00Z")
        if activity_end_time:
            activity_end_time = datetime.fromisoformat(activity_end_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
        else:
            activity_end_time = "null"

        start_time_text = Text.assemble(
            ("开放时间: ", "cyan"),
            (activity_start_time, "bright_white")
        )
        end_time_text = Text.assemble(
            ("截止时间: ", "cyan"),
            (activity_end_time, "bright_white")
        )

        # --- 准备Panel内容 ---
        content_renderables = []
        title_line = Align.center(Text.assemble((f"{activity_title}", "bold bright_magenta")))
        content_renderables.append(title_line)
        content_renderables.append(start_time_text)
        content_renderables.append(end_time_text)

        if activity_description_text:
            content_renderables.append("[cyan]任务描述: [/cyan]")
            content_renderables.append(activity_description_block)
            content_renderables.append("")
            
        if activity_content:
            content_renderables.append("")
            content_renderables.append(activity_content)

        # 读取附件（如果有的话）
        uploads: List[dict] = raw_activity.get("uploads")
        if uploads:
            content_renderables.append("")
            content_renderables.extend(extract_uploads(uploads))

        # 读取提交列表（如果有的话）
        if raw_submission_list:
            
            # 准备Submission的Panel内容
            submission_content_renderables = []
            submission_list: List[dict] = raw_submission_list.get("list")
            
            for submission in submission_list:
                submission_created_time = datetime.fromisoformat(submission.get("created_at", "1900-01-01T00:00:00Z").replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                submission_comment = extract_comment(submission.get("comment"))
                submission_instructor_comment: str = submission.get("instructor_comment") or ""
                submission_score: int|None = submission.get("score") if submission.get("score") is not None else "未评分"
                submission_uploads: List[dict]|list = submission.get("uploads", [])

                # --- 准备Panel内容 --- 
                submission_inner_comment = Text.assemble(
                    submission_comment
                )
                submission_inner_comment_block = Padding(submission_inner_comment, (0, 0, 0, 2))

                submission_inner_instructor_comment = Text.assemble(
                    submission_instructor_comment
                )
                submission_inner_instructor_comment_block = Padding(submission_inner_instructor_comment, (0, 0, 0, 2))

                submission_head_text = Text.assemble(
                    ("提交时间: ", "cyan"),
                    submission_created_time,
                    "\n",
                    (f"得分: ", "bold bright_magenta"),
                    (f"{submission_score} / {activity_highest_score}")
                )

                submission_content_renderables.append(submission_head_text)
                
                if submission_inner_instructor_comment:
                    submission_content_renderables.append("")
                    submission_content_renderables.append("[cyan]老师评语: [/cyan]")
                    submission_content_renderables.append(submission_inner_instructor_comment_block)
                
                if submission_inner_comment:
                    submission_content_renderables.append("")
                    submission_content_renderables.append("[cyan]提交内容: [/cyan]")
                    submission_content_renderables.append(submission_inner_comment_block)
                
                # 读取上传列表（如果有的话）
                if submission_uploads:
                    submission_upload_content_renderables = extract_uploads(submission_uploads)
                    submission_content_renderables.append("")
                    submission_content_renderables.extend(submission_upload_content_renderables)
                    submission_content_renderables.append("")
                
                if submission != submission_list[-1]:
                    submission_content_renderables.append(Rule(style="dim white"))
                    submission_content_renderables.append("")

            # --- 装配Submission List Panel ---
            submission_list_panel = Panel(
                Group(*submission_content_renderables),
                title = "[white][提交内容][/white]",
                border_style="dim",
                expand=True,
                padding=(1, 2)
            )
            content_renderables.append("")
            content_renderables.append(submission_list_panel)
        
        if activity_completion_criterion_key == "submitted" and not raw_submission_list:
            content_renderables.append("")
            content_renderables.append("无提交记录")

        activity_panel = Panel(
            Group(*content_renderables),
            title = f"[white][{activity_type}][/white]",
            subtitle = f"[white][ID: {activity_id}][/white]",
            border_style="bright_black",
            expand=True,
            padding=(0, 2, 1, 2)
        )
        
        progress.advance(task, advance=1)

    rprint(activity_panel)

@app.command("view")
def view_assignment(
    assignment_id: Annotated[int, typer.Argument(help="任务id")],
    exam: Annotated[Optional[bool], typer.Option("--exam", "-e", help="启用此选项，将查询对应的考试")],
    classroom: Annotated[Optional[bool], typer.Option("--classroom", "-c", help="启用此选项，将查询对应课堂任务")]
):
    """
    浏览指定任务，显示任务基本信息，任务附件与任务提交记录
    """
    type_map = {
        "material": "资料",
        "online_video": "视频",
        "homework": "作业",
        "questionnaire": "问卷",
        "exam": "测试",
        "page": "页面",
        "classroom": "课堂任务"
    }

    if exam:
        view_exam(assignment_id, type_map)
        return 
    
    if classroom:
        view_classroom(assignment_id, type_map)
        return

    view_activity(assignment_id, type_map)
    return 


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

@app.command("submit")
def submit_assignment():
    pass