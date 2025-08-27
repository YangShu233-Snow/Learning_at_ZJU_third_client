import typer
from typing_extensions import Optional, Annotated
from requests import Session
from rich import print as rprint
from datetime import datetime

from zjuAPI import zju_api, courses_search
from printlog.print_log import print_log
from ..state import state

# resource 命令组
app = typer.Typer(help="学在浙大云盘资源相关命令，可以查看，搜索，上传或下载云盘文件。")

# 资源列举file_type检验函数
def is_list_resoureces_file_type_valid(file_type: str):
    valid_file_type = ["all", "file", "video", "document", "image", "audio", "scorm", "swf", "link"]
    if file_type in valid_file_type:
        return
    
    print_log("Error", f"{file_type} 资源类型不存在！", "CLI.command.resource.is_list_resoureces_file_type_valid")
    print(f"{file_type} 资源类型不存在！")
    raise typer.Exit(code=1)

# 注册资源列举命令
@app.command("list", help="列举学在浙大云盘内的文件及其信息，支持指定文件名称与类型。")
def list_resources(
    keyword: Annotated[Optional[str], typer.Option("--name", "-n", help="文件名称")] = "",
    amount: Annotated[Optional[int], typer.Option("--amount", "-a", help="显示文件的数量")] = 10,
    page_index: Annotated[Optional[int], typer.Option("--page", "-p", help="云盘文件页面索引")] = 1,
    file_type: Annotated[Optional[str], typer.Option("--type", "-t", help="文件类型", callback=is_list_resoureces_file_type_valid)] = "all"):
    """
    列举学在浙大云盘内的文件资源，允许指定文件名称，显示数量与文件类型。

    并不建议将显示数量指定太大，这可能延长网络请求时间，并且大量输出会淹没你的显示窗口。实际上你可以通过 "--page" 参数实现翻页。
    """
    results = zju_api.resourcesListAPIFits(state.client.session, keyword, page_index, amount, file_type).get_api_data(False)
    total_pages = results.get("pages")
    if page_index > total_pages:
        print(f"页面索引超限！共 {total_pages} 页，你都索引到第 {page_index} 页啦！")
        raise typer.Exit(code=1)

    resources_list = results.get("uploads", [])
    current_results_amount = len(resources_list)

    if current_results_amount == 0:
        print("啊呀！没有找到文件呢。")
        raise typer.Exit()
    
    for resource in resources_list:
        resource_name = resource.get('name', 'null')
        resource_id = resource.get('id', 'null')
        resource_size = resource.get('size', 0)
        resource_download_status = resource.get('allow_download', False)
        resource_update_time = datetime.fromisoformat(resource.get("updated_at", "1900-01-01T00:00:00Z").replace('Z', '+00:00'))    

        print("--------------------------------------------------")
        rprint(f"[bright_yellow]{resource_name}[/bright_yellow]")
        rprint(f"  [green]文件ID: [/green][cyan]{resource_id}[/cyan]")
        rprint(f"  [green]文件是否可下载: [/green][cyan]{resource_download_status}[/cyan]")
        rprint(f"  [green]文件上传时间: [/green][white]{resource_update_time}[/white]")
        rprint(f"  [green]文件大小: [/green][bright_white]{resource_size}[/bright_white]")

    print("--------------------------------------------------")
    print(f"本页共 {current_results_amount} 个结果，第 {page_index}/{total_pages} 页。")