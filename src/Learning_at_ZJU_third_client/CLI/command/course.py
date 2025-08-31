import typer
from typing_extensions import Optional, Annotated
from requests import Session
from rich import print as rprint

from zjuAPI import zju_api
from ..state import state

# courses 命令组
app = typer.Typer(help="""
学在浙大课程相关命令组，提供了对课程的查询与对课程章节查看的功能。
""")

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