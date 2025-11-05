import typer
import logging
from asyncer import syncify
from functools import partial
from typing_extensions import Optional, Annotated, List
from requests.exceptions import HTTPError
from rich import filesize
from rich import print as rprint
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, TaskProgressColumn, TimeRemainingColumn, BarColumn, ProgressColumn, Text, Task
from datetime import datetime
from pathlib import Path
from textwrap import dedent

from ..state import state
from ...zjuAPI import zju_api
from ...login.login import ZjuAsyncClient, CredentialManager

# resource 命令组
app = typer.Typer(help="管理学在浙大云盘资源",
                  no_args_is_help=True
                  )

logger = logging.getLogger(__name__)

class HumanReadableTransferColumn(ProgressColumn):
    """
    一个以人类可读格式（如 MB/s 或 KB/s）显示进度的列。
    """
    def render(self, task: "Task") -> Text:
        """
        渲染进度，将字节转换为可读格式。
        """
        # task.completed 是已完成的字节数
        # task.total 是总字节数
        completed_str = filesize.decimal(int(task.completed))
        
        if task.total is not None:
            total_str = filesize.decimal(int(task.total))
            # 最终显示的文本格式
            display_text = f"{completed_str}/{total_str}"
        else:
            # 如果总大小未知
            display_text = f"{completed_str}/?"

        return Text(display_text, style="progress.percentage")

# 资源列举file_type检验
def is_list_resoureces_file_type_valid(file_type: str):
    valid_file_type = ["all", "file", "video", "document", "image", "audio", "scorm", "swf", "link"]

    if file_type == None:
        return "all"

    if file_type in valid_file_type:
        return file_type
    
    logger.error(f"{file_type} 资源类型不存在！")
    print(f"{file_type} 资源类型不存在！")
    raise typer.Exit(code=1)

def is_download_dest_dir(dest: Path):
    if dest == Path().home() / "Downloads" and not dest.exists:
        Path(dest).mkdir()

    if not dest.exists():
        logger.error(f"{dest} 不存在！")
        print(f"{dest} 不存在！")
        raise typer.Exit(code=1)
    
    if not dest.is_dir():
        logger.error(f"{dest} 应是文件夹！")
        print(f"{dest} 应是文件夹！")
        raise typer.Exit(code=1)
    
    return dest

# 转换时间
def transform_time(time: str|None)->str:
    if time:
        time_local = datetime.fromisoformat(time.replace('Z', '+00:00')).astimezone()
        return time_local.strftime('%Y-%m-%d %H:%M:%S')
    else:
        return "null"

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
@app.command(
        "ls",
        hidden=True,
        help="Alias for 'list'",
        epilog=dedent("""
            EXAMPLES:
                      
              $ lazy resource list -n "微积分"
                (搜索名称包含"微积分"的文件)
                      
              $ lazy resource list -A -q      
                (仅输出所有资源的文件ID)
                      
              $ lazy resource list -p 2 -a 5  
                (查看第 2 页，每页显示 5 个结果)
        """))
@app.command(
        "list",
        help="查看云盘资源列表",
        epilog=dedent("""
            EXAMPLES:
                      
              $ lazy resource list -n "微积分"
                (搜索名称包含"微积分"的文件)
                      
              $ lazy resource list -A -q      
                (仅输出所有资源的文件ID)
                      
              $ lazy resource list -p 2 -a 5  
                (查看第 2 页，每页显示 5 个结果)
        """))
@partial(syncify, raise_sync_error=False)
async def list_resources(
    keyword: Annotated[Optional[str], typer.Option("--name", "-n", help="文件名称")] = "",
    amount: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示文件的数量")] = 10,
    page_index: Annotated[Optional[int], typer.Option("--page", "-p", help="云盘文件页面索引")] = 1,
    file_type: Annotated[Optional[str], typer.Option("--type", "-t", help="文件类型", callback=is_list_resoureces_file_type_valid)] = None,
    short: Annotated[Optional[bool], typer.Option("--short", "-s", help="简化输出内容，仅显示文件名与文件id")] = False,
    quiet: Annotated[Optional[bool], typer.Option("--quiet", "-q", help="仅输出文件id")] = False,
    all: Annotated[Optional[bool], typer.Option("--all", "-A", help="启用此参数，一次性输出所有结果")] = False
    ):
    """
    列举学在浙大云盘内的文件资源，并通过指定条件进行筛选。

    默认每页显示 10 个结果。
    你可以通过 -p 与 -a 指定页码与每页显示数量，或通过 -A 输出全部文件（此时会无视 -p 与 -a）。
    你可以通过 -t 筛选指定的文件类型，合法的文件类型有："file", "video", "document", "image", "audio", "scorm", "swf", "link"
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        task = progress.add_task(description="拉取资源信息中...", total=1)

        cookies = CredentialManager().load_cookies()
        if not cookies:
            rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)

        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            # 如果启用--all，则先获取文件资源总数
            if all:
                pre_results = (await zju_api.resourcesListAPIFits(client.session, keyword, 1, 1, file_type).get_api_data(False))[0]
                amount = pre_results.get("pages", 1)
                page_index = 1

            results = (await zju_api.resourcesListAPIFits(client.session, keyword, page_index, amount, file_type).get_api_data(False))[0]
        
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
            resources_list_table.add_column("上传时间", ratio=1)
            resources_list_table.add_column("文件大小", ratio=1)

        
        # short 模式仅按表单格式打印文件名与文件id
        for resource in resources_list:
            resource_id = str(resource.get('id', 'null'))
            resource_name = resource.get('name', 'null')
            
            if short:
                resources_list_table.add_row(resource_id, resource_name)
                
                if resource != resources_list[-1]:
                    resources_list_table.add_row()
                
                continue
            
            resource_size = filesize.decimal(resource.get('size', 0))
            resource_update_time = transform_time(resource.get("updated_at", "1900-01-01T00:00:00Z"))
            resources_list_table.add_row(
                resource_id,
                resource_name,
                resource_update_time,
                resource_size
            )

            if resource != resources_list[-1]:
                resources_list_table.add_row()

        progress.advance(task, 1)
    
    rprint(resources_list_table)

# 注册资源上传命令
@app.command(
        "up",
        hidden=True,
        help="Alias for 'upload'",
        epilog=dedent("""
            EXAMPLES:
              
              $ lazy resource upload /path/to/your/file   
                (上传指定路径的文件)
                      
              $ lazy resource upload /path/to/your/dir/ -r
                (上传指定路径文件夹内的文件)
        """),
        no_args_is_help=True)
@app.command(
        "upload",
        help="上传文件至云盘",
        epilog=dedent("""
            EXAMPLES:
              
              $ lazy resource upload /path/to/your/file   
                (上传指定路径的文件)
                      
              $ lazy resource upload /path/to/your/dir/ -r
                (上传指定路径文件夹内的文件)
        """),
        no_args_is_help=True)
@partial(syncify, raise_sync_error=False)
async def upload_resources(
    files: Annotated[List[Path], typer.Argument(help="一个或多个文件路径", callback=check_files_path)],
    recursion: Annotated[Optional[bool], typer.Option("--recursion", "-r", help="启用此参数以解析文件夹")] = False
):
    """
    将本地指定文件上传云盘。

    启用 --recursion 参数后支持自动文件夹解包与上传。

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
    to_upload_files: List[Path] = []

    # 创建进度提示，开始载入并上传文件
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True   
    ) as progress:        
        pre_task = progress.add_task(description="[green]正在载入文件...[/green]", total=len(files))
        
        logger.info("载入目标路径")
        for file in files:
            if Path.is_dir(file):
                if not recursion:
                    logger.warning(f"{file} 为文件夹，但是 --recursion未启用")
                    print(f"{file} 是一个文件夹，但是你没有启用 --recursion，它不会被解包为文件上传！")
                    progress.advance(pre_task)
                    continue

                to_upload_files.extend(to_upload_dir_walker(file))
            else:
                to_upload_files.append(file)
            
            progress.advance(pre_task)
        
        success_amount  = 0
        total_amount    = len(to_upload_files)
        logger.info(f"成功载入 {total_amount} 个文件")
        main_task = progress.add_task(description="[green]正在上传文件...[/green]", total=total_amount)

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            HumanReadableTransferColumn(),
            TimeRemainingColumn()
        ) as sub_progress:
            cookies = CredentialManager().load_cookies()
            if not cookies:
                rprint("Cookies不存在！")
                logger.error("Cookies不存在！")
                raise typer.Exit(code=1)

            async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
                files_uploader = zju_api.resourceUploadAPIFits(client.session)
                
                for to_upload_file in to_upload_files:
                    # 文件子任务，跟踪单文件上传进度
                    upload_task = sub_progress.add_task(description="创建上传任务...", start=False)

                    # 创建回调函数
                    def update_progress(uploaded: int, total: int, filename: str, task_id: int = upload_task):
                        # 首次回调，更新文件名和进度
                        if not sub_progress.tasks[task_id].started:
                            sub_progress.start_task(task_id)
                            sub_progress.update(task_id, description=f"[cyan]上传: {filename}", total=total)

                        sub_progress.update(task_id, completed=uploaded)

                    if await files_uploader.upload(to_upload_file, update_progress):
                        success_amount += 1
                        sub_progress.update(upload_task, description=f"[green]√ {sub_progress.tasks[upload_task].description}[/green]", completed=sub_progress.tasks[upload_task].total)
                    else:
                        sub_progress.update(upload_task, description=f"[red]上传失败: {str(to_upload_file)} o(￣ヘ￣o＃)[/red]")

                    progress.advance(main_task, advance=1)
            
        rprint(f"[green]文件上传完成！[/green]成功上传 {success_amount} 个文件，失败 {total_amount - success_amount} 个文件。")
    
    return 
    
# 注册资源删除命令
@app.command(
        "re",
        hidden=True,
        help="Alias for 'remove'",
        epilog=dedent("""
            EXAMPLES:
                      
              $ lazy resource remove 114514         
                (从云盘上删除ID为"114514"的文件)
                      
              $ lazy resource remove 114514 23333 -b
                (从云盘上删除ID为"114514"与"2333"的文件，批量模式)
        """),
        no_args_is_help=True)
@app.command(
        "remove",
        help="删除云盘资源文件",
        epilog=dedent("""
            EXAMPLES:
                      
              $ lazy resource remove 114514         
                (从云盘上删除ID为"114514"的文件)
                      
              $ lazy resource remove 114514 23333 -b
                (从云盘上删除ID为"114514"与"2333"的文件，批量模式)
        """),
        no_args_is_help=True)
@partial(syncify, raise_sync_error=False)
async def remove_resources(
    files_id: Annotated[List[int], typer.Argument(help="需删除文件的id")],
    force: Annotated[Optional[bool], typer.Option("--force", "-f", help="启用 --force 以关闭二次确认")] = False,
    batch: Annotated[Optional[bool], typer.Option("--batch", "-b", help="启用 --batch 则使用快速批量模式，但此模式存在缺陷，服务端不会对文件id做任何校验，倘若你输入一个不存在的文件id也会返回删除成功")] = False
):
    """
    删除学在浙大云盘内的指定文件。

    默认支持多个文件ID的删除，启用批量模式并不安全。

    本命令需要二次确认，启用 --force 则忽略二次确认。
    """
    
    files_id_amount = len(files_id)
    success_delete_amount = 0

    if not force:
        rprint(f"本次共要删除 {files_id_amount} 个文件。")
        rprint(f"包含以下文件: {', '.join(map(str, files_id))}")
        delete = typer.confirm("你确定要删除它们吗?")

        if not delete:
            print("已取消")
            raise typer.Exit()
        
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        cookies = CredentialManager().load_cookies()
        if not cookies:
            rprint("Cookies不存在！")
            logger.error("Cookies不存在！")
            raise typer.Exit(code=1)
        if batch:
            task = progress.add_task(description="删除文件中...", total=1)

            async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
                file_deleter = zju_api.resourcesRemoveAPIFits(client.session, resources_id=files_id)
            
            if await file_deleter.batch_delete():
                progress.advance(task, 1)
                logger.info("删除成功")
                rprint(f"删除完成，共删除 {files_id_amount} 个文件")
                return 
            
            logger.error(f"删除失败")
            rprint(f"[blod red]删除失败[/blod red]")
            progress.advance(task, 1)
            raise typer.Exit(code=1)
        
        task = progress.add_task(description="删除文件中...", total=files_id_amount)
        
        async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
            for file_id in files_id:
                file_deleter = zju_api.resourcesRemoveAPIFits(client.session, resource_id=file_id)
                
                if await file_deleter.delete():
                    progress.advance(task, 1)
                    success_delete_amount += 1
                    continue

                logger.error(f"{file_id} 删除失败")
                rprint(f"{file_id} 删除失败")

        logger.info(f"删除完成")
        rprint(f"删除完成，{success_delete_amount} 个文件被成功删除，{files_id_amount - success_delete_amount} 个文件删除失败。")
        return

# 注册资源下载命令
@app.command(
        "dl",
        hidden=True,
        help="Alias for 'download'",
        epilog=dedent("""
            EXAMPLES:
                      
              $ lazy resource download 114514 -d /path/to/your/download_dir
                (从云盘下载ID为"114514"的文件至本地指定路径，文件名前会加上"我的文件_")
                      
              $ lazy resource download 114514 2333 -b                      
                (从云盘以压缩包形式下载指定文件)
        """),
        no_args_is_help=True)
@app.command(
        "download",
        help="从云盘下载指定文件",
        epilog=dedent("""
            EXAMPLES:
                      
              $ lazy resource download 114514 -d /path/to/your/download_dir
                (从云盘下载ID为"114514"的文件至本地指定路径)
                      
              $ lazy resource download 114514 2333 -b                      
                (从云盘以压缩包形式下载指定文件)
        """),
        no_args_is_help=True)
@partial(syncify, raise_sync_error=False)
async def download_resource(
    files_id: Annotated[List[int], typer.Argument(help="需下载文件的id")],
    basename: Annotated[List[int], typer.Option("--basename", "-n", help="文件的基本名，会附加在下载文件的开头")] = None,
    dest: Annotated[Optional[Path], typer.Option("--dest", "-d", help="下载路径", callback=is_download_dest_dir)] = Path().home() / "Downloads",
    batch: Annotated[Optional[bool], typer.Option("--batch", "-b", help="启用批量下载模式，所有下载的文件以压缩包的形式保存在下载目录下。")] = False
):
    """
    下载学在浙大云盘文件，支持对个人云盘与课程资源的下载。

    默认支持多文件ID自动下载。

    使用 -b 选项以启用批量下载，最终下载文件为包含所有目标文件的压缩包。

    课程资源下载不支持 -b 选项。
    """

    files_id_amount = len(files_id)
    success_amount = 0

    if batch:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            transient=True   
        ) as progress:
            # 总任务，跟踪总体下载进度
            main_task = progress.add_task(description="[green]正在下载文件中...[/green]", total=files_id_amount)
            
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                HumanReadableTransferColumn(),
                TimeRemainingColumn()
            ) as sub_progress:
                cookies = CredentialManager().load_cookies()
                if not cookies:
                    rprint("Cookies不存在！")
                    logger.error("Cookies不存在！")
                    raise typer.Exit(code=1)

                async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
                    resources_downloader = zju_api.resourcesDownloadAPIFits(client.session, output_path=dest, resources_id=files_id, basename=basename)
                
                # 子任务，跟踪文件下载进度
                download_task = sub_progress.add_task(description=f"下载文件中...", start=False)
                
                # 创建回调函数
                def update_progress(downloaded: int, total_size: int, filename: int, task_id: int = download_task):
                    # 首次回调，更新文件名和文件大小
                    if not sub_progress.tasks[task_id].started:
                        sub_progress.start_task(task_id)
                        sub_progress.update(task_id, description=f"[cyan]下载: {filename}", total=total_size)

                    sub_progress.update(task_id, completed=downloaded)
                
                if await resources_downloader.batch_download(progress_callback=update_progress):
                    rprint(f"[green]下载成功！")
                    rprint(f"[green]下载完成！[/green]")
                else:
                    rprint(f"[bold red]下载失败!")

                progress.update(main_task, advance=1)                

            return

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        transient=True
    ) as progress:
        # 总任务，跟踪总体下载进度
        main_task = progress.add_task(description="[green]总进度[/green]", total=files_id_amount)

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            HumanReadableTransferColumn(),
            TimeRemainingColumn()
        ) as sub_progress:
            cookies = CredentialManager().load_cookies()
            if not cookies:
                rprint("Cookies不存在！")
                logger.error("Cookies不存在！")
                raise typer.Exit(code=1)

            async with ZjuAsyncClient(cookies=cookies, trust_env=state.trust_env) as client:
                for file_id in files_id:
                    resource_downloader = zju_api.resourcesDownloadAPIFits(client.session, output_path=dest, resource_id=file_id, basename=basename)
                    
                    # 单文件子任务，跟踪文件下载状态
                    download_task = sub_progress.add_task(description=f"文件ID: {file_id}", start=False)

                    # 创建回调函数
                    def update_progress(downloaded: int, total_size: int, filename: int, task_id: int = download_task):
                        # 首次回调，更新文件名和文件大小
                        if not sub_progress.tasks[task_id].started:
                            sub_progress.start_task(task_id)
                            sub_progress.update(task_id, description=f"[cyan]下载: {filename}", total=total_size)

                        sub_progress.update(task_id, completed=downloaded)

                    if await resource_downloader.download(progress_callback=update_progress):
                        success_amount += 1
                        sub_progress.update(download_task, description=f"[green]√ {sub_progress.tasks[download_task].description}", completed=sub_progress.tasks[download_task].total)
                    else:
                        sub_progress.update(download_task, description=f"[red]下载失败: {file_id} o(￣ヘ￣o＃)[/red]")

                    progress.update(main_task, advance=1)

        rprint(f"[green]下载完成！[/green]成功下载 {success_amount} 个文件，失败 {files_id_amount - success_amount} 个文件。")
        rprint(f"[cyan]下载路径: [/cyan]{dest}")
        return
