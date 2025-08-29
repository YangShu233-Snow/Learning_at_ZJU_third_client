import typer
from typing_extensions import Optional, Annotated, List
from requests.exceptions import HTTPError
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn
from datetime import datetime
from pathlib import Path

from zjuAPI import zju_api
from upload import file_upload
from printlog.print_log import print_log
from ..state import state

# resource 命令组
app = typer.Typer(help="学在浙大云盘资源相关命令，可以查看，搜索，上传或下载云盘文件。")

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
@app.command("list", help="列举学在浙大云盘内的文件及其信息，支持指定文件名称与类型。")
def list_resources(
    keyword: Annotated[Optional[str], typer.Option("--name", "-n", help="文件名称")] = "",
    amount: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示文件的数量")] = 10,
    page_index: Annotated[Optional[int], typer.Option("--page", "-p", help="云盘文件页面索引")] = 1,
    file_type: Annotated[Optional[str], typer.Option("--type", "-t", help="文件类型", callback=is_list_resoureces_file_type_valid)] = None,
    short: Annotated[Optional[bool], typer.Option("--short", "-s", help="简化输出内容，仅显示文件名与文件id")] = False,
    quiet: Annotated[Optional[bool], typer.Option("--quiet", "-q", help="仅输出文件id")] = False
    ):
    """
    列举学在浙大云盘内的文件资源，允许指定文件名称，显示数量与文件类型。

    并不建议将显示数量指定太大，这可能延长网络请求时间，并且大量输出会淹没你的显示窗口。实际上你可以通过 "--page" 参数实现翻页。
    """
    results = zju_api.resourcesListAPIFits(state.client.session, keyword, page_index, amount, file_type).get_api_data(False)[0]
    total_pages = results.get("pages")
    if page_index > total_pages:
        print(f"页面索引超限！共 {total_pages} 页，你都索引到第 {page_index} 页啦！")
        raise typer.Exit(code=1)

    resources_list = results.get("uploads", [])
    current_results_amount = len(resources_list)

    if current_results_amount == 0:
        print("啊呀！没有找到文件呢。")
        raise typer.Exit()
    
    # quiet 模式仅打印文件id，并且不换行
    # short 模式仅按表单格式打印文件名与文件id
    for resource in resources_list:
        resource_id = resource.get('id', 'null')
        if quiet:
            print(resource_id, end=" ")
            continue

        resource_name = resource.get('name', 'null')
        if short:
            print("------------------------------")
            rprint(f"[bright_yellow]{resource_name}[/bright_yellow]")
            rprint(f"  [green]文件ID: [/green][cyan]{resource_id}[/cyan]")
            continue
        
        resource_size = transform_resource_size(resource.get('size', 0))
        resource_download_status = resource.get('allow_download', False)
        resource_update_time = datetime.fromisoformat(resource.get("updated_at", "1900-01-01T00:00:00Z").replace('Z', '+00:00'))    

        print("--------------------------------------------------")
        rprint(f"[bright_yellow]{resource_name}[/bright_yellow]")
        rprint(f"  [green]文件ID: [/green][cyan]{resource_id}[/cyan]")
        rprint(f"  [green]文件是否可下载: [/green][cyan]{resource_download_status}[/cyan]")
        rprint(f"  [green]文件上传时间: [/green][white]{resource_update_time}[/white]")
        rprint(f"  [green]文件大小: [/green][bright_white]{resource_size}[/bright_white]")

    # quiet 模式不需要结尾
    if quiet:
        print("\n")
        return

    if short:
        print("------------------------------")
        return

    print("--------------------------------------------------")
    print(f"本页共 {current_results_amount} 个结果，第 {page_index}/{total_pages} 页。")
    return 

# 注册资源上传命令
@app.command(name="upload", help="上传本地文件至云盘，启用 --recursion 以自动解包文件夹")
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
@app.command(name="remove", help="删除云盘指定文件，支持多文件删除")
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

@app.command(name="download", help="下载云盘指定文件，支持多文件下载")
def download_resource(
    files_id: Annotated[List[int], typer.Argument(help="需下载文件的id")]
):
    """
    下载学在浙大云盘内的指定文件，支持一次提供多个文件id批量下载。
    """

