from asyncer import syncify
import asyncio
from functools import partial
import typer
from typing_extensions import Optional, Annotated, List, Tuple
from rich import filesize
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

from ...zjuAPI import zju_api
from ...upload import submit
from ...load_config import load_config
from ...printlog.print_log import print_log
from ...login.login import ZjuAsyncClient

# assignment 命令组
app = typer.Typer(help="""
                  学在浙大作业任务相关命令，可以查看待完成的任务，提交作业等。

                  暂时不支持对测试与考试的提交。
                  """,
                  no_args_is_help=True
                  )

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

def transform_time(time: str|None)->str:
    if time:
        time_local = datetime.fromisoformat(time.replace('Z', '+00:00')).astimezone()
        return time_local.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return "null"

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
        file_size = filesize.decimal(upload.get("size", 0))

        upload_table = Table(show_header=False, box=None, padding=(0, 1), show_edge=False, expand=True)
        upload_table.add_column("Name", no_wrap=True)
        upload_table.add_column("Info", justify="right")

        upload_table.add_row(
            f"{file_name}",
            f"大小: {file_size} | 文件ID: {file_id}"
        )
        
        content_renderables.append(upload_table)

    return content_renderables

def get_status_text(start_status: bool, close_status: bool)->Text:
    if close_status:
        return Text(f"🔴 已结束", style="red")
    
    if start_status:
        return Text(f"🟢 进行中", style="green")
    
    return Text(f"⚪️ 未开始", style="dim")

def parse_files_id(files_id: str)->List[int]:
    if not files_id:
        return []

    if ',' in files_id:
        files_id = files_id.replace(',', ' ')

    try:
        if ' ' in files_id:
            files_id_list = list(map(int, files_id.split(' ')))
        else:
            files_id_list = [int(files_id)]
    except ValueError as e:
        typer.echo(f"文件ID格式有误！", err=True)
        raise typer.Exit(code=1)
    
    return list(set(files_id_list))

async def guess_assignment_type(assignment_id: int)->Tuple[bool, bool, bool]:
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        cookies = ZjuAsyncClient().load_cookies()
        task = progress.add_task(description="正在猜测任务类型...",total=1)

        async with ZjuAsyncClient(cookies=cookies) as client:
            raw_activity, raw_exam, raw_classroom = await asyncio.gather(*[
                zju_api.assignmentPreviewAPIFits(client.session, assignment_id).post_api_data(),
                zju_api.assignmentExamViewAPIFits(client.session, assignment_id, apis_name=["exam"]).get_api_data(),
                zju_api.assignmentClassroomViewAPIFits(client.session, assignment_id, apis_name=["classroom"]).get_api_data()
            ], return_exceptions=True)

        if isinstance(raw_activity, list) and raw_activity and raw_activity[0].get("data"):
            progress.update(task, description="猜测是作业!", completed=1)
            return (True, False, False)
        
        
        if isinstance(raw_exam, list) and raw_exam and raw_exam[0]:
            progress.update(task, description="猜测是测试!", completed=1)
            return (False, True, False)
        
        
        if isinstance(raw_classroom, list) and raw_classroom and raw_classroom[0]:
            progress.update(task, description="猜测是课堂任务!", completed=1)
            return (False, False, True)
    
    return (False, False, False)

async def view_exam(exam_id: int, type_map: dict):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(description="请求数据中...", total=2)
        cookies = ZjuAsyncClient().load_cookies()

        async with ZjuAsyncClient(cookies=cookies) as client:
            # --- 请求阶段 ---
            raw_exam, raw_exam_submission_list, raw_exam_subjects_summary = await zju_api.assignmentExamViewAPIFits(client.session, exam_id).get_api_data()
        
        if not raw_exam:
            rprint(f"[red]请求测试 [green]{exam_id}[/green] 不存在！[/red]")
            raise typer.Exit(code=1)

        progress.advance(task, 1)
        progress.update(task, description="渲染数据中...")

        # 解析返回内容
        # 主体内容
        exam_title: str = raw_exam.get("title", "null")
        exam_total_points: int|str = raw_exam.get("total_points", "null")
        exam_type: str = type_map.get(raw_exam.get("type", "null"), raw_exam.get("type", "null"))
        exam_start_status: bool = raw_exam.get("is_started", False)
        exam_close_status: bool = raw_exam.get("is_closed")
        exam_description = extract_comment(raw_exam.get("description"))
        exam_submit_times_limit: int|str = raw_exam.get("submit_times", "N/A")
        exam_submitted_times: int = raw_exam.get("submitted_times", 0)

        # 开放时间
        exam_start_time: str = transform_time(raw_exam.get("start_time"))

        # 结束时间
        exam_end_time: str = transform_time(raw_exam.get("end_time"))

        # 组装文本
        title_line = Align.center(
            Text.assemble(
                (f"{exam_title}", "bold bright_magenta")
            )
        )

        exam_status_text = get_status_text(exam_start_status, exam_close_status)

        start_time_text = Text.assemble(
            ("开放时间: ", "cyan"),
            (exam_start_time, "bright_white")
        )
        end_time_text = Text.assemble(
            ("截止时间: ", "cyan"),
            (exam_end_time, "bright_white")
        )

        submitted_text = Text.assemble(
            ("提交次数: ", "cyan"),
            (f"{exam_submitted_times} / {exam_submit_times_limit}", "bright_white")
        )

        exam_description_text = Text.assemble(
            (f"{exam_description}", "bright_white")
        )

        exam_description_block = Padding(
            exam_description_text, (0, 0, 0, 2)
        )

        # --- 准备Panel内容 ---
        content_renderables = []
        content_renderables.append(title_line)
        content_renderables.append(exam_status_text)
        content_renderables.append(start_time_text)
        content_renderables.append(end_time_text)
        content_renderables.append(submitted_text)

        if exam_description_text:
            content_renderables.append("[cyan]任务描述: [/cyan]")
            content_renderables.append(exam_description_block)
            content_renderables.append("")

        if raw_exam_submission_list:
            exam_final_score: int|None = raw_exam_submission_list.get("exam_final_score")
            if not exam_final_score:
                exam_final_score: int|str = raw_exam_submission_list.get("exam_score") if raw_exam_submission_list.get("exam_score") else "null"
            
            submission_content_renderables = []
            exam_submission_list: List[dict] = raw_exam_submission_list.get("submissions")
            
            for submission in exam_submission_list:
                submission_submitted_time = submission.get("submitted_at")
                submission_score = submission.get("score") if submission.get("score") else "未公布"

                if submission_submitted_time:
                    submission_submitted_time = datetime.fromisoformat(exam_end_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    submission_submitted_time = "null"

                # --- 准备Panel内容 ---
                submission_head_text = Text.assemble(
                    (f"提交时间: ", "cyan"),
                    (f"{submission_submitted_time}", "bright_white"),
                    "\n",
                    (f"测试得分: ", "bright_magenta"),
                    (f"{submission_score} / {exam_total_points}", "bright_white")
                )

                submission_content_renderables.append(submission_head_text)

                if submission != exam_submission_list[-1]:
                    submission_content_renderables.append(Rule(style="dim white"))
                    submission_content_renderables.append("")

            # --- 组装 Exam Submission List Panel ---
            exam_submission_list_panel = Panel(
                Group(*submission_content_renderables),
                title = "[yellow][交卷记录][/yellow]",
                border_style="yellow",
                expand=True,
                padding=(1, 2)
            )

            content_renderables.append("")
            content_renderables.append(exam_submission_list_panel)
        else:
            content_renderables.append("")
            content_renderables.append("无提交记录")

        # --- 组装 Exam Panel ---
        exam_panel = Panel(
            Group(*content_renderables),
            title=f"[white][{exam_type}][/white]",
            subtitle=f"[white][ID: {exam_id}][/white]",
            border_style="bright_black",
            expand=True,
            padding=(1, 2)
        )

        progress.update(task, description="渲染完成...")
        progress.advance(task, 1)

        rprint(exam_panel)

async def view_classroom(classroom_id: int, type_map: dict):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(description="请求数据中...", total=2)

        cookies = ZjuAsyncClient().load_cookies()

        async with ZjuAsyncClient(cookies=cookies) as client:
            # --- 请求阶段 ---
            # 请求classroom与classroom submission数据
            classroom_message, raw_classroom_submissions_list = await zju_api.assignmentClassroomViewAPIFits(client.session, classroom_id).get_api_data()

            if not classroom_message:
                rprint(f"[red]请求课堂测试 [green]{classroom_id}[/green] 不存在！[/red]")
                raise typer.Exit(code=1)
            
            if classroom_message.get("subjects_count") > 0:
                classroom_submissions_list: List[dict] = raw_classroom_submissions_list.get("submissions", [])
            else: 
                classroom_submissions_list = []
        
        progress.advance(task, 1)
        progress.update(task, description="渲染数据中...")

        # --- 渲染阶段 ---
        classroom_title: str = classroom_message.get("title") if classroom_message.get("title") else "null"
        classroom_type: str = type_map.get(classroom_message.get("type"), classroom_message.get("type"))
        
        classroom_start_time = transform_time(classroom_message.get("start_at"))
        classroom_finish_time = transform_time(classroom_message.get("finish_at"))

        classroom_start_time_text = Text.assemble(
            ("开始时间: ", "cyan"),
            (f"{classroom_start_time}", "bright_white")
        )

        if classroom_finish_time == "null":
            classroom_finish_time_text = None
        else:
            classroom_finish_time_text = Text.assemble(
                ("截止时间: ", "cyan"),
                (f"{classroom_finish_time}", "bright_white")
            )

        # --- 准备Panle内容 ---
        content_renderables = []
        title_line = Align.center(f"{classroom_title}", "bold bright_magenta")
        content_renderables.append(title_line)
        content_renderables.append(classroom_start_time_text)
        
        if classroom_finish_time_text:
            content_renderables.append(classroom_finish_time_text)

        if classroom_submissions_list:
            submissions_content_renderables = []
            for submission in classroom_submissions_list:
                submission_created_time = transform_time(submission.get("created_at"))
                submission_score: int|str = submission.get("quiz_score") if submission.get("quiz_score") else "null"

                submission_text = Text.assemble(
                    ("提交时间: ", "cyan"),
                    (f"{submission_created_time}", "bright_white"),
                    "\n",
                    ("最终得分: ", "cyan"),
                    (f"{submission_score}", "bright_white")
                )

                submissions_content_renderables.append(submission_text)

                if submission != classroom_submissions_list[-1]:
                    submissions_content_renderables.append(Rule(style="dim white"))
                    submissions_content_renderables.append("")

            classroom_submissions_panel = Panel(
                Group(*submissions_content_renderables),
                title = "[yellow][提交记录][/yellow]",
                border_style="yellow",
                expand=True,
                padding=(1, 2)
            )

            content_renderables.append(classroom_submissions_panel)

        classroom_panel = Panel(
            Group(*content_renderables),
            title = f"[white][{classroom_type}][/white]",
            border_style="dim",
            expand=True,
            padding=(1, 2)
        )

        progress.advance(task, 1)
        progress.update(task, description="渲染完成")

        rprint(classroom_panel)

async def view_activity(activity_id: int, type_map: dict):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        
        task = progress.add_task(description="请求数据中...", total=1)

        cookies = ZjuAsyncClient().load_cookies()

        async with ZjuAsyncClient(cookies=cookies) as client:
            # --- 请求阶段 ---
            # 请求预览数据
            raw_activity_read: dict = (await zju_api.assignmentPreviewAPIFits(client.session, activity_id).post_api_data())[0]

            if not raw_activity_read:
                rprint(f"[red]请求作业 [green]{activity_id}[/green] 不存在！[/red]")
                raise typer.Exit(code=1)

            if not raw_activity_read.get("data"):
                rprint(f"[red]请求作业 [green]{activity_id}[/green] 不存在！[/red]")
                raise typer.Exit(code=1)
            
            student_id = raw_activity_read.get("created_for_id")
            if not student_id:
                print_log("Error", f"{activity_id} 缺少'created_for_id'参数，请将此问题上报给开发者！", "CLI.command.assignment.view_assignment")
                print(f"{activity_id} 返回存在问题！")
                raise typer.Exit(code=1)

            # 请求主体数据
            raw_activity = (await zju_api.assignmentViewAPIFits(client.session, activity_id).get_api_data())[0]
        
        activity_completion_criterion_key: str       = raw_activity.get("completion_criterion_key", "none")
        activity_highest_score: int                  = raw_activity.get("highest_score", 0) if raw_activity.get("highest_score", 0) is not None else "N/A"
        activity_description: str                    = extract_comment(raw_activity.get("data", {}).get("description", ""))
        activity_content: str                        = extract_comment(raw_activity.get("data", {}).get("content", ""))
        activity_all_students_average_score: int|str = raw_activity.get("average_score", "N/A")

        activity_description_text = Text.assemble(
            activity_description
        )
        activity_description_block = Padding(activity_description_text, (0, 0, 0, 2))

        # 判断是否获取提交列表（必须是提交完成的任务且有提交记录）
        if activity_completion_criterion_key == "submitted":
            if raw_activity.get("user_submit_count") and raw_activity.get("user_submit_count") > 0:
                raw_submission_list = (await zju_api.assignmentSubmissionListAPIFits(client.session, activity_id, student_id).get_api_data())[0]
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
        activity_start_time = transform_time(raw_activity.get("start_time"))
        
        # 截止日期
        activity_end_time = transform_time(raw_activity.get("end_time"))

        start_time_text = Text.assemble(
            ("开放时间: ", "cyan"),
            (activity_start_time, "bright_white")
        )
        end_time_text = Text.assemble(
            ("截止时间: ", "cyan"),
            (activity_end_time, "bright_white")
        )

        if type(activity_all_students_average_score) == float:
            average_score_text = Text.assemble(
                ("班级均分: ", "cyan"),
                (f"{activity_all_students_average_score:0.2f}", "bright_white")
            )
        else:
            average_score_text = Text.assemble(
                ("班级均分: ", "cyan"),
                (f"{activity_all_students_average_score}", "bright_white")
            )

        # --- 准备Panel内容 ---
        content_renderables = []
        title_line = Align.center(Text.assemble((f"{activity_title}", "bold bright_magenta")))
        content_renderables.append(title_line)
        content_renderables.append(start_time_text)
        content_renderables.append(end_time_text)
        content_renderables.append(average_score_text)

        if activity_description_text:
            content_renderables.append("[cyan]任务描述: [/cyan]")
            content_renderables.append(activity_description_block)
            content_renderables.append("")
            
        if activity_content:
            if content_renderables[-1] != "":
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
                submission_score: int|None = submission.get("score") if submission.get("score") else "未评分"
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
                title = "[yellow][提交记录][/yellow]",
                border_style="yellow",
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
            padding=(1, 2, 1, 2)
        )
        
        progress.advance(task, advance=1)

    rprint(activity_panel)

@app.command("view")
@partial(syncify, raise_sync_error=False)
async def view_assignment(
    assignment_id: Annotated[int, typer.Argument(help="任务id")],
    exam: Annotated[Optional[bool], typer.Option("--exam", "-e", help="启用此选项，将查询对应的考试")] = False,
    classroom: Annotated[Optional[bool], typer.Option("--classroom", "-c", help="启用此选项，将查询对应课堂任务")] = False,
    homework: Annotated[Optional[bool], typer.Option("--homework", "-H", help="启用此选项，将查询对应作业")] = False
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
    # 猜测任务类型
    if not (homework or exam or classroom):
        homework, exam, classroom = await guess_assignment_type(assignment_id)

    # 按照指定分配至相应任务
    if homework:
        await view_activity(assignment_id, type_map)
        return 

    if exam:
        await view_exam(assignment_id, type_map)
        return 
    
    if classroom:
        await view_classroom(assignment_id, type_map)
        return
    
    rprint(f"任务 {assignment_id} 不存在！")
    return 


@app.command("todo")
@partial(syncify, raise_sync_error=False)
async def todo_assignment(
    amount: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示待办任务数量", callback=is_todo_show_amount_valid)] = 5,
    page_index: Annotated[Optional[int], typer.Option("--page", "-p", help="待办任务页面索引")] = 1,
    reverse: Annotated[Optional[bool], typer.Option("--reverse", "-r", help="以任务截止时间降序排列")] = False,
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此选项，输出所有待办事项")] = False
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
        
        cookies = ZjuAsyncClient().load_cookies()

        async with ZjuAsyncClient(cookies=cookies) as client:
            raw_todo_list: dict = zju_api.assignmentTodoListAPIFits(client.session).get_api_data()[0]
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
        
        if not all:
            total_pages = int(total / amount) + 1
            if page_index > total_pages:
                print(f"页面索引超限！共 {total} 页，你都索引到第 {page_index} 页啦！")
                raise typer.Exit(code=1)
        else:
            amount = total
            page_index = 1

        # 依照截止时间排序
        todo_list = sorted(todo_list, key=lambda todo: datetime.fromisoformat(todo.get("end_time").replace('Z', '+00:00') if todo.get("end_time") else "3000-01-01T00:00:00+00:00"), reverse=reverse)

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
            end_time = datetime.fromisoformat(todo.get("end_time").replace('Z', '+00:00')) if todo.get("end_time") else None
            todo_type = type_map.get(todo.get("type", "null"), todo.get("type", "null"))

            # 创建标题内容
            title_text = Text.assemble(
                (title, "bold bright_magenta"),
                (" [ID: ", "bright_white"),
                (f"{todo_id}", "green"),
                (f"]", "bright_white"),
                "\n",
                (f"{course_name} {course_id}", "dim")
            )

            # 创建时间描述文本
            if end_time:
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
            else:
                remaining_time_text = "无截止日期"
                style = "dim"
                total_pages = 1

            if end_time:
                local_end_time = end_time.astimezone()

                end_time_text = Text.assemble(
                    ("截止时间: ", "cyan"),
                    (local_end_time.strftime("%Y-%m-%d %H:%M:%S"), "bright_white"),
                    (remaining_time_text, style)
                )
            else: 
                end_time_text = Text.assemble(
                    ("截止时间: ", "cyan"),
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
            
            if style != "dim":
                panel_border_style = "bright_" + style
            else:
                panel_border_style = "dim"

            todo_panel = Panel(
                Group(*content_renderables),
                title=panel_title,
                border_style=panel_border_style,
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
@partial(syncify, raise_sync_error=False)
async def submit_assignment(
    activity_id: Annotated[int, typer.Argument(help="待提交任务ID")],
    text: Annotated[Optional[str], typer.Option("--text", "-t", help="待提交的文本内容")] = "",
    files_id: Annotated[Optional[str], typer.Option("--files", "-f", help="待上传附件ID", callback=parse_files_id)] = ""
):
    cookies = ZjuAsyncClient().load_cookies()

    async with ZjuAsyncClient(cookies=cookies) as client:
        if submit.submitAssignment(activity_id, text, files_id).submit(client.session):
            rprint(f"[green]提交成功！[/green]")
        else:
            rprint(f"[red]提交失败！[/red]")