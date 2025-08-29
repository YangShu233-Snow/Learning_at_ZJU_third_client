import typer
from typing_extensions import Optional, Annotated, List
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn
from datetime import datetime
from pathlib import Path

from zjuAPI import zju_api
from upload import submit
from printlog.print_log import print_log
from ..state import state

# assignment 命令组
app = typer.Typer(help="""
                  学在浙大作业任务相关命令，可以查看待完成的任务，提交作业等。

                  暂时不支持对测试与考试的提交。
                  """)