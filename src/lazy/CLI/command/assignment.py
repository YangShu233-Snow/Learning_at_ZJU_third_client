import asyncio
import logging
from datetime import datetime, timezone
from functools import partial
from textwrap import dedent
from typing import Annotated, Dict, Callable
from enum import Enum, unique

import keyring
import typer
from asyncer import syncify
from lxml import html
from lxml.html import HtmlElement
from rich import filesize
from rich import print as rprint
from rich.align import Align
from rich.console import Group
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from ...login.login import CredentialManager, ZjuAsyncClient
from ...zjuAPI import zju_api
from ..config.config import type_map
from ..state import state
from ..utils.utils import (
    get_status_text,
    make_jump_url,
    print_with_json,
    transform_time,
)

KEYRING_SERVICE_NAME = "lazy"
KEYRING_LAZ_STUDENTID_NAME = "laz_studentid"

# assignment 命令组
app = typer.Typer(help="""
                  学在浙大作业任务相关命令，可以查看待完成的任务，提交作业等。

                  暂时不支持对测试与考试的提交。
                  """,
                  no_args_is_help=True
                  )

logger = logging.getLogger(__name__)

@unique
class AssignmentType(Enum):
    UNKOWN = 0
    ACTIVITY = 1
    FORMUN = 2
    EXAM = 3
    CLASSROOM = 4
    
def is_todo_show_amount_valid(amount: int):
    if amount <= 0:
        print("显示数量应为正数！")
        raise typer.Exit(code=1)
    
    return amount

def extract_comment(raw_content: str|None)->str:
    if not raw_content or not raw_content.strip():
        return ""
    
    doc: HtmlElement = html.fromstring(raw_content)
    return doc.text_content()

def extract_uploads_json(uploads_list: list[dict])->list[dict]:
    uploads = []

    for upload in uploads_list:
        file_name = upload.get("name", "null")
        file_id = upload.get("id", "null")
        file_size = filesize.decimal(upload.get("size", 0))
        
        uploads.append({
            "filename": file_name,
            "id": file_id,
            "file_size": file_size
        })

    return uploads

def extract_uploads(uploads_list: list[dict])->list[Table]:
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

def extract_subjects_json(subjects: list[dict], subject_type_map: dict)->list[dict]|None:
    subjects_list = []
    
    if not subjects:
        return None
    
       
    for index, subject in enumerate(subjects):
        subject_description: str = subject.get("description")
        subject_point: int = subject.get("point", 0)
        subject_type: str = subject_type_map.get(subject.get("type"), subject.get("type"))
        subject_options: list[str] = []
        subject_answers: list[str] = []

        if subject_type == "填空":
            answers: list[dict] = subject.get("correct_answers", [])
            for answer in answers:
                answer_content = answer.get("content")
                subject_answers.append(f"{answer_content}")

        for option_index, option in enumerate(subject.get("options"), start=65):
            raw_content = extract_comment(option.get("content"))
            is_answer: bool = option.get("is_answer", False)
            
            if is_answer:
                subject_answers.append(f"{chr(option_index)}. {raw_content}")
                subject_options.append(f"{chr(option_index)}. {raw_content}")
            else:
                subject_options.append(f"{chr(option_index)}. {raw_content}")

        subject_note = subject.get("note")
        subject_json = {
            "index": index,
            "type": subject_type,
            "point": subject_point,
            "content": subject_description,
            "options": subject_options,
            "answer": ' '.join(subject_answers),
            "note": subject_note
        }

        subjects_list.append(subject_json)

    return subjects_list

def extract_subjects(subjects: list[dict], subject_type_map: dict)->list[Text|Padding|str]:
    content_renderables = []
    if not subjects:
        return ""
    
    for index, subject in enumerate(subjects):
        subject_description: str = extract_comment(subject.get("description"))
        subject_point: int = subject.get("point", 0)
        subject_type: str = subject_type_map.get(subject.get("type"), subject.get("type"))
        subject_options: list[str] = []
        subject_answers: list[str] = []

        if subject_type == "填空":
            answers: list[dict] = subject.get("correct_answers", [])
            for answer in answers:
                answer_content = answer.get("content")
                subject_answers.append(f"{answer_content}")

        for option_index, option in enumerate(subject.get("options"), start=65):
            raw_content = extract_comment(option.get("content"))
            is_answer: bool = option.get("is_answer", False)
            
            if is_answer:
                subject_options.append(f"[green]{chr(option_index)}. {raw_content}[/green]")
            else:
                subject_options.append(f"{chr(option_index)}. {raw_content}")

        subject_note = subject.get("note")

        if subject_note:
            subject_head_note = Text(subject_note, "dim")

        subject_text = Text.assemble(
            (f"[{subject_type}]", "green"),
            (f"({subject_point}分) ", "white"),
            (f"{index + 1}. {subject_description}", "white")
        )

        if subject_options:
            subject_options_text = Padding('\n'.join(subject_options), (0, 0, 0, 2))

        if subject_answers:
            subject_answers_text = Padding(f"答案: {' '.join(subject_answers)}", (0, 0, 0, 2), style="green")

        if subject_note:
            content_renderables.append(subject_head_note)
        
        content_renderables.append(subject_text)

        if subject_options:
            content_renderables.append(subject_options_text)

        if subject_answers:
            content_renderables.append(subject_answers_text)

        if subject != subjects[-1]:
            content_renderables.append("")

    return content_renderables

def parse_files_id(files_id: str)->list[int]:
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
        typer.echo("文件ID格式有误！", err=True)
        raise typer.Exit(code=1) from e
    
    return list(set(files_id_list))

async def guess_assignment_type(assignment_id: int, json: bool)->AssignmentType:
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
                logger.error("Cookies不存在！")
                raise typer.Exit(code=1)
            
            rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)
        
        task = progress.add_task(description="正在猜测任务类型...",total=1)

        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            raw_activity, raw_exam, raw_classroom = await asyncio.gather(*[
                zju_api.assignmentViewAPIFits(client.session, assignment_id).get_api_data(),
                zju_api.assignmentExamViewAPIFits(client.session, assignment_id, apis_name=["exam"]).get_api_data(),
                zju_api.assignmentClassroomViewAPIFits(client.session, assignment_id, apis_name=["classroom"]).get_api_data()
            ], return_exceptions=True)

        if raw_activity[0]:
            if raw_activity[0].get("type") == "forum":
                progress.update(task, description="猜测是作业!", completed=1)
                logger.info(f"猜测 {assignment_id} 为 Activity")    
                return AssignmentType.FORMUN
            
            progress.update(task, description="猜测是作业!", completed=1)
            logger.info(f"猜测 {assignment_id} 为 Activity")
            return AssignmentType.ACTIVITY
        
        
        if isinstance(raw_exam, list) and raw_exam and raw_exam[0]:
            progress.update(task, description="猜测是测试!", completed=1)
            logger.info(f"猜测 {assignment_id} 为 Exam")
            return AssignmentType.EXAM
        
        
        if isinstance(raw_classroom, list) and raw_classroom and raw_classroom[0]:
            progress.update(task, description="猜测是课堂任务!", completed=1)
            logger.info(f"猜测 {assignment_id} 为 Classroom")
            return AssignmentType.CLASSROOM
    
    return AssignmentType.UNKOWN

async def view_exam(exam_id: int, type_map: dict, preview: bool, json: bool):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=json
    ) as progress:
        task = progress.add_task(description="请求数据中...", total=2)
        cookies = CredentialManager().load_cookies()
        if not cookies:
            if json:
                print_with_json(False, "Cookies is unacceptable.")
                logger.error("Cookies不存在！")
                raise typer.Exit(code=1)
            
            rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)
        
        # --- 请求阶段 ---
        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            raw_exam, raw_exam_submission_list, raw_exam_distribute = await zju_api.assignmentExamViewAPIFits(client.session, exam_id).get_api_data()
        
            if not raw_exam:
                if json:
                    print_with_json(False, f"Exam whose ID {exam_id} does not exist.")
                    raise typer.Exit(code=1)
                
                rprint(f"[red]请求测试 [green]{exam_id}[/green] 不存在！[/red]")
                raise typer.Exit(code=1)

            if not raw_exam_distribute and raw_exam_submission_list:
                head_submission_id = raw_exam_submission_list.get("submissions")[0].get("id")
                raw_exam_submission_subjects = (await zju_api.assignmentExanSubmissionViewAPIFits(client.session, exam_id, head_submission_id).get_api_data())[0]
            else:
                raw_exam_submission_subjects = {}

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
        exam_submit_times_limit: int|str = raw_exam.get("submit_times", "N/A") if raw_exam.get("submit_times", "N/A") != 0 else '\u221E'
        exam_submitted_times: int = raw_exam.get("submitted_times", 0)

        # 开放时间
        exam_start_time: str = transform_time(raw_exam.get("start_time"))

        # 结束时间
        exam_end_time: str = transform_time(raw_exam.get("end_time"))


        # --- JSON FORMAT HEAD ---
        if json:
            if preview:            
                if not raw_exam_distribute and not raw_exam_submission_subjects.get("subjects_data"):
                    preview_content = "Preview Failed."
                else:
                    if raw_exam_distribute:
                        exam_subjects: list[dict] = raw_exam_distribute.get("subjects", [])
                    else:
                        exam_subjects: list[dict] = raw_exam_submission_subjects.get("subjects_data").get("subjects")
                    
                    subject_type_map = {
                        "single_selection": "单选",
                        "short_answer": "简答",
                        "multiple_selection": "多选",
                        "true_or_false": "判断",
                        "fill_in_blank": "填空"
                    }

                    preview_content = extract_subjects_json(exam_subjects, subject_type_map, json)

            if raw_exam_submission_list:
                # 测试最终成绩
                exam_final_score: int|None = raw_exam_submission_list.get("exam_final_score")
                if not exam_final_score:
                    exam_final_score: int|str = raw_exam_submission_list.get("exam_score") if raw_exam_submission_list.get("exam_score") else "null"
            
                submissions_list = []
                exam_submission_list: list[dict] = raw_exam_submission_list.get("submissions")

                for submission in exam_submission_list:
                    submission_submitted_time = submission.get("submitted_at")
                    submission_score = submission.get("score") if submission.get("score") else "未公布"

                    if submission_submitted_time:
                        submission_submitted_time = datetime.fromisoformat(exam_end_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        submission_submitted_time = "null"

                    submissions_list.append({
                        "submmited_time": submission_submitted_time,
                        "score": submission_score
                    })
            else:
                exam_final_score = None
                submissions_list = None

            result = {
                "title": exam_title,
                "total_points": exam_total_points,
                "type": exam_type,
                "start_status": exam_start_status,
                "start_time": exam_start_time,
                "close_status": exam_close_status,
                "end_time": exam_end_time,
                "description": exam_description,
                "submit_time_limit": exam_submit_times_limit,
                "submitted_times": exam_submitted_times,
                "final_score": exam_final_score,
                "submissions": submissions_list,
                "preview": preview_content
            }

            print_with_json(True, "Exam View", result)
            return 
        # --- JSON FORMAT END ---

        # --- 解析预览内容 ---
        if preview:
            exam_subjects_renderables = []
            
            if not raw_exam_distribute and not raw_exam_submission_subjects.get("subjects_data"):
                preview_error_text = Text.assemble(
                    ("(╥╯^╰╥) 预览失效了……", "red"),
                    "\n",
                    ("测试未开放、测试已结束但未公布或作答次数达到上限等情况均无法预览题目。", "dim")
                )

                exam_subjects_renderables.append(preview_error_text)
            else:
                if raw_exam_distribute:
                    exam_subjects: list[dict] = raw_exam_distribute.get("subjects", [])
                else:
                    exam_subjects: list[dict] = raw_exam_submission_subjects.get("subjects_data").get("subjects")
            
                subject_type_map = {
                    "single_selection": "单选",
                    "short_answer": "简答",
                    "multiple_selection": "多选",
                    "true_or_false": "判断",
                    "fill_in_blank": "填空"
                }

                exam_subjects_renderables = extract_subjects(exam_subjects, subject_type_map)

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

        # --- 解析提交列表 ---
        if raw_exam_submission_list:
            exam_final_score: int|None = raw_exam_submission_list.get("exam_final_score")
            if not exam_final_score:
                exam_final_score: int|str = raw_exam_submission_list.get("exam_score") if raw_exam_submission_list.get("exam_score") else "null"
            
            submission_content_renderables = []
            exam_submission_list: list[dict] = raw_exam_submission_list.get("submissions")

            for submission in exam_submission_list:
                submission_submitted_time = submission.get("submitted_at")
                submission_score = submission.get("score") if submission.get("score") else "未公布"

                if submission_submitted_time:
                    submission_submitted_time = datetime.fromisoformat(submission_submitted_time.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    submission_submitted_time = "null"

                # --- 准备Panel内容 ---
                submission_head_text = Text.assemble(
                    ("提交时间: ", "cyan"),
                    (f"{submission_submitted_time}", "bright_white"),
                    "\n",
                    ("测试得分: ", "bright_magenta"),
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

        # --- 解析预览内容 ---
        if preview:
            exam_subjects_renderables = []
            
            if not raw_exam_distribute and not (raw_exam_submission_subjects and raw_exam_submission_subjects.get("subjects_data")):
                preview_error_text = Text.assemble(
                    ("(╥╯^╰╥) 预览失效了……", "red"),
                    "\n",
                    ("测试未开放、测试已结束但未公布或作答次数达到上限等情况均无法预览题目。", "dim")
                )

                exam_subjects_renderables.append(preview_error_text)
            else:
                if raw_exam_distribute:
                    exam_subjects: list[dict] = raw_exam_distribute.get("subjects", [])
                else:
                    exam_subjects: list[dict] = raw_exam_submission_subjects.get("subjects_data").get("subjects")
                
                subject_type_map = {
                    "single_selection": "单选",
                    "short_answer": "简答",
                    "multiple_selection": "多选",
                    "true_or_false": "判断",
                    "fill_in_blank": "填空"
                }

                exam_subjects_renderables = extract_subjects(exam_subjects, subject_type_map)

            
            exam_preview_subjects_panel = Panel(
                Group(*exam_subjects_renderables),
                title = "[yellow][内容预览][/yellow]",
                border_style="cyan",
                expand=True,
                padding=(1, 2)
            )
            
            content_renderables.append("")
            content_renderables.append(exam_preview_subjects_panel)

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

async def view_classroom(
        classroom_id: int, 
        type_map: dict, 
        preview: bool,
        json: bool
    ):

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=json
    ) as progress:
        task = progress.add_task(description="请求数据中...", total=2)
        cookies = CredentialManager().load_cookies()
        
        if not cookies:
            if json:
                print_with_json(False, "Cookies is unacceptable.")
                logger.error("Cookies不存在！")
                raise typer.Exit(code=1)
            
            rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)
        
        # --- 请求阶段 ---
        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            # 请求classroom与classroom submission数据
            classroom_message, raw_classroom_submissions_list, raw_classroom_subjects_result, raw_classroom_subjects = await zju_api.assignmentClassroomViewAPIFits(client.session, classroom_id).get_api_data()

            if not classroom_message:
                if json:
                    print_with_json(False, f"Classroom Test whose ID {classroom_id} does not exist.")
                    raise typer.Exit(code=1)
                
                rprint(f"[red]请求课堂测试 [green]{classroom_id}[/green] 不存在！[/red]")
                raise typer.Exit(code=1)
            
            if classroom_message.get("subjects_count") > 0:
                classroom_submissions_list: list[dict] = raw_classroom_submissions_list.get("submissions", [])
            else: 
                classroom_submissions_list = []
        
        progress.advance(task, 1)
        progress.update(task, description="渲染数据中...")

        # --- 渲染阶段 ---
        classroom_title: str = classroom_message.get("title") if classroom_message.get("title") else "null"
        classroom_type: str = type_map.get(classroom_message.get("type"), classroom_message.get("type"))
        
        classroom_start_time = transform_time(classroom_message.get("start_at"))
        classroom_finish_time = transform_time(classroom_message.get("finish_at"))

        # --- JSON FORMAT HEAD ---
        if json:
            # --- 解析提交列表 ---
            if classroom_submissions_list:
                submissions_list = []
                
                for submission in classroom_submissions_list:
                    submission_created_time = transform_time(submission.get("created_at"))
                    submission_score: int|str = submission.get("quiz_score") if submission.get("quiz_score") else "null"

                    submissions_list.append({
                        "submitted_time": submission_created_time,
                        "score": submission_score
                    })
            else:
                submissions_list = None

            # --- 解析预览内容 ---
            if preview:
                if not raw_classroom_subjects_result and not raw_classroom_subjects:
                    preview_content = "Preview Failed."
                else:
                    if raw_classroom_subjects_result.get("correct_answers_data", {}).get("correct_answers"):
                        classroom_subjects: list[dict] = raw_classroom_subjects_result.get("subjects_data", {}).get("subjects", [])
                    else:
                        classroom_subjects: list[dict] = raw_classroom_subjects.get("subjects")
                                    
                    subject_type_map = {
                        "single_selection": "单选",
                        "short_answer": "简答",
                        "multiple_selection": "多选",
                        "true_or_false": "判断",
                        "fill_in_blank": "填空"
                    }

                    preview_content = extract_subjects_json(classroom_subjects, subject_type_map)
            
            result = {
                "title": classroom_title,
                "type": classroom_type,
                "start_time": classroom_start_time,
                "end_time": classroom_finish_time,
                "submissions": submissions_list,
                "preview": preview_content

            }

            print_with_json(True, "Classroom Test View", result)
            return 
        # --- JSON FORMAT END ---

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
        
        # --- 解析提交列表 ---
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

        # --- 解析预览内容 ---
        if preview:
            classroom_subjects_renderables = []

            if not raw_classroom_subjects_result and not raw_classroom_subjects:
                preview_error_text = Text.assemble(
                    ("(╥╯^╰╥) 预览失效了……", "red"),
                    "\n",
                    ("未知错误导致无法预览题目。", "dim")
                )

                classroom_subjects_renderables.append(preview_error_text)
            else:
                if raw_classroom_subjects_result.get("correct_answers_data", {}).get("correct_answers"):
                    classroom_subjects: list[dict] = raw_classroom_subjects_result.get("subjects_data", {}).get("subjects", [])
                else:
                    classroom_subjects: list[dict] = raw_classroom_subjects.get("subjects")
                                
                subject_type_map = {
                    "single_selection": "单选",
                    "short_answer": "简答",
                    "multiple_selection": "多选",
                    "true_or_false": "判断",
                    "fill_in_blank": "填空"
                }

                classroom_subjects_renderables = extract_subjects(classroom_subjects, subject_type_map)

            classroom_preview_subjects_panel = Panel(
                Group(*classroom_subjects_renderables),
                title = "[yellow][内容预览][/yellow]",
                border_style="cyan",
                expand=True,
                padding=(1, 2)
            )

            content_renderables.append("")
            content_renderables.append(classroom_preview_subjects_panel)

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

async def view_activity(
        activity_id: int, 
        type_map: dict,
        json: bool
    ):

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=json
    ) as progress:
        
        task = progress.add_task(description="请求数据中...", total=1)

        cookies = CredentialManager().load_cookies()
        if not cookies:
            if json:
                print_with_json(False, "Cookies is unacceptable.")
                logger.error("Cookies不存在！")
                raise typer.Exit(code=1)
            
            rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)

        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            # --- 请求阶段 ---
            # 请求预览数据
            # raw_activity_read: dict = (await zju_api.assignmentPreviewAPIFits(client.session, activity_id).post_api_data())[0]
            
            student_id = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_LAZ_STUDENTID_NAME)
            
            if not student_id:
                logger.error(f"{activity_id} 缺少'laz_studentid'参数，请将此问题上报给开发者！")
                if json:
                    print_with_json(False, "STUDENT_ID does not exist. Report it to developer,")
                    raise typer.Exit(code=1)
                
                print(f"{activity_id} 返回存在问题！")
                raise typer.Exit(code=1)

            # 请求主体数据
            raw_activity = (await zju_api.assignmentViewAPIFits(client.session, activity_id).get_api_data())[0]
        
            activity_completion_criterion_key: str = raw_activity.get("completion_criterion_key", "none")
            
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
        activity_title                               = raw_activity.get("title", "null")
        activity_type                                = type_map.get(raw_activity.get("type", "null"), raw_activity.get("type", "null"))
        activity_highest_score: int                  = raw_activity.get("highest_score", 0) if raw_activity.get("highest_score", 0) is not None else "N/A"
        activity_description: str                    = extract_comment(raw_activity.get("data", {}).get("description", ""))
        activity_content: str                        = extract_comment(raw_activity.get("data", {}).get("content", ""))
        activity_all_students_average_score: int|str = raw_activity.get("average_score", "N/A")
        # 开放时间
        activity_start_time = transform_time(raw_activity.get("start_time"))
        
        # 截止日期
        activity_end_time = transform_time(raw_activity.get("end_time"))

        if json:
            # 读取提交列表（如果有的话）
            if raw_submission_list:
                # 准备Submission的Panel内容
                submissions = []
                submissions_list: list[dict] = raw_submission_list.get("list")
                
                for submission in submissions_list:
                    submission_created_time = datetime.fromisoformat(submission.get("created_at", "1900-01-01T00:00:00Z").replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                    submission_comment = submission.get("comment")
                    submission_instructor_comment: str = submission.get("instructor_comment", None)
                    submission_score: int|None = submission.get("score") if submission.get("score") else "未评分"
                    submission_uploads_list: list[dict]|None = submission.get("uploads", None)

                    if submission_uploads_list:
                        submission_uploads = extract_uploads_json(submission_uploads_list)
                    else:
                        submission_uploads = None
                    
                    submissions.append({
                        "submmited_time": submission_created_time,
                        "comment": submission_comment,
                        "instructor_comment": submission_instructor_comment,
                        "score": submission_score,
                        "uploads": submission_uploads
                    })
            else:
                submissions = None

            uploads_list = raw_activity.get("uploads", None)
            uploads = extract_uploads_json(uploads_list) if uploads_list else None

            result = {
                "title": activity_title,
                "type": activity_type,
                "start_time": activity_start_time,
                "end_time": activity_end_time,
                "description": raw_activity.get("data", {}).get("description", ""),
                "content": raw_activity.get("data", {}).get("description", ""),
                "highest_score": activity_highest_score,
                "all_students_average_score": activity_all_students_average_score,
                "uploads": uploads,
                "submissions": submissions
            }

            print_with_json(True, "Activity View", result)
            return 

        start_time_text = Text.assemble(
            ("开放时间: ", "cyan"),
            (activity_start_time, "bright_white")
        )
        end_time_text = Text.assemble(
            ("截止时间: ", "cyan"),
            (activity_end_time, "bright_white")
        )

        activity_description_text = Text.assemble(
            activity_description
        )
        activity_description_block = Padding(activity_description_text, (0, 0, 0, 2))

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
        uploads: list[dict] = raw_activity.get("uploads")
        if uploads:
            content_renderables.append("")
            content_renderables.extend(extract_uploads(uploads))

        # 读取提交列表（如果有的话）
        if raw_submission_list:
            
            # 准备Submission的Panel内容
            submission_content_renderables = []
            submission_list: list[dict] = raw_submission_list.get("list")
            
            for submission in submission_list:
                submission_created_time = datetime.fromisoformat(submission.get("created_at", "1900-01-01T00:00:00Z").replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                submission_comment = extract_comment(submission.get("comment"))
                submission_instructor_comment: str = submission.get("instructor_comment") or ""
                submission_score: int|None = submission.get("score") if submission.get("score") else "未评分"
                submission_uploads: list[dict]|list = submission.get("uploads", [])

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
                    ("得分: ", "bold bright_magenta"),
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

def view_forum(
    forum_id: int,
    type_map: dict,
    json: bool
):
    pass

@app.command(
    "vw",
    help="Alias for 'view'",
    hidden=True,
    epilog=dedent("""
        EXAMPLES:
        
          $ lazy assignment view 114514
            (查看ID为'114514'的任务内容)
            
          $ lazy assignment view 114514 -e -P
            (查看ID为'114514'的测试内容，并预览其测试题目)
    """),
    no_args_is_help=True)
@app.command(
    "view",
    help="查看任务内容",
    epilog=dedent("""
        EXAMPLES:
        
          $ lazy assignment view 114514
            (查看ID为'114514'的任务内容)
            
          $ lazy assignment view 114514 -e -P
            (查看ID为'114514'的测试内容，并预览其测试题目)
    """),
    no_args_is_help=True)
@partial(syncify, raise_sync_error=False)
async def view_assignment(
    assignment_id: Annotated[int, typer.Argument(help="任务id")],
    exam: Annotated[bool | None, typer.Option("--exam", "-e", help="启用此选项，将查询对应的考试")] = False,
    classroom: Annotated[bool | None, typer.Option("--classroom", "-c", help="启用此选项，将查询对应课堂任务")] = False,
    activity: Annotated[bool | None, typer.Option("--activity", "-H", help="启用此选项，将查询对应作业")] = False,
    forum: Annotated[bool | None, typer.Option("--forum", "-F", help="启用此选项，将查询对应讨论")] = False,
    preview: Annotated[bool | None, typer.Option("--preview", "-P", help="启用此选项，预览测试或课堂任务题目")] = False,
    json: Annotated[bool | None, typer.Option("--json", "-J", hidden=True)] = False
):
    """
    浏览指定任务，显示任务基本信息，任务附件与任务提交记录。

    通过指定 -c, -e, -H 来指定三种不同类型的任务，更推荐不指定此选项，lazy会自行判断任务类型。

    对于测试与课堂互动型的任务，使用 -P 可以预览其测试题目。
    """
    assignment_type = AssignmentType.UNKOWN

    # 猜测任务类型
    match (activity, forum, exam, classroom): 
        case (True, _, _, _): assignment_type = AssignmentType.ACTIVITY
        case (_, True, _, _): assignment_type = AssignmentType.FORMUN
        case (_, _, True, _): assignment_type = AssignmentType.EXAM
        case (_, _, _, True): assignment_type = AssignmentType.CLASSROOM
        case _: assignment_type =  await guess_assignment_type(assignment_id, json)

    if assignment_type == AssignmentType.UNKOWN:
        if json:
            print_with_json(True, f"Assignment {assignment_id} doesn't exist.")
        
        rprint(f"任务 {assignment_id} 不存在！")

    if assignment_type in (AssignmentType.ACTIVITY, AssignmentType.FORMUN) and preview:
        if json:
            print_with_json(False, "Assignment whose type is 'Activity' cannot be previewed.")
            raise typer.Exit(code=1)
        
        rprint("[red]'activity' 类型不可预览！[/red]")
        raise typer.Exit(code=1)
    
    # 统一一下接口方便调用
    async def view_activity_wrapper(activity_id: int, type_map: dict, _: bool, json: bool):
        return await view_activity(activity_id, type_map, json)
    
    async def view_forum_wrapper(activity_id: int, type_map: dict, _: bool, json: bool):
        return await view_forum(activity_id, type_map, json)

    view_callable_map: Dict[AssignmentType, Callable] = {
        AssignmentType.ACTIVITY: view_activity_wrapper,
        AssignmentType.FORMUN: view_forum_wrapper,
        AssignmentType.EXAM: view_exam,
        AssignmentType.CLASSROOM: view_classroom
    }

    await view_callable_map[assignment_type](assignment_id, type_map, preview, json)
    return

@app.command(
    "td",
    help="Alias for 'todo'",
    hidden=True,
    epilog=dedent("""
        EXAMPLES:
        
          $ lazy assignment todo -A       
            (查看所有待办事项清单)
        
          $ lazy assignment todo -p 2 -a 5
            (查看第 2 页，每页显示 5 个待办事项)
    """))
@app.command(
    "todo",
    help="查看任务待办清单",
    epilog=dedent("""
        EXAMPLES:
        
          $ lazy assignment todo -A       
            (查看所有待办事项清单)
        
          $ lazy assignment todo -p 2 -a 5
            (查看第 2 页，每页显示 5 个待办事项)
        
          $ lazy assignment todo -r       
            (反转排序顺序查看待办事项清单)
    """))
@partial(syncify, raise_sync_error=False)
async def todo_assignment(
    amount: Annotated[int | None, typer.Option("--amount", "-a", help="显示待办任务数量", callback=is_todo_show_amount_valid)] = 10,
    page_index: Annotated[int | None, typer.Option("--page", "-p", help="待办任务页面索引")] = 1,
    reverse: Annotated[bool | None, typer.Option("--reverse", "-r", help="以任务截止时间降序排列")] = False,
    all: Annotated[bool | None, typer.Option("--all", "-A", help="启用此选项，输出所有待办事项")] = False,
    json: Annotated[bool | None, typer.Option("--json", "-J", hidden=True)] = False
):
    """
    列举待办事项清单

    默认按分页显示，每页显示 10 个。
    使用 -A 来显示所有待办清单，这将忽略 -p 与 -a。

    默认以任务截止时间作为排序依据，越早截止，排序越靠前，使用 -r 来反转任务清单排序结果。
    """
    todo_panel_list = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        disable=json
    ) as progress:
        
        task = progress.add_task(description="获取待办事项信息中...", total=1)
        
        cookies = CredentialManager().load_cookies()
        if not cookies:
            if json:
                print_with_json(False, "Cookies is unacceptable.")
                logger.error("Cookies不存在！")
                raise typer.Exit(code=1)
            
            rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)

        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            raw_todo_list: dict = (await zju_api.assignmentTodoListAPIFits(client.session).get_api_data())[0]
        progress.advance(task, advance=1)

        task = progress.add_task(description="加载内容中...", total=1)

        todo_list: list[dict] = raw_todo_list.get("todo_list", [])
        
        if type(todo_list) != list:
            if json:
                print_with_json(False, "todo list resolving occur error.")
                raise typer.Exit(code=1)
            
            logger.error("todo_list存在错误，请将此日志上报给开发者！")
            print("待办事项清单解析存在异常！")
            raise typer.Exit(code=1)
        
        # 总任务数量
        total = len(todo_list)
        
        if total == 0:
            if json:
                print_with_json(True, "There are currently no todos.")
                return
            
            print("当前没有待办任务哦~")
            return 
        
        if not all:
            total_pages = int(total / amount) + 1
            if page_index > total_pages:
                if json:
                    print_with_json(False, f"Index Exceeded! Index page {page_index} of {total}")
                    raise typer.Exit(code=1)
                
                print(f"页面索引超限！共 {total} 页，你都索引到第 {page_index} 页啦！")
                raise typer.Exit(code=1)
        else:
            amount = total
            page_index = 1
            total_pages = 1

        # 依照截止时间排序
        todo_list = sorted(todo_list, key=lambda todo: datetime.fromisoformat(todo.get("end_time").replace('Z', '+00:00') if todo.get("end_time") else "3000-01-01T00:00:00+00:00"), reverse=reverse)

        start = amount * (page_index - 1)
        todo_list = todo_list[start:]

        json_result = []

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

            if json:
                json_todo = {
                    "title": title,
                    "course_name": course_name,
                    "course_id": course_id,
                    "todo_id": todo_id,
                    "end_time": end_time,
                    "todo_type": todo_type
                }

                json_result.append(json_todo)

            # 创建标题内容
            title_text = Text.assemble(
                (title, "bold bright_magenta"),
                (" [ID: ", "bright_white"),
                (f"{todo_id}", "green"),
                ("]", "bright_white"),
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
            
            panel_border_style = "bright_" + style if style != "dim" else "dim"

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
    
    if json:
        print_with_json(True, "Todo List", json_result)
        return 
    
    rprint(*todo_panel_list)
    print(f"本页共 {amount} 个结果，第 {page_index}/{total_pages} 页")

@app.command(
    "sm",
    help="Alias for 'submit'",
    hidden=True,
    epilog=dedent("""
        EXAMPLES:

          $ lazy assignment submit 114514 -t 'Hello World' 
            (向ID为'114514'的任务提交文本内容为'Hello World'的作业)
            
          $ lazy assignment submit 114514 -f '2333, 6666' 
            (向ID为'114514'的任务提交附件ID为'2333'和'6666'的作业)
    """),
    no_args_is_help=True)
@app.command(
    "submit",
    help="提交任务作业",
    epilog=dedent("""
        EXAMPLES:

          $ lazy assignment submit 114514 -t 'Hello World' 
            (向ID为'114514'的任务提交文本内容为'Hello World'的作业)
            
          $ lazy assignment submit 114514 -f '2333, 6666' 
            (向ID为'114514'的任务提交附件ID为'2333'和'6666'的作业)
    """),
    no_args_is_help=True)
@partial(syncify, raise_sync_error=False)
async def submit_assignment(
    activity_id: Annotated[int, typer.Argument(help="待提交任务ID")],
    text: Annotated[str | None, typer.Option("--text", "-t", help="待提交的文本内容")] = "",
    files_id: Annotated[str | None, typer.Option("--files", "-f", help="待上传附件ID", callback=parse_files_id)] = "",
    json: Annotated[bool | None, typer.Option("--json", "-J", hidden=True, help="启用JSON输出")] = False
):
    """
    提交学在浙大 Homeword 任务，支持传入文本与附件ID。

    在提交任务之前，请先将文件上传至学在浙大云盘，通过指定云盘文件ID来指定附件。

    通过 -f 传入文件ID时，请务必用引号包裹以避免 lazy 的意外行为，如果要传入多个文件，请使用半角逗号或空格分割。
    """
    if not text and not files_id:
        if json:
            print_with_json(False, "Cannot submit blank context.")
            raise typer.Exit(code=1)

        rprint("不可空提交！")
        raise typer.Exit(code=1)

    cookies = CredentialManager().load_cookies()
    if not cookies:
        if json:
            print_with_json(False, "Cookies is unacceptable.")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)
        
        rprint("Cookies不存在！")
        logger.error("Cookies不存在！")
        raise typer.Exit(code=1)

    async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
        status = await zju_api.assignmentSubmitAPIFits(client.session, activity_id, text, files_id).submit()
        
        if json:
            description = "Success" if status else "Failed"

            print_with_json(status=status, description=description)
            
            return

        if status:
            rprint("[green]提交成功！[/green]")
        else:
            rprint("[red]提交失败！[/red]")

@app.command(
    "op",
    help="Alias for 'open'",
    hidden=True,
    epilog=dedent("""
        EXAMPLES:

          $ lazy assignment open 114514 -T 'Hello World' -t 'Hello World' 
            (向版块ID为'114514'的讨论提交一个标题为'Hello World'，文本内容为'Hello World'的话题)
            
          $ lazy assignment submit 114514 -f '2333, 6666' 
            (向版块ID为'114514'的讨论提交一个标题为'Hello World'，附件ID为2333和6666的话题)
    """),
    no_args_is_help=True)
@app.command(
    "open",
    help="在讨论下发起一个新话题",
    epilog=dedent("""
        EXAMPLES:

          $ lazy assignment open 114514 -T 'Hello World' -t 'Hello World' 
            (向版块ID为'114514'的讨论提交一个标题为'Hello World'，文本内容为'Hello World'的话题)
            
          $ lazy assignment submit 114514 -f '2333, 6666' 
            (向版块ID为'114514'的讨论提交一个标题为'Hello World'，附件ID为2333和6666的话题)
    """),
    no_args_is_help=True)
@partial(syncify, raise_sync_error=False)
async def open_topic(
    category_id: Annotated[int, typer.Argument(help="版块ID")],
    title: Annotated[str, typer.Option("--title", "-T", help="话题标题")],
    text: Annotated[str | None, typer.Option("--text", "-t", help="待提交的文本内容")] = "",
    files_id: Annotated[str | None, typer.Option("--files", "-f", help="待上传附件ID", callback=parse_files_id)] = "",
    json: Annotated[bool | None, typer.Option("--json", "-J", hidden=True, help="启用JSON输出")] = False
):
    if not text and not files_id:
        if json:
            print_with_json(False, "Cannot open blank topic.")
            raise typer.Exit(code=1)

        rprint("不可创建一个空话题！")
        raise typer.Exit(code=1)
    
    cookies = CredentialManager().load_cookies()
    if not cookies:
        if json:
            print_with_json(False, "Cookies is unacceptable.")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)
        
        rprint("Cookies不存在！")
        logger.error("Cookies不存在！")
        raise typer.Exit(code=1)
    
    async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
        status = await zju_api.assignmentOpenForumTopicAPIFits(client.session, category_id, title, text, files_id).submit()
        
        if json:
            description = "Success" if status else "Failed"

            print_with_json(status=status, description=description)
            
            return

        if status:
            rprint("[green]提交成功！[/green]")
        else:
            rprint("[red]提交失败！[/red]")