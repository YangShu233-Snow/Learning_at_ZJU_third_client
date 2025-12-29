import typer
from ...load_config.backup import BackupManager
from typing import Annotated, List, Optional
from rich import print as rprint
from pathlib import Path

app = typer.Typer(help="管理 LAZY CLI 配置文件")

@app.command(
    "backup",
    help="备份 LAZY CLI 配置文件"
)
def backup(
    user: Annotated[Optional[bool], typer.Option("--user", "-u", help="启用此选项，备份用户配置")] = False,
    lazy: Annotated[Optional[bool], typer.Option("--lazy", "-l", help="启用此选项，备份程序配置")] = False,
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此选项，导出所有配置")] = False,
    destination: Annotated[Optional[str], typer.Option("--dest", "-d", help="备份目标文件夹")] = Path.home()
):
    if not (user or lazy or all):
        rprint("[red]应至少制定一种备份模式！[/red]")
        raise typer.Exit(code=1)
    
    manager = BackupManager(destination)
    
    if user or all:
        if manager.run_for_user():
            rprint(f"[green]用户配置备份成功！[/green]备份目录: {Path(destination).resolve()}")
        else:
            rprint("[red]备份出错！[/red]")

    if lazy or all:
        if manager.run_for_lazy():
            rprint(f"[green]程序配置备份成功！[/green]备份目录: {Path(destination).resolve()}")
        else:
            rprint("[red]备份出错！[/red]")

    return