from pathlib import Path
from typing import Annotated, List, Optional

import typer
from rich import print as rprint

from ...load_config.backup import BackupManager, LoadManager

app = typer.Typer(help="管理 LAZY CLI 配置文件")

@app.command(
    "backup",
    help="备份 LAZY CLI 配置文件",
    no_args_is_help=True
)
def backup(
    user: Annotated[Optional[bool], typer.Option("--user", "-u", help="启用此选项，备份用户配置")] = False,
    lazy: Annotated[Optional[bool], typer.Option("--lazy", "-l", help="启用此选项，备份程序配置")] = False,
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此选项，导出所有配置")] = False,
    ouyput_dir: Annotated[Optional[str], typer.Option("--dest", "-d", help="备份目标文件夹")] = Path.home()
):
    if not (user or lazy or all):
        rprint("[red]应至少制定一种备份模式！[/red]")
        raise typer.Exit(code=1)
    
    destination = Path(ouyput_dir)
    if not destination.is_dir():
        rprint("[red]目标文件夹不存在！[/red]")
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

@app.command(
    "load",
    help="加载 LAZY CLI 配置文件",
    no_args_is_help=True
)
def load(
    sources: Annotated[List[str], typer.Argument(help="待加载配置路径")],
    force: Annotated[Optional[bool], typer.Option("--force", "-f", help="启用此选项，强制覆盖应用配置 (unsafe!!!)")] = False
):
    try:
        sources_path = list(map(Path, sources))
        for path in sources_path:
            if not path.is_file():
                rprint(f"{path} 文件不存在！")
                raise typer.Exit(code=1)
    except TypeError as e:
        rprint("请输入合法路径！")
        raise typer.Exit(code=1) from e

    manager = LoadManager(sources_path, force)
    
    if manager.load():
        rprint("[green]配置加载成功！[/green]")
        return
    rprint("[red]配置加载失败！[/red]")
