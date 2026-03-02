import logging
import math
from functools import partial
from textwrap import dedent
from typing import List, Optional, Tuple

import keyring
import typer
from asyncer import syncify
from rich import filesize
from rich import print as rprint
from rich.console import Group
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich.tree import Tree
from typing_extensions import Annotated

from ...login.login import CredentialManager, ZjuAsyncClient
from ...zjuAPI import zju_api
from ..state import state
from ..utils.utils import (
    get_status_text,
    make_jump_url,
    print_with_json,
    transform_time,
)

KEYRING_SERVICE_NAME = "lazy"
KEYRING_LAZ_STUDENTID_NAME = "laz_studentid"

# course 命令组
app = typer.Typer(help="""
                        管理学在浙大课程信息与章节
                       """,
                    no_args_is_help=True
                  )

logger = logging.getLogger(__name__)

# view 子命令组
view_app = typer.Typer(help="学在浙大课程查看相关命令组，支持对课程多维信息的查看。", no_args_is_help=True)

def get_completion_json(completion_status: bool, completion_criterion_key: str)->str:
    if completion_criterion_key == "none":
        return "No need to complete"
    
    if completion_status:
        return "Completed"
    
    return "Incomplete"

def get_completion_text(completion_status: bool, completion_criterion_key: str)->Text:
    if completion_criterion_key == "none":
        return Text("无完成指标", style="dim")
    
    if completion_status:
        return Text("🟢 已完成", style="green")
    
    return Text("🔴 未完成", style="red")

def get_classroom_status_json(status: str)->str:
    if status == "finish":
        return "Closed"
    
    if status == "start":
        return "In Progress"
    
    return "Not Started"

def get_classroom_status_text(status: str)->Text:
    if status == "finish":
        return Text("🔴 已结束", style="red")
    
    if status == "start":
        return Text("🟢 进行中", style="green")
    
    return Text("⚪️ 未开始", style="dim")

def get_classroom_completion_json(completion_key: str)->bool:
    return completion_key == "full"

def get_classroom_completion_text(completion_key: str)->Text:
    if completion_key == "full":
        return Text("🟢 已完成", style="green")
    
    return Text("🔴 未完成", style="red")

def parse_indices(indices: str|None)->List[int]:
    if not indices:
        return []
    
    indices = indices.split(',') if ',' in indices else [indices]

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
                raise typer.Exit(code=1) from e
        else:
            try:
                result.append(int(item)-1)
            except ValueError as e:
                logger.error(f"{item} 格式有误，错误信息: {e}")
                typer.echo(f"{item} 应为整数！", err=True)
                raise typer.Exit(code=1) from e
    
    # 去重，排序
    return sorted(list(set(result)))

def extract_modules(modules: List[dict], indices: List[int], modules_id: List[int], last: bool)->List[Tuple[int, dict]]:
    result = []
    
    safe_indices = indices if indices is not None else []
    safe_modules_id = modules_id if modules_id is not None else []

    for index, module in enumerate(modules):
        if index in safe_indices or module.get("id") in safe_modules_id:
            result.append((module.get("id"), module))

    if last and modules[-1] not in result:
        result.append((modules[-1].get("id"), modules[-1]))

    return result

# 注册课程列举命令
@app.command(
        "ls",
        help="Alias for 'list'",
        hidden=True,
        epilog=dedent("""
            EXAMPLES:

              $ lazy course list -n "微积分"
                (搜索名称包括"微积分"的课程)
              
              $ lazy course list -A -q      
                (仅列出所有课程的ID)
            
              $ lazy course list -p 2 -a 5  
                (查看第 2 页，每页显示 5 个结果)
        """))
@app.command(
        "list",
        help="列举课程并支持搜索",
        epilog=dedent("""
            EXAMPLES:

              $ lazy course list -n "微积分"
                (搜索名称包括"微积分"的课程)
              
              $ lazy course list -A -q      
                (仅列出所有课程的ID)
            
              $ lazy course list -p 2 -a 5  
                (查看第 2 页，每页显示 5 个结果)
        """))
@partial(syncify, raise_sync_error=False)
async def list_courses(
    keyword: Annotated[Optional[str], typer.Option("--name", "-n", help="课程搜索关键字")] = None,
    amount: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示课程的数量")] = 10,
    page_index: Annotated[Optional[int], typer.Option("--page", "-p", help="课程页面索引")] = 1,
    short: Annotated[Optional[bool], typer.Option("--short", "-s", help="简化输出内容，仅显示课程名与课程id")] = False,
    quiet: Annotated[Optional[bool], typer.Option("--quiet", "-q", help="仅输出课程id")] = False,
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此参数，一次性输出所有结果")] = False,
    json: Annotated[Optional[bool], typer.Option("--json", "-J", hidden=True)] = False
    ):
    """
    列举学在浙大内的课程信息，并按条件筛选。

    默认按分页显示（每页10条）。你可以使用 -n 进行关键词搜索，
    或者使用 -A 来获取所有结果（这将忽略 -p 和 -a）。
    """
    # 如果启用--all，则先获取有多少课程
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=json
    ) as progress:
        
        cookies = CredentialManager().load_cookies()
        if not cookies:
            if json:
                print_with_json(False, "Cookies is unacceptable.")
            else:
                rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)
        
        task = progress.add_task(description="拉取课程信息中...", total=1)

        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            if all:
                pre_results = (await zju_api.coursesListAPIFits(client.session, keyword, 1, 1).get_api_data())[0]
                amount = pre_results.get("total", 0)
                page_index = 1

            results = (await zju_api.coursesListAPIFits(client.session, keyword, page_index, amount).get_api_data())[0]

        progress.advance(task, 1)
        task = progress.add_task(description="渲染课程信息中...", total=1)

        total_pages = results.get("pages", 0)
        if page_index > total_pages and total_pages > 0:
            
            if json:
                print_with_json(False, f"Index Exceeded! Index page {page_index} of {total_pages}")
            else:
                rprint(f"页面索引超限！共 {total_pages} 页，你都索引到第 {page_index} 页啦！")
            
            raise typer.Exit(code=1)

        courses_list = results.get("courses", [])
        total_results_amount = results.get("total", 0)

        # 如果搜索没有结果，则直接退出
        if total_results_amount == 0:
            if json:
                print_with_json(True, "Not Found")    
            else:
                rprint("啊呀！没有找到课程呢。")
            
            return

        # quiet 模式仅打印课程id，并且不换行
        if quiet:
            course_ids = [str(course.get("id", "")) for course in courses_list]
            if json:
                print_with_json(True, "Courses List", course_ids)
            else:
                print(" ".join(course_ids))
            
            return 
        
        if json:
            results = []
            for course in courses_list:
                course_id = str(course.get("id"))
                course_name = course.get("name")

                if short:
                    results.append({
                        "name": course_name,
                        "id": course_id
                    })
                    
                    continue

                course_attributes = course.get("course_attributes")
                course_time = course_attributes.get("teaching_class_name", "N/A") if course_attributes.get("teaching_class_name", "N/A") else "N/A"
                course_time = ", ".join(course_time.split(";"))
                teachers = course.get("instructors", [])
                teachers_name = ', '.join([t.get("name", "") for t in teachers]) or "N/A"
                department = course.get("department")
                course_department_name = department.get("name", "N/A") if department else "N/A"
                academic_year = course.get("academic_year")
                course_academic_year_name = academic_year.get("name", "N/A") if academic_year else "N/A"

                results.append({
                    "name": course_name,
                    "id": course_id,
                    "time": course_time,
                    "teachers": teachers_name,
                    "department_name": course_department_name,
                    "academic_year": course_academic_year_name
                })

            print_with_json(True, "Courses List", results)
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
@view_app.command(
        "sy",
        help="Alias for 'syllabus'",
        hidden=True,
        epilog=dedent("""
            EXAMPLES:

              $ lazy course view syllabus 114514       
                (查看ID为"114514"课程的章节目录)
            
              $ lazy course view syllabus 114514 -i 4  
                (查看ID为"114514"课程的第四章节内容)
              
              $ lazy course view syllabus 114514 -A -e 
                (查看ID为"114514"课程所有的测试活动)
                
              $ lazy course view syllabus 114514 --last
                (查看ID为"114514"课程的最新章节内容)
        """),
        no_args_is_help=True)
@view_app.command(
        "syllabus",
        help="查看课程目录",
        epilog=dedent("""
            EXAMPLES:

              $ lazy course view syllabus 114514       
                (查看ID为"114514"课程的章节目录)
            
              $ lazy course view syllabus 114514 -i 4  
                (查看ID为"114514"课程的第四章节内容)
              
              $ lazy course view syllabus 114514 -A -e 
                (查看ID为"114514"课程所有的测试活动)
                
              $ lazy course view syllabus 114514 --last
                (查看ID为"114514"课程的最新章节内容)
        """),
        no_args_is_help=True)
@partial(syncify, raise_sync_error=False)
async def view_syllabus(
    course_id: Annotated[int, typer.Argument(help="课程id")],
    modules_id: Annotated[Optional[List[int]], typer.Option("--module", "-m", help="章节id")] = None,
    last: Annotated[Optional[bool], typer.Option("--last", "-l", help="启用此选项，自动展示最新一章节")] = False,
    indices: Annotated[Optional[str], typer.Option("--index", "-i", help="通过索引号查看章节，索引从'1'开始，支持使用范围表示，如'1-5'。", callback=parse_indices)] = "",
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此选项，展示所有章节内容")] = False,
    only_activity: Annotated[Optional[bool], typer.Option("--activity", "-a", help="启用此选项，只展示活动内容")] = False,
    only_classroom: Annotated[Optional[bool], typer.Option("--classroom", "-c", help="启用此选项，只展示课堂任务")] = False,
    only_exam: Annotated[Optional[bool], typer.Option("--exam", "-e", help="启用此选项，只展示测试内容")] = False,
    only_homework: Annotated[Optional[bool], typer.Option("--homework", "-H", help="启用此选项，只展示作业")] = False,
    json: Annotated[Optional[bool], typer.Option("--json", "-J", hidden=True)] = False
):
    """
    浏览指定课程的目录，并按条件进行筛选。
    
    默认对章节进行折叠，你可以通过 -m 或 -i 来展开指定的章节。
    或者使用 -A 来展开所有章节，并通过 -a, -c, -e 与 -H 进行筛选。
    """
    # 给出module_id则进行完整的请求
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=json
    ) as progress:
        cookies = CredentialManager().load_cookies()
        if not cookies:
            if json:
                print_with_json(False, "Cookies is unacceptable.")
            else:
                rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)

        task = progress.add_task(description="获取课程信息中...", total=1)
    
        # --- 加载预备课程信息 ---
        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            course_messages, raw_course_modules = await zju_api.coursePreviewAPIFits(client.session, course_id).get_api_data()
        
        course_name = course_messages.get("name", "null")
        course_modules: List[dict] = raw_course_modules.get("modules", [])

        if not course_modules:
            if json:
                print_with_json(True, "Not Content")
            else:
                rprint(f"课程{course_name} (ID: {course_id}) 无章节内容")

            return
        
        if all:
            indices = list(range(0, len(course_modules)))
        
        if modules_id or indices or last:
            # --- 筛选目标modules ---
            modules_list = extract_modules(course_modules, indices, modules_id, last)
            course_modules_node_list: List[Tuple[dict, dict, dict, dict]] = []
            
            if not modules_list:
                if json:
                    print_with_json(True, "Not Found")
                else:
                    rprint("未找到章节！")

                return 

            async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
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
                if not (only_classroom or only_exam):
                    for course_activity in course_activities:
                        if only_homework and course_activity.get("type", "null") != "homework":
                            continue

                        if course_activity.get("module_id") == module_id:
                                activities_list.append(course_activity)

                exams_list: List[dict] = []
                if not (only_classroom or only_activity or only_homework):
                    for course_exam in course_exams:
                        if course_exam.get("module_id") == module_id:
                            exams_list.append(course_exam)

                classrooms_list: List[dict] = []
                if not (only_exam or only_activity or only_homework):
                    for course_classroom in course_classrooms:
                        if course_classroom.get("module_id") == module_id:
                            classrooms_list.append(course_classroom)

                if len(activities_list) == 0 and len(exams_list) == 0 and len(classrooms_list) == 0:
                    if json:
                        print_with_json(True, f"Module {module_id} Not Content")
                    else:
                        rprint(f"章节 {module_id} 无内容")
                    
                    return
                
                course_modules_node_list.append((module, activities_list, exams_list, classrooms_list))

            if not course_modules_node_list:
                return
        else:
            modules_list = course_modules
            progress.advance(task)


        task = progress.add_task(description="加载内容中...", total=1)

        if json:
            modules = []
            if modules_id or indices or last:
                for _, (module, activities_list, exams_list, classrooms_list) in enumerate(course_modules_node_list):
                    module_name = module.get("name", "null")
                    type_map = {
                        "material": "资料",
                        "online_video": "视频",
                        "homework": "作业",
                        "questionnaire": "问卷",
                        "exam": "测试",
                        "page": "页面",
                        "classroom": "课堂任务"
                    }

                    activities = []
                    for activity in activities_list: # type: ignore
                        # 标题、类型与ID
                        activity_title = activity.get("title")
                        activity_type = type_map.get(activity.get("type"), activity.get("type"))
                        activity_id = activity.get("id")
                        activity_completion_criterion_key = activity.get("completion_criterion_key")
                        completion_status = activity_id in activities_completeness
                        completion_text = get_completion_json(completion_status, activity_completion_criterion_key)

                        # 开放日期
                        activity_start_time = transform_time(activity.get("start_time"))
                        activity_is_started: bool = activity.get("is_started", False)
                        
                        # 截止日期
                        activity_end_time = transform_time(activity.get("end_time"))
                        activity_is_closed: bool = activity.get("is_closed", False)
                        
                        # 跳转链接
                        url_jump = make_jump_url(course_id, activity_id, activity.get("type"))

                        # 附件
                        activity_uploads: List[dict]= activity.get("uploads", [])
                        uploads = []
                        for upload in activity_uploads:
                            file_name = upload.get("name")
                            file_id = upload.get("id")
                            file_size = filesize.decimal(upload.get("size", 0))

                            uploads.append({
                                "filename": file_name,
                                "id": file_id,
                                "size": file_size
                            })

                        activities.append({
                            "title": activity_title,
                            "type": activity_type,
                            "id": activity_id,
                            "completion": completion_text,
                            "start_time": activity_start_time,
                            "is_started": activity_is_started,
                            "end_time": activity_end_time,
                            "is_closed": activity_is_closed,
                            "uploads": uploads
                        })
                    
                    exams = []
                    for exam in exams_list:
                        exam_title = exam.get("title", "null")
                        exam_type = type_map.get(exam.get("type", "null"), exam.get("type", "null"))
                        exam_id = exam.get("id", "null")
                        exam_completion_criterion_key = exam.get("completion_criterion_key", "none")
                        completion_status = exam_id in exams_completeness
                        completion_text = get_completion_json(completion_status, exam_completion_criterion_key)
                        # 开放日期
                        exam_start_time = transform_time(exam.get("start_time"))
                        exam_is_started: bool = exam.get("is_started", False)
                        # 截止日期
                        exam_end_time = transform_time(exam.get("end_time"))
                        exam_is_closed: bool = exam.get("is_closed", False)
                        url_jump = make_jump_url(course_id, exam_id, exam.get("type", "null"))
                        
                        exams.append({
                            "title": exam_title,
                            "type": exam_type,
                            "id": exam_id,
                            "completion": completion_text,
                            "start_time": exam_start_time,
                            "is_started": exam_is_started,
                            "end_time": exam_end_time,
                            "is_closed": exam_is_closed,
                            "uploads": uploads
                        })
                        

                    classrooms = []
                    for classroom in classrooms_list:
                        classroom_title = classroom.get("title", "null")
                        classroom_type = type_map.get(classroom.get("type", "null"), classroom.get("type", "null"))
                        classroom_id = classroom.get("id", "null")
                        classroom_status = classroom.get("status")
                        
                        for classroom_completeness in classrooms_completeness:
                            if classroom_completeness.get("activity_id") == classroom_id:
                                classroom_completeness_status = "full"
                                break
                        else:
                            classroom_completeness_status = ""

                        classroom_start_time: str = transform_time(classroom.get("start_at"))

                        classroom_status_text = get_classroom_status_json(classroom_status)
                        classroom_completeness_status_text = get_classroom_completion_json(classroom_completeness_status)

                        classrooms.append({
                            "title": classroom_title,
                            "type": classroom_type,
                            "id": classroom_id,
                            "start_time": classroom_start_time,
                            "status": classroom_status_text,
                            "completion": classroom_completeness_status_text
                        })
                    
                    modules.append({
                        "name": module_name,
                        "activities": activities,
                        "exams": exams,
                        "classroom_tests": classrooms
                    })
            else:
                for index, module in enumerate(modules_list):
                    module_name = module.get("name", "null")
                    module_id = module.get("id", "null")

                    modules.append({
                        "index": index,
                        "id": module_id,
                        "name": module_name
                    })
            
            result = {
                "course_name": course_name,
                "course_id": course_id,
                "modules": modules
            }

            print_with_json(True, "Syllabus View", result)

            return 

        # 装填树状图
        course_tree = Tree(f"[bold yellow]{course_name}[/bold yellow][dim] 课程ID: {course_id}[/dim]")
        
        if modules_id or indices or last:
            # _index is unused, thus named with a prefix "_"
            for _, (module, activities_list, exams_list, classrooms_list) in enumerate(course_modules_node_list):
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
                    completion_status = activity_id in activities_completeness
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
                        (" [ID: ", "bright_white"),
                        (f"{activity_id}", "green"),
                        ("]", "bright_white"),
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

                    else:
                        panel_title = f"[white][{activity_type}][/white]"

                    activity_panel = Panel(
                        Group(*content_renderables),
                        title=panel_title,
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
                    completion_status = exam_id in exams_completeness

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
                        (" [ID: ", "bright_white"),
                        (f"{exam_id}", "green"),
                        ("]", "bright_white"),
                        "\n",
                        completion_text,
                        status_text
                    )
                    content_renderables.append(title_line)
                    content_renderables.append(start_time_text)
                    content_renderables.append(end_time_text)
                    content_renderables.append(url_jump_text)

                    panel_title = f"[yellow][{exam_type}][/yellow]"

                    activity_panel = Panel(
                        Group(*content_renderables),
                        title=panel_title,
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
                    
                    for classroom_completeness in classrooms_completeness:
                        if classroom_completeness.get("activity_id") == classroom_id:
                            classroom_completeness_status = "full"
                            break
                    else:
                        classroom_completeness_status = ""

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
                        (" [ID: ", "bright_white"),
                        (f"{classroom_id}", "green"),
                        ("]", "bright_white"),
                        "\n",
                        classroom_completeness_status_text,
                        classroom_status_text
                    )
                    content_renderables.append(title_line)
                    content_renderables.append(start_time_text)
                    content_renderables.append("")
                    content_renderables.append(prompt_text)

                    panel_title = f"[yellow][{classroom_type}][/yellow]"

                    classroom_panel = Panel(
                        Group(*content_renderables),
                        title=panel_title,
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

@view_app.command(
        "cw",
        hidden=True,
        help="Alias for 'coursewares'",
        epilog=dedent("""
            EXAMPLES:
 
              $ lazy course view coursewares 114514 -A -q    
                (查看课程所有资源并只输出文件ID)
            
              $ lazy course view coursewares 114514 -p 2 -a 5
                (查看第 2 页，每页显示 5 个结果)
        """),
        no_args_is_help=True)
@view_app.command(
        "coursewares",
        help="查看课程资源与课件",
        epilog=dedent("""
            EXAMPLES:
 
              $ lazy course view coursewares 114514 -A -q    
                (查看课程所有资源并只输出文件ID)
            
              $ lazy course view coursewares 114514 -p 2 -a 5
                (查看第 2 页，每页显示 5 个结果)
        """),
        no_args_is_help=True)
@partial(syncify, raise_sync_error=False)
async def view_coursewares(
    course_id: Annotated[int, typer.Argument(help="课程ID")],
    page: Annotated[Optional[int], typer.Option("--page", "-p", help="页面索引")] = 1,
    page_size: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示课件数量")] = 10,
    short: Annotated[Optional[bool], typer.Option("--short", "-s", help="启用此选项，简化输出，仅显示文件名与文件ID")] = False,
    quiet: Annotated[Optional[bool], typer.Option("--quiet", "-q", help="启用此选项，仅输出文件ID")] = False,
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此选项，输出所有结果")] = False,
    json: Annotated[Optional[bool], typer.Option("--json", "-J", hidden=True)] = False
):
    """
    查看课程资源与课件，并按条件筛选。

    默认按分页显示（每页10条）。
    使用 -A 来获取所有结果（这将忽略 -p 和 -a）。
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=json
    ) as progress:
        cookies = CredentialManager().load_cookies()
        if not cookies:
            if json:
                print_with_json(False, "Cookies is unacceptable.")
            else:
                rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)

        task = progress.add_task(description="获取课程信息中...", total=2)

        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            # 预请求，检查一下有多少章节
            pre_raw_coursewares = (await zju_api.coursewaresViewAPIFits(client.session, course_id, 1, 1).get_api_data())[0]
            total_syllabuses = pre_raw_coursewares.get("total", 0)
            
            if total_syllabuses == 0:
                if json:
                    print_with_json(True, "Not Found Coursewares")
                else:
                    rprint("当前还没有课件哦~\\( ^ ω ^ )/")
                
                return

            # 一次性拉取所有章节
            raw_coursewares = (await zju_api.coursewaresViewAPIFits(client.session, course_id, 1, total_syllabuses).get_api_data())[0]
        
        progress.update(task, description="渲染任务信息中...", advance=1)

        # 提取并拼装所有文件
        coursewares_list: List[dict] = raw_coursewares.get("activities", [])
        coursewares_uploads: List[dict] = []
        for courseware in coursewares_list:
            coursewares_uploads.extend(courseware.get("uploads", []))

        total: int = len(coursewares_uploads)
        if all:
            page_size = total

        pages: int = math.ceil(total / page_size)

        if page > pages:
            if json:
                print_with_json(False, f"Index Exceeded! Index page {page} of {total}")
            else:
                rprint(f"当前仅有 {pages} 页，你都索引到 {page} 页啦！[○･｀Д´･ ○]")
            
            raise typer.Exit(code=1)
        
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        coursewares_uploads_shown = coursewares_uploads[start_index: end_index]

        if quiet:
            courseware_ids = [str(courseware_upload.get("id", "null")) for courseware_upload in coursewares_uploads_shown]
            if json:
                print_with_json(True, "Courses List", courseware_ids)
            else:
                print(" ".join(courseware_ids))
            
            return

        # --- JSON FORMAT HEAD ---
        if json:
            results = []
            for courseware_upload in coursewares_uploads_shown:
                courseware_id          = str(courseware_upload.get("id", "null"))
                courseware_name        = courseware_upload.get("name", "null")
                if short:
                    results.append({
                        "id": courseware_id,
                        "name": courseware_name
                    })

                    continue
                
                courseware_size        = filesize.decimal(courseware_upload.get("size", 0))
                courseware_update_time = transform_time(courseware_upload.get("updated_at", "1900-01-01T00:00:00Z"))

                results.append({
                    "id": courseware_id,
                    "name": courseware_name,
                    "size": courseware_size,
                    "update_time": courseware_update_time
                })

            print_with_json(True, "Coursewares View", results)
            return
        # --- JSON FORMAT END ---

        # --- 准备表格 ---
        coursewares_table = Table(
            title=f"资源列表 (第 {page} / {pages} 页)",
            caption=f"本页显示 {len(coursewares_uploads_shown)} 个，共 {total} 个结果。",
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

        for courseware_upload in coursewares_uploads_shown:
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

@view_app.command(
        "mb",
        help="Alias for 'members'",
        hidden=True,
        epilog=dedent("""
            EXAMPLES:

              $ lazy course view members 114514    
                (查看课程成员名单)
                      
              $ lazy course view members 114514 -I 
                (只查看课程教师)          
        """),
        no_args_is_help=True)
@view_app.command(
        "members",
        help="查看课程教师与学生",
        epilog=dedent("""
            EXAMPLES:

              $ lazy course view members 114514    
                (查看课程成员名单)
                      
              $ lazy course view members 114514 -I 
                (只查看课程教师)    
        """),
        no_args_is_help=True)
@partial(syncify, raise_sync_error=False)
async def view_members(
    course_id: Annotated[int, typer.Argument(help="课程ID")],
    instructor: Annotated[Optional[bool], typer.Option("--instructor", "-I", help="启用此选项，只输出教师")] = False,
    student: Annotated[Optional[bool], typer.Option("--student", "-S", help="启用此选项，只输出学生")] = False,
    json: Annotated[Optional[bool], typer.Option("--json", "-J", hidden=True)] = False
):
    """
    查看课程教师与学生，并按条件筛选。

    默认同时展示教师与学生，你可以通过 -I 或 -S 来指定输出教师还是学生，两个选项互斥。
    """
    if instructor and student:
        rprint("[red](#`Д´)ﾉ不可以同时'只'输出啦！[/red]")
        raise typer.Exit(code=1)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=json
    ) as progress:
        cookies = CredentialManager().load_cookies()
        if not cookies:
            if json:
                print_with_json(False, "Cookies is unacceptable.")
            else:
                rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)
        
        task = progress.add_task(description="请求数据中...", total=2)

        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            raw_course_enrollments = (await zju_api.courseMembersViewAPIFits(client.session, course_id).get_api_data())[0]

        progress.update(task, description="渲染任务信息中...", advance=1)
        course_enrollments = raw_course_enrollments.get("enrollments")

        if not course_enrollments:
            if json:
                print_with_json(True, "Not Found")
            else:
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
            if json:
                print_with_json(True, "No member chosen")
            else:
                rprint("[red]∑(✘Д✘๑ )呀，没有结果呢~[/red]")
            
            return 
        
        if json:
            result = {}

            if instructor_course_enrollments:
                result.update({
                    "instructor": instructor_course_enrollments
                })

            if student_course_enrollments:
                result.update({
                    "student": student_course_enrollments
                })

            print_with_json(True, "Members View", result)
        
            return 
        
        if instructor_course_enrollments:
                rprint(f"[cyan]教师: [/cyan]{', '.join(instructor_course_enrollments)}")
        
        if student_course_enrollments:
            rprint(f"[cyan]学生: [/cyan]{', '.join(student_course_enrollments)}")
        
        progress.update(task, description="渲染完成", advance=1)

@view_app.command(
    "rc",
    help="Alias for 'rollcalls'",
    hidden=True,
    epilog=dedent(
        """
        EXAMPLES:

            $ lazy course view rollcalls 114514
              (查看课程点名记录)    

            $ lazy course view rollcalls 114514 -A 
              (查看课程所有点名记录)

            $ lazy course view rollcalls 114514 -p 2 -a 5
              (查看课程点名记录，每页显示 5 个，显示第 2 页)

            $ lazy course view rollcalls 114514 -S
              (查看课程点名概况)
    """),
    no_args_is_help=True)
@view_app.command(
    "rollcalls",
    help="查看课程点名记录",
    epilog=dedent(
        """
        EXAMPLES:

            $ lazy course view rollcalls 114514
              (查看课程点名记录)    

            $ lazy course view rollcalls 114514 -A 
              (查看课程所有点名记录)

            $ lazy course view rollcalls 114514 -p 2 -a 5
              (查看课程点名记录，每页显示 5 个，显示第 2 页)

            $ lazy course view rollcalls 114514 -S
              (查看课程点名概况)
    """),
    no_args_is_help=True)
@partial(syncify, raise_sync_error=False)
async def view_rollcalls(
    course_id: Annotated[str, typer.Argument(help="课程id")],
    amount: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示点名记录的数量")] = 10,
    page_index: Annotated[Optional[int], typer.Option("--page", "-p", help="点名记录页面索引")] = 1,
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此参数，一次性输出所有结果")] = False,
    summary: Annotated[Optional[bool], typer.Option("--summary", "-S", help="启用此选项，统计点名情况")] = False,
    json: Annotated[Optional[bool], typer.Option("--json", "-J", hidden=True)] = False
):
    student_id = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_LAZ_STUDENTID_NAME)
    rollcall_type_map = {
        "radar": "雷达点名",
        "number": "数字点名"
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=json
    ) as progress:
        cookies = CredentialManager().load_cookies()
        if not cookies:
            if json:
                print_with_json(False, "Cookies is unacceptable.")
            else:
                rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)
        
        task = progress.add_task(description="请求数据中...", total=2)

        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            raw_course_rollcalls = (await zju_api.courseRollcallsViewAPIFits(client.session, course_id=course_id, student_id=student_id).get_api_data())[0]

        progress.update(task, description="渲染点名记录中...", completed=1)
        
        course_rollcalls: List[dict] = raw_course_rollcalls.get("rollcalls")

        if not course_rollcalls:
            if json:
                print_with_json(True, "Not Found Rollcalls history")
            else:
                rprint("暂无点名记录哦~")
            
            return 

        total_rollcalls_amount = len(course_rollcalls)

        if summary:
            on_call_rollcalls_amount = 0
            
            for rollcall in course_rollcalls:
                if rollcall.get("status") == "on_call_fine":
                    on_call_rollcalls_amount += 1

            if json:
                print_with_json(
                    True, 
                    "Rollcalls Summary",
                    {
                        "total": total_rollcalls_amount,
                        "on_call": on_call_rollcalls_amount
                    }
                )
            else:
                rprint(f"签到情况: 共 {total_rollcalls_amount} 次签到，[green]{on_call_rollcalls_amount}[/green] 次已到，[red]{total_rollcalls_amount - on_call_rollcalls_amount}[/red] 次未到")
            
            return

        shown_amount = total_rollcalls_amount if all else amount

        total_pages = int(total_rollcalls_amount / shown_amount) + 1
        offset = (page_index - 1) * shown_amount

        if page_index > total_pages:
            if json:
                print_with_json(False, f"Index Exceeded! Index page {page_index} of {total_pages}")
            else:
                rprint(f"页面索引超限！共 {total_pages} 页，你都索引到第 {page_index} 页啦！")
            
            raise typer.Exit(code=1)

        if 0 < amount < total_rollcalls_amount:
            course_rollcalls_shown = course_rollcalls[offset: offset + amount]
        else:
            course_rollcalls_shown = course_rollcalls

        # --- JSON FORMAT HEAD ---
        if json:
            results = []
            for rollcall in course_rollcalls_shown:
                rollcall_id = str(rollcall.get("rollcall_id", 0))
                rollcall_time = transform_time(rollcall.get("rollcall_time"))
                rollcall_type = rollcall_type_map.get(rollcall.get("source"), "None")

                if rollcall.get("status") == "on_call_fine":
                    rollcall_status_text = "Signed in"
                else:
                    if rollcall.get("rollcall_status") == "finished":   
                        rollcall_status_text = "No sign-in"
                    else:
                        rollcall_status_text = "In progress"

                results.append({
                    "id": rollcall_id,
                    "time": rollcall_time,
                    "type": rollcall_type,
                    "status": rollcall_status_text
                })

            print_with_json(True, "Rollcalls View", results)
            return 
        # --- JSON FORMAT END ---

        rollcalls_table = Table(
            title=f"课程点名记录 (第 {page_index} / {total_pages})",
            caption=f"共 {total_rollcalls_amount} 条记录，本页显示 {len(course_rollcalls_shown)}",
            border_style="bright_black",
            show_header=True,
            header_style="bold magenta",
            expand=True
        )

        rollcalls_table.add_column("任务ID", style="cyan")
        rollcalls_table.add_column("签到时间")
        rollcalls_table.add_column("任务签到状态")
        rollcalls_table.add_column("签到类型")

        for rollcall in course_rollcalls_shown:
            rollcall_id = str(rollcall.get("rollcall_id", 0))
            rollcall_time = transform_time(rollcall.get("rollcall_time"))
            rollcall_type = rollcall_type_map.get(rollcall.get("source"), "None")

            if rollcall.get("status") == "on_call_fine":
                rollcall_status_text = Text(
                    "√ 已签到",
                    "green"
                )
            else:
                if rollcall.get("rollcall_status") == "finished":   
                    rollcall_status_text = Text(
                        "✘ 未签到",
                        "red"
                    )
                else:
                    rollcall_status_text = Text(
                        "！ 待签到",
                        "yellow"
                    )

            rollcalls_table.add_row(
                rollcall_id,
                rollcall_time,
                rollcall_status_text,
                rollcall_type
            )
        
        progress.update(task, completed=2)

    rprint(rollcalls_table)


# view 注册入课程命令组
app.add_typer(view_app, name="view", help="管理学在浙大课程的查看")
