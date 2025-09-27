import typer
from typing_extensions import Optional, Annotated, List
from requests.exceptions import HTTPError
from rich import print as rprint
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, TaskProgressColumn, TimeRemainingColumn
from datetime import datetime
from pathlib import Path

from ...zjuAPI import zju_api
from ...upload import file_upload
from ...printlog.print_log import print_log
from ..state import state

# resource 命令组
app = typer.Typer(help="学在浙大云盘资源相关命令，可以查看，搜索，上传或下载云盘文件。",
                  no_args_is_help=True
                  )

# 资源列举file_type检验
def is_list_resoureces_file_type_valid(file_type: str):
    valid_file_type = ["all", "file", "video", "document", "image", "audio", "scorm", "swf", "link"]

    if file_type == None:
        return "all"

    if file_type in valid_file_type:
        return file_type
    
    print_log("Error", f"{file_type} 资源类型不存在！", "CLI.command.resource.is_list_resoureces_file_type_valid")
    print(f"{file_type} 资源类型不存在！")
    raise typer.Exit(code=1)

def is_download_dest_dir(dest: Path):
    if dest == Path().home() / "Downloads" and not dest.exists:
        Path(dest).mkdir()

    if not dest.exists():
        print_log("Error", f"{dest} 不存在！", "CLI.command.resource.is_download_dest_dir")
        print(f"{dest} 不存在！")
        raise typer.Exit(code=1)
    
    if not dest.is_dir():
        print_log("Error", f"{dest} 应是文件夹！", "CLI.command.resource.is_download_dest_dir")
        print(f"{dest} 应是文件夹！")
        raise typer.Exit(code=1)
    
    return dest

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

# 修整并检查文件路径
def check_files_path(files: List[Path])->List[Path]:
    new_files_path = []
    for file in files:
        new_file_path = file.expanduser().resolve()
        if not new_file_path.exists():
            raise typer.BadParameter(message=f"{new_file_path} 不存在！")
        
        new_files_path.append(new_file_path)

    return new_files_path

# 解包文件夹及其嵌套
def to_upload_dir_walker(dir: Path)->List[Path]:
    to_upload_files = []

    for file in dir.glob("*"):
        if Path.is_dir(file):
            to_upload_files.extend(to_upload_dir_walker(file))
            continue

        to_upload_files.append(file)

    return to_upload_files

# 注册资源列举命令
@app.command("list")
def list_resources(
    keyword: Annotated[Optional[str], typer.Option("--name", "-n", help="文件名称")] = "",
    amount: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示文件的数量")] = 10,
    page_index: Annotated[Optional[int], typer.Option("--page", "-p", help="云盘文件页面索引")] = 1,
    file_type: Annotated[Optional[str], typer.Option("--type", "-t", help="文件类型", callback=is_list_resoureces_file_type_valid)] = None,
    short: Annotated[Optional[bool], typer.Option("--short", "-s", help="简化输出内容，仅显示文件名与文件id")] = False,
    quiet: Annotated[Optional[bool], typer.Option("--quiet", "-q", help="仅输出文件id")] = False,
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此参数，一次性输出所有结果")] = False
    ):
    """
    列举学在浙大云盘内的文件资源，允许指定文件名称，显示数量与文件类型。

    并不建议将显示数量指定太大，这可能延长网络请求时间，并且大量输出会淹没你的显示窗口。实际上你可以通过 "--page" 参数实现翻页。
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(description="拉取资源信息中...", total=1)
        # 如果启用--all，则先获取文件资源总数
        if all:
            pre_results = zju_api.resourcesListAPIFits(state.client.session, keyword, 1, 1, file_type).get_api_data(False)[0]
            amount = pre_results.get("pages", 1)
            page_index = 1

        results = zju_api.resourcesListAPIFits(state.client.session, keyword, page_index, amount, file_type).get_api_data(False)[0]
        
        progress.advance(task, 1)
        task = progress.add_task(description="渲染资源信息中...", total=1)
        
        total_pages = results.get("pages", 0)

        if page_index > total_pages and total_pages > 0:
            print(f"页面索引超限！共 {total_pages} 页，你都索引到第 {page_index} 页啦！")
            raise typer.Exit(code=1)

        resources_list = results.get("uploads", [])
        current_results_amount = len(resources_list)

        if current_results_amount == 0:
            print("啊呀！没有找到文件呢。")
            return
        
        if quiet:
            resourse_ids = [str(resource.get('id', 'null')) for resource in resources_list]
            print(" ".join(resourse_ids))
            return

        resources_list_table = Table(
            title=f"资源列表 (第 {page_index} / {total_pages} 页)",
            caption=f"本页显示 {len(resources_list)} 个。",
            border_style="bright_black",
            show_header=True,
            header_style="bold magenta",
            expand=True
        )

        if short:
            resources_list_table.add_column("资源ID", style="cyan", no_wrap=True, width=10)
            resources_list_table.add_column("资源名称", style="bright_yellow", ratio=1)
        else:
            resources_list_table.add_column("资源ID", style="cyan", no_wrap=True, width=8)
            resources_list_table.add_column("资源名称", style="bright_yellow", ratio=3)
            resources_list_table.add_column("上传时间", ratio=2)
            resources_list_table.add_column("文件大小", ratio=1)
            resources_list_table.add_column("下载状态", ratio=1)

        
        # quiet 模式仅打印文件id，并且不换行
        # short 模式仅按表单格式打印文件名与文件id
        for resource in resources_list:
            resource_id = str(resource.get('id', 'null'))
            resource_name = resource.get('name', 'null')
            
            if short:
                resources_list_table.add_row(resource_id, resource_name)
                
                if resource != resources_list[-1]:
                    resources_list_table.add_row()
                
                continue
            
            resource_size = transform_resource_size(resource.get('size', 0))
            resource_download_status = "[green]可下载[/green]" if resource.get('allow_download', False) else "[red]不可下载[/red]"
            resource_update_time = datetime.fromisoformat(resource.get("updated_at", "1900-01-01T00:00:00Z").replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')

            resources_list_table.add_row(
                resource_id,
                resource_name,
                resource_update_time,
                resource_size,
                resource_download_status
            )

            if resource != resources_list[-1]:
                resources_list_table.add_row()

        progress.advance(task, 1)
    
    rprint(resources_list_table)

# 注册资源上传命令
@app.command(name="upload")
def upload_resources(
    files: Annotated[List[Path], typer.Argument(help="一个或多个文件路径", callback=check_files_path)],
    recursion: Annotated[Optional[bool], typer.Option("--recursion", "-r", help="启用此参数以解析文件夹")] = False
):
    """
    将本地指定文件上传云盘，支持批量上传，启用 --recursion 参数后支持自动文件夹解包与上传。

    目前学在浙大仅支持以下文件格式上传：
        
        视频: avi, flv, m4v, mkv, mov, mp4, 3gp, 3gpp, mpg, rm, rmvb, swf, webm, wmv
        音频: mp3, m4a, wav, wma
        图像: jpeg, jpg, png, gif, bmp, heic, webp
        文档: txt, pdf, csv, xls, xlsx, doc, ppt, pptx, docx, odp, ods, odt, rtf
        压缩包: zip, rar, tar
        其他: mat, dwg, m, mlapp, slx, mlx

    任何不属于以上文件格式的文件都会被自动忽略。

    不属于其他类的文件格式的文件单文件大小限制在3GB以内，其他类文件格式的文件单文件大小限制在2GB以内，超出限定大小的文件将被自动忽略。
    """
    to_upload_files = []
    
    print_log("Info", "载入目标路径", "CLI.command.resource.upload_resources")

    # 创建进度提示，开始载入并上传文件
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(description="载入文件中...", total=1)
        for file in files:
            if Path.is_dir(file):
                if not recursion:
                    print_log("Warning", f"{file} 为文件夹，但是 --recursion未启用", "CLI.command.resource.upload_resources")
                    print(f"{file} 是一个文件夹，但是你没有启用 --recursion，它不会被解包为文件上传！")
                    continue

                to_upload_files.extend(to_upload_dir_walker(file))
                continue
            
            to_upload_files.append(file)
        progress.advance(task, advance=1)

        total_to_upload_files_amount = len(to_upload_files)
        print_log("Info", f"成功载入 {total_to_upload_files_amount} 个文件", "CLI.command.resource.upload_resources")    
        print(f"{total_to_upload_files_amount} 个文件被载入")

        task = progress.add_task(description="文件上传中...")
        try:
            files_uploader = file_upload.uploadFile(to_upload_files)
            files_uploader.upload(state.client.session)
        except HTTPError as e:
            print_log("Error", f"上传发生网络错误！错误原因: {e}", "CLI.command.resource.upload_resources")
            print("上传发生错误！")
            raise typer.Exit(code=1)
        
        print("文件上传完成！")
        progress.advance(task, advance=1)
    
    return 
    
# 注册资源删除命令
@app.command(name="remove")
def remove_resources(
    files_id: Annotated[List[int], typer.Argument(help="需删除文件的id")],
    force: Annotated[Optional[bool], typer.Option("--force", "-f", help="启用 --force 以关闭二次确认")] = False,
    batch: Annotated[Optional[bool], typer.Option("--batch", "-b", help="启用 --batch 则使用快速批量模式，但此模式存在缺陷，服务端不会对文件id做任何校验，倘若你输入一个不存在的文件id也会返回删除成功")] = False
):
    """
    删除学在浙大云盘内的指定文件，支持一次提供多个文件id批量删除。

    本命令需要二次确认，启用 --force 则忽略二次确认。
    """
    
    files_id_amount = len(files_id)
    success_delete_amount = 0

    if not force:
        rprint(f"本次共要删除 {files_id_amount} 个文件。")
        rprint(f"包含以下文件: {", ".join(map(str, files_id))}")
        delete = typer.confirm("你确定要删除它们吗?")

        if not delete:
            print("已取消")
            raise typer.Exit()
        
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        if batch:
            task = progress.add_task(description="删除文件中...", total=1)
            file_deleter = zju_api.resourcesRemoveAPIFits(state.client.session, resources_id=files_id)
            
            if file_deleter.batch_delete():
                progress.advance(task, 1)
                print_log("Info","删除成功", "CLI.command.resource.remove_resources")
                rprint(f"删除完成，共删除 {files_id_amount} 个文件")
                return 
            
            print_log("Error", f"删除失败", "CLI.command.resource.remove_resources")
            rprint(f"[blod red]删除失败[/blod red]")
            progress.advance(task, 1)
            raise typer.Exit(code=1)
        
        task = progress.add_task(description="删除文件中...", total=files_id_amount)
        
        for file_id in files_id:
            file_deleter = zju_api.resourcesRemoveAPIFits(state.client.session, resource_id=file_id)
            
            if file_deleter.delete():
                progress.advance(task, 1)
                success_delete_amount += 1
                continue

            print_log("Error", f"{file_id} 删除失败", "CLI.command.resource.remove_resources")
            rprint(f"{file_id} 删除失败")

        print_log("Info", f"删除完成", "CLI.command.resource.remove_resources")
        rprint(f"删除完成，{success_delete_amount} 个文件被成功删除，{files_id_amount - success_delete_amount} 个文件删除失败。")
        return

@app.command(name="download")
def download_resource(
    files_id: Annotated[List[int], typer.Argument(help="需下载文件的id")],
    dest: Annotated[Optional[Path], typer.Option("--dest", "-d", help="下载路径", callback=is_download_dest_dir)] = Path().home() / "Downloads",
    batch: Annotated[Optional[bool], typer.Option("--batch", "-b", help="启用批量下载模式，所有下载的文件以压缩包的形式保存在下载目录下。")] = False
):
    """
    下载学在浙大的文件，同时支持个人浙大云盘与课程资源下载，支持一次提供多个文件id批量下载。

    使用 --batch 选项以启用批量下载，最终下载文件打包为.zip
    """

    files_id_amount = len(files_id)
    success_amount = 0

    if batch:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True   
        ) as progress:
            task = progress.add_task(description="[green]正在下载文件中...[/green]", total=files_id_amount)
            
            resources_downloader = zju_api.resourcesDownloadAPIFits(state.client.session, output_path=dest, resources_id=files_id)
            
            if resources_downloader.batch_download():
                rprint(f"[green]下载成功！")
                rprint(f"[green]下载完成！[/green]")
            else:
                rprint(f"[bold red]下载失败!")

            progress.update(
                task,
                advance=1
            )

            return

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TaskProgressColumn(),
        transient=True
    ) as progress:
        task = progress.add_task(description="[green]正在下载文件中...[/green]", total=files_id_amount)
        
        if batch:
            resources_downloader = zju_api.resourcesDownloadAPIFits(state.client.session, output_path=dest, resources_id=files_id)
            if resources_downloader.batch_download():
                rprint(f"[green]下载成功！")
                rprint(f"[green]下载完成！[/green]")
            else:
                rprint(f"[bold red]下载失败!")

            progress.update(
                task,
                advance=1
            )

            return

        for file_id in files_id:
            resource_downloader = zju_api.resourcesDownloadAPIFits(state.client.session, output_path=dest, resource_id=file_id)
            if resource_downloader.download():
                success_amount += 1
                rprint(f"{file_id} [green]下载成功！")
            else:
                rprint(f"{file_id} [bold red]下载失败!")

            progress.update(
                task,
                advance=1,
                description="正在下载中..."
            )

        rprint(f"[green]下载完成！[/green]成功下载 {success_amount} 个文件，失败 {files_id_amount - success_amount} 个文件。")
        rprint(f"[cyan]下载路径: [/cyan]{dest}")
        return
