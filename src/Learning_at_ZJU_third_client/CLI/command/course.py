import asyncio
import httpx
import typer
import logging
from asyncer import syncify
from functools import partial
from typing_extensions import Optional, Annotated, List, Tuple
from rich import filesize
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.tree import Tree
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.console import Group
from datetime import datetime

from ...zjuAPI import zju_api
from ...login.login import ZjuAsyncClient
# course 命令组
app = typer.Typer(help="""
                        学在浙大课程相关命令组，提供了对课程的查询与对课程章节查看的功能。
                       """,
                    no_args_is_help=True
                  )

logger = logging.getLogger(__name__)

# view 子命令组
view_app = typer.Typer(help="学在浙大课程查看相关命令组，支持对课程多维信息的查看。", no_args_is_help=True)

def transform_time(time: str|None)->str:
    if time:
        time_local = datetime.fromisoformat(time.replace('Z', '+00:00')).astimezone()
        return time_local.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return "null"

def get_status_text(start_status: bool, close_status: bool)->Text:
    if close_status:
        return Text(f"🔴 已结束", style="red")
    
    if start_status:
        return Text(f"🟢 进行中", style="green")
    
    return Text(f"⚪️ 未开始", style="dim")

def get_completion_text(completion_status: bool, completion_criterion_key: str)->Text:
    if completion_criterion_key == "none":
        return Text(f"无完成指标", style="dim")
    
    if completion_status:
        return Text(f"🟢 已完成", style="green")
    
    return Text(f"🔴 未完成", style="red")

def get_classroom_status_text(status: str)->Text:
    if status == "finish":
        return Text(f"🔴 已结束", style="red")
    
    if status == "start":
        return Text(f"🟢 进行中", style="green")
    
    return Text(f"⚪️ 未开始", style="dim")

def get_classroom_completion_text(completion_key: str)->Text:
    if completion_key == "full":
        return Text(f"🟢 已完成", style="green")
    
    return Text(f"🔴 未完成", style="red")

def make_jump_url(course_id: int, material_id: int, material_type: str):
    if material_type == "material":
        return ""
    
    if material_type == "online_video" or material_type == "homework":
        return f"https://courses.zju.edu.cn/course/{course_id}/learning-activity/full-screen#/{material_id}"

    return f"https://courses.zju.edu.cn/course/{course_id}/learning-activity/full-screen#/{material_type}/{material_id}"

def parse_indices(indices: str|None)->List[int]:
    if not indices:
        return []
    
    if ',' in indices:
        indices = indices.split(',')
    else:
        indices = [indices]

    result = []
    for item in indices:
        if '-' in item:
            try:
                start, end = map(int, item.split('-'))
                if start >= end:
                    raise ValueError("范围起始值不应大于结束值！")
                
                if start <= 0:
                    raise ValueError("索引范围应大于等于0！")

                result.extend(range(start-1, end))
            except ValueError as e:
                logger.error(f"{item} 格式有误，错误信息: {e}")
                typer.echo(f"{item} 格式错误，请使用 'start_index - end_index' 的格式！", err=True)
                raise typer.Exit(code=1)
        else:
            try:
                result.append(int(item)-1)
            except ValueError as e:
                logger.error(f"{item} 格式有误，错误信息: {e}")
                typer.echo(f"{item} 应为整数！", err=True)
                raise typer.Exit(code=1)
    
    # 去重，排序
    return sorted(list(set(result)))

def extract_modules(modules: List[dict], indices: List[int], modules_id: List[int], last: bool)->List[Tuple[int, dict]]:
    result = []
    
    safe_indices = indices if indices is not None else []
    safe_modules_id = modules_id if modules_id is not None else []

    for index, module in enumerate(modules):
        if index in safe_indices or module.get("id") in safe_modules_id:
            result.append((module.get("id"), module))

    if last:
        if modules[-1] not in result:
            result.append((modules[-1].get("id"), modules[-1]))

    return result

# 注册课程列举命令
@app.command("list")
@partial(syncify, raise_sync_error=False)
async def list_courses(
    keyword: Annotated[Optional[str], typer.Option("--name", "-n", help="课程搜索关键字")] = None,
    amount: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示课程的数量")] = 10,
    page_index: Annotated[Optional[int], typer.Option("--page", "-p", help="课程页面索引")] = 1,
    short: Annotated[Optional[bool], typer.Option("--short", "-s", help="简化输出内容，仅显示课程名与课程id")] = False,
    quiet: Annotated[Optional[bool], typer.Option("--quiet", "-q", help="仅输出课程id")] = False,
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此参数，一次性输出所有结果")] = False
    ):
    """
    列举学在浙大内的课程信息，允许指定课程名称，显示数量。

    并不建议将显示数量指定太大，这可能延长网络请求时间，并且大量输出会淹没你的显示窗口。实际上你可以通过 "--page" 参数实现翻页。
    """
    # 如果启用--all，则先获取有多少课程
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        
        cookies = ZjuAsyncClient().load_cookies()

        task = progress.add_task(description="拉取课程信息中...", total=1)

        async with ZjuAsyncClient(cookies=cookies) as client:
            if all:
                pre_results = (await zju_api.coursesListAPIFits(client.session, keyword, 1, 1).get_api_data())[0]
                amount = pre_results.get("total", 0)
                page_index = 1

            results = (await zju_api.coursesListAPIFits(client.session, keyword, page_index, amount).get_api_data())[0]

        progress.advance(task, 1)
        task = progress.add_task(description="渲染课程信息中...", total=1)

        total_pages = results.get("pages", 0)
        if page_index > total_pages and total_pages > 0:
            print(f"页面索引超限！共 {total_pages} 页，你都索引到第 {page_index} 页啦！")
            raise typer.Exit(code=1)

        courses_list = results.get("courses", [])
        total_results_amount = results.get("total", 0)

        # 如果搜索没有结果，则直接退出
        if total_results_amount == 0:
            print("啊呀！没有找到课程呢。")
            return
        
        # quiet 模式仅打印课程id，并且不换行
        if quiet:
            course_ids = [str(course.get("id", "")) for course in courses_list]
            print(" ".join(course_ids))
            return 
        
        courses_list_table = Table(
            title=f"课程列表 (第 {page_index} / {total_pages} 页)",
            caption=f"共找到 {total_results_amount} 个结果，本页显示 {len(courses_list)} 个。",
            border_style="bright_black",
            show_header=True,
            header_style="bold magenta",
            expand=True
        )

        # short模式仅显示课程ID与课程名称
        if short:
            courses_list_table.add_column("课程ID", style="cyan", no_wrap=True, width=8)
            courses_list_table.add_column("课程名称", style="bright_yellow", ratio=1)
        else:
            courses_list_table.add_column("课程ID", style="cyan", no_wrap=True, width=6)
            courses_list_table.add_column("课程名称", style="bright_yellow", ratio=6)
            courses_list_table.add_column("授课教师", ratio=3)
            courses_list_table.add_column("上课时间", ratio=3)
            courses_list_table.add_column("开课院系", ratio=4)
            courses_list_table.add_column("开课学年", style="white", width=9)

        # short 模式仅按表单格式打印课程名与课程id
        for course in courses_list:
            course_id = str(course.get("id", "N/A"))
            course_name = course.get("name", "N/A")

            if short:
                courses_list_table.add_row(course_id, course_name)
                continue

            course_attributes = course.get("course_attributes")
            course_time = course_attributes.get("teaching_class_name", "N/A") if course_attributes.get("teaching_class_name", "N/A") else "N/A"

            course_time = ", ".join(course_time.split(";"))

            teachers = course.get("instructors", [])
            teachers_name = ', '.join([t.get("name", "") for t in teachers]) or "N/A"

            department = course.get("department")
            course_department_name = department.get("name", "N/A") if department else "N/A"

            if len(course_department_name) > 10:
                if "与" in course_department_name:
                    course_department_name = course_department_name.split("与")[0] + "与\n" + course_department_name.split("与")[1]
                else:
                    course_department_name = course_department_name[:11] + "\n" + course_department_name[11:]
                

            academic_year = course.get("academic_year")
            course_academic_year_name = academic_year.get("name", "N/A") if academic_year else "N/A"
            
            courses_list_table.add_row(
                course_id,
                course_name,
                teachers_name,
                course_time,
                course_department_name,
                course_academic_year_name
            )
            
            if course != courses_list[-1]:
                courses_list_table.add_row()

        progress.advance(task, 1)

    rprint(courses_list_table)

# 注册课程查看命令
@view_app.command("syllabus")
@partial(syncify, raise_sync_error=False)
async def view_syllabus(
    course_id: Annotated[int, typer.Argument(help="课程id")],
    modules_id: Annotated[Optional[List[int]], typer.Option("--module", "-m", help="章节id")] = None,
    last: Annotated[Optional[bool], typer.Option("--last", "-l", help="启用此选项，自动展示最新一章节")] = False,
    indices: Annotated[Optional[str], typer.Option("--index", "-i", help="通过索引号查看章节，索引从'1'开始，支持使用范围表示，如'1-5'。", callback=parse_indices)] = "",
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此选项，展示所有章节内容")] = False
):
    """
    浏览指定课程的目录，默认对章节进行折叠，使用'--module'选项指定展开特定章节，使用'--index'展开对应索引号的章节，启用'--last'自动展开最新章节。
    """
    # 给出module_id则进行完整的请求
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        cookies = ZjuAsyncClient().load_cookies()

        task = progress.add_task(description="获取课程信息中...", total=1)
    
        # --- 加载预备课程信息 ---
        async with ZjuAsyncClient(cookies=cookies) as client:
            course_messages, raw_course_modules = await zju_api.coursePreviewAPIFits(client.session, course_id).get_api_data()
        
        course_name = course_messages.get("name", "null")
        course_modules: List[dict] = raw_course_modules.get("modules", [])

        if not course_modules:
            rprint(f"课程{course_name} (ID: {course_id}) 无章节内容")
            return
        
        if all:
            indices = list(range(0, len(course_modules)))
        
        if modules_id or indices or last:
            # --- 筛选目标modules ---
            modules_list = extract_modules(course_modules, indices, modules_id, last)
            course_modules_node_list: List[Tuple[dict, dict, dict, dict]] = []
            
            if not modules_list:
                logger.error(f"{course_name}(ID: {course_id})中你要查询的章节不存在！")
                rprint(f"未找到章节！")
                return 

            async with ZjuAsyncClient(cookies=cookies) as client:
                raw_course_activities, raw_course_exams, raw_course_classrooms, raw_course_activities_reads, raw_homework_completeness, raw_exam_completeness = await zju_api.courseViewAPIFits(client.session, course_id).get_api_data()

            for module_id, module in modules_list:
                course_activities: List[dict] = raw_course_activities.get("activities", [])
                course_exams: List[dict] = raw_course_exams.get("exams", [])
                course_classrooms: List[dict] = raw_course_classrooms.get("classrooms", [])
                exams_completeness: List[int] = raw_exam_completeness.get("exam_ids", [])
                activities_completeness: List[int] = [homework_activitie.get("id") for homework_activitie in raw_homework_completeness.get("homework_activities", {}) if homework_activitie.get("status") == "已交"]
                classrooms_completeness: List[dict] = [activity_read for activity_read in raw_course_activities_reads.get("activity_reads") if activity_read.get("activity_type") == "classroom_activity"]

                # 筛选目标activities, exams 和 classrooms
                
                activities_list: List[dict] = []
                for course_activity in course_activities:
                    if course_activity.get("module_id") == module_id:
                        activities_list.append(course_activity)

                exams_list: List[dict] = []
                for course_exam in course_exams:
                    if course_exam.get("module_id") == module_id:
                        exams_list.append(course_exam)

                classrooms_list: List[dict] = []
                for course_classroom in course_classrooms:
                    if course_classroom.get("module_id") == module_id:
                        classrooms_list.append(course_classroom)

                if len(activities_list) == 0 and len(exams_list) == 0 and len(classrooms_list) == 0:
                    rprint(f"章节 {module_id} 无内容")
                    continue
                
                course_modules_node_list.append((module, activities_list, exams_list, classrooms_list))

            if not course_modules_node_list:
                return
        else:
            modules_list = course_modules
            progress.advance(task)


        task = progress.add_task(description="加载内容中...", total=1)

        # 装填树状图
        course_tree = Tree(f"[bold yellow]{course_name}[/bold yellow][dim] 课程ID: {course_id}[/dim]")
        
        if modules_id or indices or last:
            for index, (module, activities_list, exams_list, classrooms_list) in enumerate(course_modules_node_list):
                module_name = module.get("name", "null")
                module_tree = course_tree.add(f"[green]{module_name}[/green][dim] 章节ID: {module_id}[/dim]")
                type_map = {
                    "material": "资料",
                    "online_video": "视频",
                    "homework": "作业",
                    "questionnaire": "问卷",
                    "exam": "测试",
                    "page": "页面",
                    "classroom": "课堂任务"
                }

                # --- 加载活动内容 ---
                for activity in activities_list: # type: ignore
                    # 标题、类型与ID
                    activity_title = activity.get("title", "null")
                    activity_type = type_map.get(activity.get("type", "null"), activity.get("type", "null"))
                    activity_id = activity.get("id", "null")
                    activity_completion_criterion_key = activity.get("completion_criterion_key", "none")
                    completion_status = True if activity_id in activities_completeness else False
                    # 活动的start_time和end_time都可能是null值，必须多做一次判断
                    # is_started 和 is_closed 来判断活动是否开始或者截止
                    # 开放日期
                    activity_start_time = transform_time(activity.get("start_time"))
                    
                    activity_is_started: bool = activity.get("is_started", False)
                    
                    # 截止日期
                    activity_end_time = transform_time(activity.get("end_time"))

                    activity_is_closed: bool = activity.get("is_closed", False)

                    # 创建状态描述文本和截止时间富文本
                    status_text = get_status_text(activity_is_started, activity_is_closed)
                    start_time_text = Text.assemble(
                        ("开放时间: ", "cyan"),
                        (activity_start_time, "bright_white")
                    )
                    end_time_text = Text.assemble(
                        ("截止时间: ", "cyan"),
                        (activity_end_time, "bright_white")
                    )
                    # 跳转链接
                    url_jump = make_jump_url(course_id, activity_id, activity.get("type", "null"))
                    url_jump_text = Text.assemble(
                        ("跳转链接: ", "cyan"),
                        (url_jump, "bright_white")
                    )

                    # 任务完成状态
                    completion_text = get_completion_text(completion_status, activity_completion_criterion_key)

                    # --- 准备Panel内容 ---
                    content_renderables = []
                    title_line = Text.assemble(
                        (f"{activity_title}", "bold bright_magenta"),
                        "\n",
                        completion_text,
                        status_text
                    )
                    content_renderables.append(title_line)
                    content_renderables.append(start_time_text)
                    content_renderables.append(end_time_text)
                    if url_jump:
                        content_renderables.append(url_jump_text)

                    # 附件
                    activity_uploads: List[dict]= activity.get("uploads", [])
                    if activity_uploads:
                        content_renderables.append("[cyan]附件: [/cyan]")

                    for upload in activity_uploads:
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

                    if activity_type == "作业":
                        panel_title = f"[cyan][{activity_type}][/cyan]"
                        panel_subtitle = f"[cyan]ID: {activity_id}[/cyan]"

                    else:
                        panel_title = f"[white][{activity_type}][/white]"
                        panel_subtitle = f"[white]ID: {activity_id}[/white]"

                    activity_panel = Panel(
                        Group(*content_renderables),
                        title=panel_title,
                        subtitle=panel_subtitle,
                        border_style="bright_cyan" if activity_type == "作业" else "bright_black",
                        expand=True,
                        padding=(1, 2)
                    )

                    module_tree.add(activity_panel)

                # --- 加载测试内容 ---
                for exam in exams_list:
                    exam_title = exam.get("title", "null")
                    exam_type = type_map.get(exam.get("type", "null"), exam.get("type", "null"))
                    exam_id = exam.get("id", "null")
                    exam_completion_criterion_key = exam.get("completion_criterion_key", "none")
                    completion_status = True if exam_id in exams_completeness else False

                    # 理由同上
                    # 开放日期
                    exam_start_time = transform_time(exam.get("start_time"))
                    exam_is_started: bool = exam.get("is_started", False)
                    
                    # 截止日期
                    exam_end_time = transform_time(exam.get("end_time"))

                    exam_is_closed: bool = exam.get("is_closed", False)

                    # 创建状态描述文本和截止时间富文本
                    status_text = get_status_text(exam_is_started, exam_is_closed)
                    start_time_text = Text.assemble(
                        ("开放时间: ", "cyan"),
                        (exam_start_time, "bright_white")
                    )
                    end_time_text = Text.assemble(
                        ("截止时间: ", "cyan"),
                        (exam_end_time, "bright_white")
                    )
                    url_jump = make_jump_url(course_id, exam_id, exam.get("type", "null"))
                    url_jump_text = Text.assemble(
                        ("跳转链接: ", "cyan"),
                        (url_jump, "bright_white")
                    )

                    completion_text = get_completion_text(completion_status, exam_completion_criterion_key)

                    # --- 准备Panel内容 ---
                    content_renderables = []
                    title_line = Text.assemble(
                        (f"{exam_title}", "bold bright_magenta"),
                        "\n",
                        completion_text,
                        status_text
                    )
                    content_renderables.append(title_line)
                    content_renderables.append(start_time_text)
                    content_renderables.append(end_time_text)
                    content_renderables.append(url_jump_text)

                    panel_title = f"[yellow][{exam_type}][/yellow]"
                    panel_subtitle = f"[yellow]ID: {exam_id}[/yellow]"

                    activity_panel = Panel(
                        Group(*content_renderables),
                        title=panel_title,
                        subtitle=panel_subtitle,
                        border_style="bright_yellow",
                        expand=True,
                        padding=(1, 2)
                    )

                    module_tree.add(activity_panel)

                # --- 加载课堂任务内容 ---
                for classroom in classrooms_list:
                    classroom_title = classroom.get("title", "null")
                    classroom_type = type_map.get(classroom.get("type", "null"), classroom.get("type", "null"))
                    classroom_id = classroom.get("id", "null")
                    classroom_status = classroom.get("status")
                    classroom_completeness_status = [classroom_completeness.get("completeness", "null") for classroom_completeness in classrooms_completeness if classroom_completeness.get("activity_id") == classroom_id][0]

                    classroom_start_time: str = transform_time(classroom.get("start_at"))

                    classroom_status_text = get_classroom_status_text(classroom_status)
                    classroom_completeness_status_text = get_classroom_completion_text(classroom_completeness_status)
                    start_time_text = Text.assemble(
                        ("开放时间: ", "cyan"),
                        (classroom_start_time, "bright_white")
                    )

                    prompt_text = Text("请在移动端上完成！", "red")
                    
                    # --- 准备Panel内容 ---
                    content_renderables = []
                    title_line = Text.assemble(
                        (f"{classroom_title}", "bold bright_magenta"),
                        "\n",
                        classroom_completeness_status_text,
                        classroom_status_text
                    )
                    content_renderables.append(title_line)
                    content_renderables.append(start_time_text)
                    content_renderables.append("")
                    content_renderables.append(prompt_text)

                    panel_title = f"[yellow][{classroom_type}][/yellow]"
                    panel_subtitle = f"[yellow]ID: {classroom_id}[/yellow]"

                    classroom_panel = Panel(
                        Group(*content_renderables),
                        title=panel_title,
                        subtitle=panel_subtitle,
                        border_style="bright_green",
                        expand=True,
                        padding=(1, 2)
                    )

                    module_tree.add(classroom_panel)
        else:
            for index, module in enumerate(modules_list):
                module_name = module.get("name", "null")
                module_id = module.get("id", "null")

                # 微型表格，装填！ ---- from gemini 2.5pro
                course_tree_node = Table(show_header=False, box=None, padding=(0, 1), show_edge=False, expand=True)
                course_tree_node.add_column("Name", no_wrap=True, style="green")
                course_tree_node.add_column("ID", justify="right", style="bright_white")
                course_tree_node.add_row(f"[magenta]{index + 1}[/magenta] {module_name}", f"章节ID: {module_id}")

                course_tree.add(course_tree_node)

        progress.advance(task)

    rprint(course_tree)

@view_app.command("coursewares")
@partial(syncify, raise_sync_error=False)
async def view_coursewares(
    course_id: Annotated[int, typer.Argument(help="课程ID")],
    page: Annotated[Optional[int], typer.Option("--page", "-p", help="页面索引")] = 1,
    page_size: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示课件数量")] = 10,
    short: Annotated[Optional[bool], typer.Option("--short", "-s", help="启用此选项，简化输出，仅显示文件名与文件ID")] = False,
    quiet: Annotated[Optional[bool], typer.Option("--quiet", "-q", help="启用此选项，仅输出文件ID")] = False,
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此选项，输出所有结果")] = False
):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        cookies = ZjuAsyncClient().load_cookies()

        task = progress.add_task(description="获取课程信息中...", total=2)

        async with ZjuAsyncClient(cookies=cookies) as client:
            if all:
                pre_raw_coursewares = (await zju_api.coursewaresViewAPIFits(client.session, course_id, 1, 1).get_api_data())[0]
                page = 1
                page_size = pre_raw_coursewares.get("total", 0)

            raw_coursewares = (await zju_api.coursewaresViewAPIFits(client.session, course_id, page, page_size).get_api_data())[0]
        
        progress.update(task, description="渲染任务信息中...", advance=1)
        
        # 检验返回结果
        total: int = raw_coursewares.get("total", 0)
        pages: int = raw_coursewares.get("pages", 0)

        if total == 0:
            rprint("当前还没有课件哦~\\( ^ ω ^ )/")

        if page > pages:
            rprint(f"当前仅有 {pages} 页，你都索引到 {page} 页啦！[○･｀Д´･ ○]")

        # 提取并拼装所有文件
        coursewares_list: List[dict] = raw_coursewares.get("activities", [])
        coursewares_uploads: List[dict] = []
        for courseware in coursewares_list:
            coursewares_uploads.extend(courseware.get("uploads", []))

        if quiet:
            courseware_ids = [str(courseware_upload.get("id", "null")) for courseware_upload in coursewares_uploads]
            print(" ".join(courseware_ids))
            return

        # --- 准备表格 ---
        coursewares_table = Table(
            title=f"资源列表 (第 {page} / {pages} 页)",
            caption=f"本页显示 {len(coursewares_uploads)} 个，共 {total} 个结果。",
            border_style="bright_black",
            show_header=True,
            header_style="bold magenta",
            expand=True
        )

        if short:
            coursewares_table.add_column("资源ID", style="cyan", no_wrap=True, width=10)
            coursewares_table.add_column("资源名称", style="bright_yellow", ratio=1)
        else:
            coursewares_table.add_column("资源ID", style="cyan", no_wrap=True, width=8)
            coursewares_table.add_column("资源名称", style="bright_yellow", ratio=3)
            coursewares_table.add_column("上传时间", ratio=1)
            coursewares_table.add_column("文件大小", ratio=1)

        for courseware_upload in coursewares_uploads:
            courseware_id   = str(courseware_upload.get("id", "null"))
            courseware_name = courseware_upload.get("name", "null")

            if short:
                coursewares_table.add_row(
                    courseware_id,
                    courseware_name
                )

                if courseware_upload != coursewares_uploads[-1]:
                    coursewares_table.add_row()

                continue

            courseware_size        = filesize.decimal(courseware_upload.get("size", 0))
            courseware_update_time = transform_time(courseware_upload.get("updated_at", "1900-01-01T00:00:00Z"))

            coursewares_table.add_row(
                courseware_id,
                courseware_name,
                courseware_update_time,
                courseware_size
            )

            if courseware_upload != coursewares_uploads[-1]:
                coursewares_table.add_row()

        progress.update(task, description="渲染完成！", advance=1)

    rprint(coursewares_table)

@view_app.command("enrollments")
@partial(syncify, raise_sync_error=False)
async def view_members(
    course_id: Annotated[int, typer.Argument(help="课程ID")],
    keyword: Annotated[Optional[str|None], typer.Option("--keyword", "-k", help="搜索关键词")] = None,
    instructor: Annotated[Optional[bool], typer.Option("--instructor", "-I", help="启用此选项，只输出教师")] = False,
    student: Annotated[Optional[bool], typer.Option("--student", "-S", help="启用此选项，只输出学生")] = False
):
    if instructor and student:
        rprint("[red](#`Д´)ﾉ不可以同时'只'输出啦！[/red]")
        raise typer.Exit(code=1)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        cookies = ZjuAsyncClient().load_cookies()
        task = progress.add_task(description="请求数据中...", total=2)

        async with ZjuAsyncClient(cookies=cookies) as client:
            raw_course_enrollments = (await zju_api.courseMembersViewAPIFits(client.session, course_id, keyword).get_api_data())[0]

        progress.update(task, description="渲染任务信息中...", advance=1)
        course_enrollments = raw_course_enrollments.get("enrollments")

        if not course_enrollments:
            rprint("[red]∑(✘Д✘๑ )呀，没有结果呢~[/red]")
            return 

        instructor_course_enrollments = []
        student_course_enrollments = []

        if instructor:
            instructor_course_enrollments = [enrollment.get("user").get("name") for enrollment in course_enrollments if enrollment.get("roles")[0] == "instructor"]
        elif student:
            student_course_enrollments    = [enrollment.get("user").get("name") for enrollment in course_enrollments if enrollment.get("roles")[0] == "student"]
        else:
            instructor_course_enrollments = [enrollment.get("user").get("name") for enrollment in course_enrollments if enrollment.get("roles")[0] == "instructor"]
            student_course_enrollments    = [enrollment.get("user").get("name") for enrollment in course_enrollments if enrollment.get("roles")[0] == "student"]

        if not instructor_course_enrollments and not student_course_enrollments:
            rprint("[red]∑(✘Д✘๑ )呀，没有结果呢~[/red]")
            return 
            
        if instructor_course_enrollments:
            rprint(f"[cyan]教师: [/cyan]{', '.join(instructor_course_enrollments)}")
        
        if student_course_enrollments:
            rprint(f"[cyan]学生: [/cyan]{', '.join(student_course_enrollments)}")
        
        progress.update(task, description="渲染完成x    ...", advance=1)

@view_app.command("assignments")
@partial(syncify, raise_sync_error=False)
async def view_assignments(
    course_id: Annotated[int, typer.Argument(help="课程ID")],
    page: Annotated[Optional[int], typer.Option("--page", "-p", help="页面索引")] = 1,
    page_size: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示任务数量")] = 10,
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此选项，输出所有结果")] = False
):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        cookies = ZjuAsyncClient().load_cookies()
        task = progress.add_task(description="获取任务信息中...", total=2)
        async with ZjuAsyncClient(cookies=cookies) as client:
            raw_course_activities, raw_course_exams, raw_course_classrooms, raw_course_activities_reads, raw_homework_completeness, raw_exam_completeness = await zju_api.courseViewAPIFits(client.session, course_id)

        progress.update(task, description="渲染任务信息中...", completed=1)

        activities_list: List[dict]         = raw_course_activities.get("activities", [])
        exams_list: List[dict]              = raw_course_exams.get("exams", [])
        classrooms_list: List[dict]         = raw_course_classrooms.get("classrooms", [])
        exams_completeness: List[int]       = raw_exam_completeness.get("exam_ids", [])
        activities_completeness: List[int]  = [homework_activitie.get("id") for homework_activitie in raw_homework_completeness.get("homework_activities", {}) if homework_activitie.get("status") == "已交"]
        classrooms_completeness: List[dict] = [activity_read for activity_read in raw_course_activities_reads.get("activity_reads") if activity_read.get("activity_type") == "classroom_activity"]

        


# view 注册入课程命令组
app.add_typer(view_app, name="view")