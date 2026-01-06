from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print as rprint

from ...load_config.backup import BackupManager

app =  typer.Typer(help="管理 LAZY CLI 日志文件")

@app.command(
    "export",
    help="导出 LAZY CLI 本地日志文件"
)
def export(
    output_dir: Annotated[Optional[str], typer.Option("--dest", "-d", help="日志导出目录")] = Path.home()
):
    mannager = BackupManager(output_dir)
    if mannager.run_for_log():
        rprint(f"[green]日志导出成功！[/green]导出目录: {output_dir}")
        return 
    
    rprint("[red]日志导出失败！[/red]")
    raise typer.Exit(code=1)