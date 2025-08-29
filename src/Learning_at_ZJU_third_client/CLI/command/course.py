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

# 注册课程搜素命令
@app.command("search", help="搜索指定的课程，搜索结果会以表单的形式呈现。")
def search_courses(
    keyword: Annotated[str, typer.Argument(help="课程搜索关键字")]
    ):
    courses_searcher = zju_api.coursesAPIFits(state.client.session, keyword=keyword)
    search_results = courses_searcher.get_api_data()[0]
    search_results_amount = search_results.get("total", 0)
    rprint(f"搜索结果共 [green]{search_results_amount}[/green] 个")

    # 如果搜索没有结果，则直接退出
    if search_results_amount == 0:
        raise typer.Exit()
    
    course_results: list[dict] = search_results.get("courses", [])

    for course in course_results:
        course_name = course.get("name", "null")
        course_time = course.get("course_attributes", {}).get("teaching_class_name", "null") if course.get("course_attributes", {}) != None else "null"
        course_teachers = course.get("instructors", []) if course.get("instructors", []) != None else []
        course_department = course.get("department", {}).get("name", "null") if course.get("department", {}) != None else "null"
        course_academic_year = course.get("academic_year", {}).get("name", "null") if course.get("academic_year", {}) else "null"
        course_code = course.get("course_code", "null")
        course_id = course.get("id", "null")

        teachers_name = []
        for teacher in course_teachers:
            name = teacher.get("name", "null")
            teachers_name.append(name)

        if teachers_name == []:
            teachers_name.append("null")

        print("----------------------------------------")
        rprint(f"[bright_yellow]{course_name}[/bright_yellow]")
        rprint(f"  [green]课程ID: [/green]  [cyan]{course_id}[/cyan]")
        rprint(f"  [green]上课时间: [/green][cyan]{course_time}[/cyan]")
        rprint(f"  [green]授课教师: [/green]{'、'.join(teachers_name)}")
        rprint(f"  [green]开课院系: [/green]{course_department}")
        rprint(f"  [green]开课学年: [/green][white]{course_academic_year}[/white]")
        rprint(f"  [green]课程代码：[/green][bright_black]{course_code}[/bright_black]")

    print("----------------------------------------")