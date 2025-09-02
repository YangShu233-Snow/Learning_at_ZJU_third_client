import typer
from typing_extensions import Optional, Annotated, List
from requests import Session
from rich import print as rprint
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
    quiet: Annotated[Optional[bool], typer.Option("--quiet", "-q", help="仅输出课程id")] = False
    ):
    """
    列举学在浙大内的课程信息，允许指定课程名称，显示数量。

    并不建议将显示数量指定太大，这可能延长网络请求时间，并且大量输出会淹没你的显示窗口。实际上你可以通过 "--page" 参数实现翻页。
    """
    results = zju_api.coursesListAPIFits(state.client.session, keyword, page_index, amount).get_api_data()[0]
    total_pages = results.get("pages", 0)
    if page_index > total_pages:
        print(f"页面索引超限！共 {total_pages} 页，你都索引到第 {page_index} 页啦！")
        raise typer.Exit(code=1)

    courses_list = results.get("courses", [])
    current_results_amount = results.get("total", 0)

    # 如果搜索没有结果，则直接退出
    if current_results_amount == 0:
        print("啊呀！没有找到课程呢。")
        return
    
    # quiet 模式仅打印文件id，并且不换行
    # short 模式仅按表单格式打印文件名与文件id
    for course in courses_list:
        # 课程id
        course_id = course.get("id", "null")

        if quiet:
            print(course_id, end=" ")
            continue

        # 课程名称
        course_name = course.get("name", "null")
        if short:
            print("------------------------------")
            rprint(f"[bright_yellow]{course_name}[/bright_yellow]")
            rprint(f"  [green]文件ID: [/green][cyan]{course_id}[/cyan]")
            continue


        # 上课时间
        course_attributes = course.get("course_attributes")
        if course_attributes:
            course_time = course_attributes.get("teaching_class_name", "null")
        else:
            course_time = "null"

        # 授课教师
        teachers_name = []
        if course.get("instructors"):
            for teacher in course.get("instructors"):
                name = teacher.get("name", "null")
                teachers_name.append(name)
        else:
            teachers_name = [""]

        # 开课院系
        course_department = course.get("department")
        if course_department:
            course_department_name = course_department.get("name", "null")
        else:
            course_department_name = "null"

        # 课程学年
        course_academic_year = course.get("academic_year")
        if course_academic_year:
            course_academic_year_name = course_academic_year.get("name", "null")
        else:
            course_academic_year_name = "null"
        
        # 课程代码
        course_code = course.get("course_code", "null")

        print("----------------------------------------")
        rprint(f"[bright_yellow]{course_name}[/bright_yellow]")
        rprint(f"  [green]课程ID: [/green]  [cyan]{course_id}[/cyan]")
        rprint(f"  [green]上课时间: [/green][cyan]{course_time}[/cyan]")
        rprint(f"  [green]授课教师: [/green]{'、'.join(teachers_name)}")
        rprint(f"  [green]开课院系: [/green]{course_department_name}")
        rprint(f"  [green]开课学年: [/green][white]{course_academic_year_name}[/white]")
        rprint(f"  [green]课程代码：[/green][bright_black]{course_code}[/bright_black]")

    if quiet:
        print("\n")
        return

    if short:
        print("------------------------------")
        print(f"本页共 {current_results_amount} 个结果，第 {page_index}/{total_pages} 页。")
        return

    print("----------------------------------------")
    print(f"本页共 {current_results_amount} 个结果，第 {page_index}/{total_pages} 页。")

@app.command("view")
def view_course(
    course_id: Annotated[int, typer.Argument(help="课程id")],
    module_id: Annotated[Optional[int], typer.Option("--module", "-m", help="章节id")] = None
):
    """
    
    """
    # 给出module_id则进行完整的请求
    if module_id:
        course_messages, raw_course_modules, raw_course_activities, raw_course_exams = zju_api.courseViewAPIFits(state.client.session, course_id).get_api_data()
        course_name = course_messages.get("name", "null")
        course_modules: List[dict] = raw_course_modules.get("modules", [])
        course_activities: List[dict] = raw_course_activities.get("activities", [])
        course_exams: List[dict] = raw_course_exams.get("exams", [])

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

        exam_lists: List[dict] = []
        for course_exam in course_exams:
            if course_exam.get("module_id") == module_id:
                exam_lists.append(course_exam)
    else:
        course_messages, raw_course_modules = zju_api.courseViewAPIFits(state.client.session, course_id, ["view", "modules"]).get_api_data()

        course_name = course_messages.get("name", "null")
        modules_list: List[dict] = raw_course_modules.get("modules", [])

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
            "exam": "测试"
        }

        for activity in activities_list:
            # 标题、类型与ID
            activity_title = activity.get("title", "null")
            activity_type = type_map.get(activity.get("type", "null"), activity.get("type", "null"))
            activity_id = activity.get("id", "null")

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
            url_jump = make_jump_url(course_id, activity_id, activity.get("type", "null"))
            url_jump_text = Text.assemble(
                ("跳转链接: ", "cyan"),
                (url_jump, "bright_white")
            )

            # --- 准备Panel内容 ---
            content_renderables = []
            title_line = Text.assemble(
                (f"{activity_title}", "bold bright_magenta"),
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

        for exam in exam_lists:
            exam_title = exam.get("title", "null")
            exam_type = type_map.get(exam.get("type", "null"), exam.get("type", "null"))
            exam_id = exam.get("id", "null")

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

            # --- 准备Panel内容 ---
            content_renderables = []
            title_line = Text.assemble(
                (f"{exam_title}", "bold bright_magenta"),
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

    rprint(course_tree)
