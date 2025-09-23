import typer
from typing_extensions import Optional, Annotated, List
from requests import Session
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.tree import Tree
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.console import Group
from datetime import datetime

from printlog.print_log import print_log
from zjuAPI import zju_api
from ..state import state

# course 命令组
app = typer.Typer(help="""
学在浙大课程相关命令组，提供了对课程的查询与对课程章节查看的功能。
""")

# 文件大小换算
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

def get_status_text(start_status: bool, close_status: bool)->Text:
    if close_status:
        return Text(f"🔴 已结束", style="red")
    
    if start_status:
        return Text(f"🟢 进行中", style="green")
    
    return Text(f"⚪️ 未开始", style="dim")

def get_completion_text(completion_status: bool, completion_criterion_key: str)->Text:
    if completion_criterion_key == "none":
        return Text(f"无需完成", style="dim")
    
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

# 注册课程列举命令
@app.command("list")
def list_courses(
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
        task = progress.add_task(description="拉取课程信息中...", total=1)
        if all:
            pre_results = zju_api.coursesListAPIFits(state.client.session, keyword, 1, 1).get_api_data()[0]
            amount = pre_results.get("total", 0)
            page_index = 1

        results = zju_api.coursesListAPIFits(state.client.session, keyword, page_index, amount).get_api_data()[0]
        
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

@app.command("view")
def view_course(
    course_id: Annotated[int, typer.Argument(help="课程id")],
    module_id: Annotated[Optional[int], typer.Option("--module", "-m", help="章节id")] = None
):
    """
    浏览指定课程的目录，默认对章节进行折叠，使用'--module'选项指定展开特定章节。
    """
    # 给出module_id则进行完整的请求
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(description="获取课程信息中...", total=1)
        if module_id:
            course_messages, raw_course_modules, raw_course_activities, raw_course_exams, raw_course_completeness, raw_course_classrooms, raw_course_activities_reads = zju_api.courseViewAPIFits(state.client.session, course_id).get_api_data()
            course_name = course_messages.get("name", "null")
            course_modules: List[dict] = raw_course_modules.get("modules", [])
            course_activities: List[dict] = raw_course_activities.get("activities", [])
            course_exams: List[dict] = raw_course_exams.get("exams", [])
            course_classrooms: List[dict] = raw_course_classrooms.get("classrooms", [])
            exams_completeness: List[int] = raw_course_completeness.get("completed_result", {}).get("completed", {}).get("exam_activity", [])
            activities_completeness: List[int] = raw_course_completeness.get("completed_result", {}).get("completed", {}).get("learning_activity", [])
            classrooms_completeness: List[dict] = [activity_read for activity_read in raw_course_activities_reads.get("activity_reads") if activity_read.get("activity_type") == "classroom_activity"]

            # 筛选目标module, activities 和 exams
            modules_list: List[dict] = []
            for course_module in course_modules:
                if course_module.get("id") == module_id:
                    modules_list.append(course_module)
                    break
            else:
                print_log("Error", f"{course_name}(ID: {course_id})中 {module_id} 章节不存在！", "CLI.command.course.view_course")
                rprint(f"未找到ID为 {module_id} 的章节！")
                raise typer.Exit(code=1)
            
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
                return 

        else:
            course_messages, raw_course_modules = zju_api.courseViewAPIFits(state.client.session, course_id, ["view", "modules"]).get_api_data()
            course_name = course_messages.get("name", "null")
            modules_list: List[dict] = raw_course_modules.get("modules", [])
        progress.advance(task)

        task = progress.add_task(description="加载内容中...", total=1)

        # 装填树状图
        course_tree = Tree(f"[bold yellow]{course_name}[/bold yellow][dim] 课程ID: {course_id}[/dim]")
        if module_id:
            module = modules_list[0]
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
                activity_start_time = activity.get("start_time", "1900-01-01T00:00:00Z")
                if activity_start_time:
                    activity_start_time = datetime.fromisoformat(activity_start_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    activity_start_time = "null"
                
                activity_is_started: bool = activity.get("is_started", False)
                
                # 截止日期
                activity_end_time = activity.get("end_time", "1900-01-01T00:00:00Z")
                if activity_end_time:
                    activity_end_time = datetime.fromisoformat(activity_end_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    activity_end_time = "null"

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
                    file_size = transform_resource_size(upload.get("size", 0))

                    upload_table = Table(show_header=False, box=None, padding=(0, 1), show_edge=False, expand=True)
                    upload_table.add_column("Name", no_wrap=True)
                    upload_table.add_column("Info", justify="right")

                    upload_table.add_row(
                        f"{file_name}",
                        f"大小: {file_size} | 文件ID: {file_id}"
                    )
                    
                    content_renderables.append(upload_table)

                panel_title = f"[white][{activity_type}][/white]"
                panel_subtitle = f"[white]ID: {activity_id}[/white]"

                activity_panel = Panel(
                    Group(*content_renderables),
                    title=panel_title,
                    subtitle=panel_subtitle,
                    border_style="bright_black",
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
                exam_start_time = exam.get("start_time", "1900-01-01T00:00:00Z")
                if exam_start_time:
                    exam_start_time = datetime.fromisoformat(exam_start_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    exam_start_time = "null"
                
                exam_is_started: bool = exam.get("is_started", False)
                
                # 截止日期
                exam_end_time = exam.get("end_time", "1900-01-01T00:00:00Z")
                if exam_end_time:
                    exam_end_time = datetime.fromisoformat(exam_end_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    exam_end_time = "null"

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

                classroom_start_time: str = classroom.get("start_at", "1900-01-01T00:00:00Z")
                if classroom_start_time:
                    classroom_start_time = datetime.fromisoformat(classroom_start_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    classroom_start_time = "null"

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
            for module in modules_list:
                module_name = module.get("name", "null")
                module_id = module.get("id", "null")

                # 微型表格，装填！ ---- from gemini 2.5pro
                course_tree_node = Table(show_header=False, box=None, padding=(0, 1), show_edge=False, expand=True)
                course_tree_node.add_column("Name", no_wrap=True, style="green")
                course_tree_node.add_column("ID", justify="right", style="bright_white")
                course_tree_node.add_row(module_name, f"章节ID: {module_id}")

                course_tree.add(course_tree_node)

        progress.advance(task)

    rprint(course_tree)