from login import login
from zjuAPI import zju_api, courses_search
from load_config import load_config
from upload import file_upload
from printlog.print_log import print_log
from pathlib import Path
from requests.exceptions import HTTPError
import sys
from datetime import datetime, timezone
from colorama import Fore, Style, Back, init

class HelpManual:
    def __init__(self):
        self.search_courses_alias = ["search_courses", "sc"]
        self.upload_file_alias = ["upload_file", "uf"]
        self.todo_list_alias = ["todo_list", "tl", "ddl"]
        self.quit_alias = ["quit", "qq"]

    def help(self):
        print("""""")

    def search_courses_help(self):
        print("search_courses 命令可以查询你学在浙大上已经加入的某些课程")
        print("\t用法: search_courses <search_keyword>")
        print("命令会返回查询到的所有课程的名称，上课时间和任课教师")
        print(f"该命令存在别名：{", ".join(self.search_courses_alias)}")

    def upload_file_help(self):
        print("upload_file 命令可以将你本地的文件提交至云盘。")
        print("\t用法: upload_file <path_to_your_file> ... <path_to_your_dir>")
        print("命令会自动解包路径下的所有文件夹。注意，提交任务前请务必确保文件已经上传至云盘！")
        print(f"该命令存在别名: {", ".join(self.upload_file_alias)}")

    def todo_list_help(self):
        print("todo_list 命令可以查询你学在浙大上正在进行的任务")
        print("\t用法: todo_list -n <show_amount> -r <show_offset>")
        print("\t-n: 显示任务数量，为正整数")
        print("\t-r: 任务查询起始位，为正整数")
        print("命令会返回查询到的任务，并放回任务名称，任务截止日期，任务类型与id，所属课程与id")
        print("任务采用颜色分级，根据任务紧急程度分为红色，黄色，蓝色与绿色。")
        print(f"该命令存在别名：{", ".join(self.todo_list_alias)}")

    def list_cloud_files(self):
        pass

    def quit_help(self):
        print("quit 命令退出CLI交互。")
        print("\t用法: quit")
        print(f"该命令存在别名: {", ".join(self.quit_alias)}")

def login_zju():
    # 执行登录
    print("登录中...")
    login_fit = login.LoginFit()
    login_client = login_fit.login()
    print("登录成功！！！")

    return login_client

def quit(command_parts: list[str]):
    command = command_parts[0]

    if len(command_parts) != 1 and "--help" not in command_parts:
        print(f"该命令不应提供参数！可通过{command} --help获取更多帮助")
        return 1

    sys.exit()

def search_courses(command_parts: list[str], login_client):
    command = command_parts[0]
    C_NAME = Style.BRIGHT + Fore.YELLOW
    C_LABEL = Fore.GREEN
    C_KEY_INFO = Fore.CYAN
    C_NORMAL_INFO = Fore.WHITE
    C_CODE = Style.DIM + Fore.WHITE

    if len(command_parts) != 2:
        print(f"'{command}'命令参数不合法！")
        return 1
            
    keyword = command_parts[1]

    if keyword == "--help":
        HelpManual().search_courses_help()
        return 0

    courses_searcher = courses_search.CoursesSearcher(keyword)
    courses_searcher.search_courses(login_client)

    result = load_config.searchCoursesResults().load_config()

    course_results_count = result.get("total")
    print(f"搜索结果共 {course_results_count} 个")
    
    if course_results_count == 0:
        return 0

    course_results: list[dict] = result.get("courses")

    for course in course_results:
        course_name = course.get("name", "null")
        course_time = course.get("course_attributes").get("teaching_class_name", "null")
        course_teachers = course.get("instructors", [])
        course_department = course.get("department").get("name", "null")
        course_academic_year = course.get("academic_year").get("name", "null")
        course_code = course.get("course_code", "null")

        teachers_name = []
        for teacher in course_teachers:
            name = teacher.get("name", "null")
            teachers_name.append(name)
        
        print("----------------------------------------")
        print(f"{C_NAME}{course_name}")
        print(f"  {C_LABEL}上课时间: {C_KEY_INFO}{course_time}")
        print(f"  {C_LABEL}授课教师: {C_NORMAL_INFO}{'、'.join(teachers_name    )}")
        print(f"  {C_LABEL}开课院系: {C_NORMAL_INFO}{course_department}")
        print(f"  {C_LABEL}开课学年: {C_NORMAL_INFO}{course_academic_year}")
        print(f"  {C_LABEL}课程代码：{C_CODE}{course_code}")

    print("----------------------------------------")
    return 0

def dir_walker(dir_path: Path) -> list[Path]:
    """检索路径下所有文件并返回

    Parameters
    ----------
    file_paths : list[Path]
        _description_

    Returns
    -------
    list[Path]
        _description_
    """    
    file_paths = []

    if Path.is_file(dir_path):
        return list(dir_path)

    for file_path in dir_path.glob("*"):
        if Path.is_file(file_path):
            file_paths.append(file_path)
            continue
        
        file_paths.extend(dir_walker(file_path))

    return file_paths

def upload_files(command_parts: list[str], login_client):
    command = command_parts[0]
    to_upload_file = []
    file_paths:list[Path] = []

    if len(command_parts) < 2:
        print(f"该命令需要提供参数！可通过{command} --help获取更多帮助")
        return 1

    if "--help" in command_parts:
        HelpManual().upload_file_help()
        return 0
    
    print("文件载入中...")
    # 检查路径合法性
    for file_path_str in command_parts[1:]:
        file_path = Path(file_path_str)
        if file_path.exists():
            file_paths.append(file_path)
        else:
            print(f"{file_path_str} 不是一个文件/文件夹！")
            print("Warning", f"{file_path_str} 不是一个文件/文件夹！", "CLI.CLI.upload_files")

    if len(file_paths) == 0:
        print("没有文件/文件夹可以上传！")
        print("Info", f"{file_path_str} 不是一个文件/文件夹！", "CLI.CLI.upload_files")
        return 0

    # 载入所有文件路径
    for file_path in file_paths:
        if Path.is_file(file_path):
            to_upload_file.append(file_path)
            continue

        to_upload_file.extend(dir_walker(file_path))

    print("文件上传中...")
    try:
        files_uploader = file_upload.uploadFile(to_upload_file)
        files_uploader.upload(login_client)
    except HTTPError as e:
        print_log("Error", "上传发生网络错误！", "CLI.CLI.upload_files")
        return 1

    print("文件上传完成！")
    return 0

def print_todo_colorful(todo_attributes: dict):
    C_DEADLINE = Back.RED + Fore.WHITE
    C_EMERGENCY = Style.BRIGHT + Fore.RED
    C_HIGH_PRIORITY = Fore.YELLOW
    C_URGENT = Fore.BLUE
    C_ROUTINE = Fore.GREEN
    C_NORMAL = Fore.WHITE
    C_KEY_INFO = Fore.CYAN

    # 定义不同紧急程度的颜色和标签
    # (下限天数, 上限天数, 颜色代码, 标签)
    ddl_urgency = (
        (0, 1, C_EMERGENCY, "即将截止"),  # 1天内：红色
        (1, 3, C_HIGH_PRIORITY, "略有余地"),  # 3天内：黄色
        (3, 7, C_URGENT, "计划之中")   # 7天内：蓝色
    )
    # 默认颜色（7天以上）：绿色
    color_code = C_ROUTINE
    
    # 从传入的字典中获取截止日期
    todo_deadline = todo_attributes.get("todo_deadline")
    
    # 获取当前的UTC时间，以确保时区匹配
    now_time = datetime.now(timezone.utc)

    # 判断任务是否已经截止
    if todo_deadline > now_time:
        time_to_ddl = todo_deadline - now_time
        # 设置一个默认的紧急程度
        todo_attributes["todo_urgency"] = "远在天边"
        
        # 遍历紧急程度定义，设置对应的颜色和标签
        for urgency in ddl_urgency:
            # 使用 time_to_ddl.days 进行正确的总天数比较
            if time_to_ddl.days < urgency[1]:
                color_code = urgency[2]
                todo_attributes["todo_urgency"] = urgency[3]
                break
    else:
        color_code = C_DEADLINE # 加粗红色
        todo_attributes["todo_urgency"] = "已经截止"

    print(f"----------------------------------------")
    print(f"{color_code}{todo_attributes.get('todo_title')}")
    print(f"{C_NORMAL}截止日期: {C_KEY_INFO}{todo_attributes.get('todo_deadline').strftime('%Y-%m-%d %H:%M:%S')} {todo_attributes.get('todo_urgency')}")
    print(f"{C_NORMAL}任务id: {todo_attributes.get('todo_id')}")
    print(f"{C_NORMAL}任务类型: {todo_attributes.get('todo_type')}")
    print(f"{C_NORMAL}课程名称: {todo_attributes.get('todo_course_name')}")
    print(f"{C_NORMAL}课程id: {todo_attributes.get('todo_course_id')}")

def todo_list(command_parts: list[str], login_client):
    command = command_parts[0]
    show_amount = 5
    offset = 0
    
    # 检验参数
    if "--help" in command_parts:
        HelpManual().todo_list_help()
        return 0
    
    # 显示数量
    if '-n' in command_parts:
        if command_parts.index('-n') == (len(command_parts) - 1):
            print("'-n'未提供参数！")
            return 1
        
        show_amount = command_parts[command_parts.index('-n') + 1]
        if not show_amount.isnumeric():
            print("'-n'应提供整数参数")
            return 1
        
        show_amount = int(show_amount)

        if show_amount == 0:
            print("显示数量不可为0！")
            return 1
    
    # 起始偏移
    if '-r' in command_parts:
        if command_parts.index('-r') == (len(command_parts) - 1):
            print("'-r'未提供足够参数！")
            return 1
        
        offset = command_parts[command_parts.index('-r') + 1]
        if not offset.isnumeric():
            print("'-r'应提供整型参数")
            return 1
        
        offset = int(offset)
        offset = offset -1

    # 更新并加载todo_list
    zju_api.todoListLiteAPIFits(login_client).get_api_data()
    todo_list_dict = load_config.userIndexConfig("todo_list_config").load_config()
    todo_list: list[dict] = todo_list_dict.get("todo_list", None)
    if todo_list == None:
        print_log("Error", f"todo_list存在错误，请将此日志上报给开发者！", "CLI.CLI.todo_list")
        return 1

    # 解析todo_list
    todo_list_amount = len(todo_list)

    if todo_list_amount == 0:
        print("你当前没有需要完成的任务哦~")
        return 0
    
    # 按照时间重新排序
    todo_list = sorted(todo_list, key=lambda todo: datetime.fromisoformat(todo.get("end_time").replace('Z', '+00:00')))
    todo_list = todo_list[offset:]

    # 打印结果
    for index, todo in enumerate(todo_list):
        if index >= show_amount:
            remaining_amount = todo_list_amount - index - 1
            if remaining_amount != 0:
                print("----------------------------------------")
                print(f"...还有{remaining_amount}个结果待显示")
            break
        todo_attributes = dict(        
            todo_title = todo.get("title", "null"),
            todo_id = todo.get("id", "null"),
            todo_type = todo.get("type", "null"),
            todo_deadline = datetime.fromisoformat(todo.get("end_time", "1900-01-01T00:00:00Z").replace('Z', '+00:00')),
            todo_urgency = "远在天边",
            todo_course_name = todo.get("course_name", "null"),
            todo_course_id = todo.get("course_id", "null"))

        print_todo_colorful(todo_attributes)
        continue
    else:
        print("----------------------------------------")

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


def list_cloud_files(command_parts: list[str], login_client):
    C_NAME = Style.BRIGHT + Fore.YELLOW
    C_LABEL = Fore.GREEN
    C_KEY_INFO = Fore.CYAN
    C_NORMAL_INFO = Fore.WHITE
    C_CODE = Style.DIM + Fore.WHITE

    command = command_parts[0]
    show_amount = 10
    page = 1

    # 检验参数
    if "--help" in command_parts:
        HelpManual.list_cloud_files()
        return 0
    
    # 显示数量
    if "-n" in command_parts:
        if command_parts.index("-n") == (len(command_parts) - 1):
            print("'-n' 未提供参数！")
            return 1
        
        show_amount = command_parts[command_parts.index('-n') + 1]
        if not show_amount.isnumeric():
            print("'-n'应提供整型参数！")
            return 1
        
        show_amount = int(show_amount)
        if show_amount == 0:
            print("显示数量不应为0！")
            return 1
    
    # 页面索引
    if '-p' in command_parts:
        if command_parts.index('-p') == (len(command_parts) - 1):
            print("'-p' 未提供参数！")
            return 1
        
        page = command_parts[command_parts.index('-p') + 1]
        if not page.isnumeric():
            print("'-p'应提供整型参数！")
            return 1
        
        page = int(page)
        if page == 0:
            print("页面索引不应为0！")
            return 1
    
    # 更新云盘资源列表数据
    zju_api.resourcesListAPIFits(login_client, page, show_amount).get_api_data()
    resources_list_dict = load_config.myResourcesConfig().load_config()
    
    # 检查页面索引是否超出限制
    pages = resources_list_dict.get('pages')
    if page > pages:
        print(f"页面索引超出限制！当前每页显示{show_amount}个资源，共{pages}页")
        return 0
    
    resources_list: list[dict] = resources_list_dict.get('uploads')
    if resources_list == None:
        print_log("Error", "云盘资源列表获取存在问题！请将此条日志报告给开发者！", "CLI.CLI.list_cloud_files")
        return 1
    
    if len(resources_list) == 0:
        print("资源列表为空！")
        return 0
    
    for resource in resources_list:
        resource_name = resource.get('name', 'null')
        resource_id = resource.get('id', 'null')
        resource_size = resource.get('size', 0)
        resource_download_status = resource.get('allow_download', False)
        resource_update_time = datetime.fromisoformat(resource.get("updated_at", "1900-01-01T00:00:00Z").replace('Z', '+00:00'))

        print("--------------------------------------------------")
        print(f"{C_NAME}{resource_name}")
        print(f"  {C_LABEL}文件ID: {C_KEY_INFO}{resource_id}")
        print(f"  {C_LABEL}文件是否可下载: {C_KEY_INFO}{resource_download_status}")
        print(f"  {C_LABEL}文件上传时间: {C_NORMAL_INFO}{resource_update_time}")
        print(f"  {C_LABEL}文件大小: {C_CODE}{resource_size}")

    print("--------------------------------------------------")
    return 0

def main():
    init(autoreset=True)
    # Hello, user!
    print("""Hello, my name is LAZY!""")
    login_client = login_zju()

    is_running = True

    while is_running:
        user_input = input("> ").strip()

        if not user_input:
            continue

        command_parts = user_input.split()
        command = command_parts[0]

        if command in ["search_courses", "sc"]:
            status_code = search_courses(command_parts, login_client)
            if status_code == 1:
                print(f"{command} 命令执行未成功，你可以使用{command} --help获取该命令的帮助")
            continue

        elif command in ["upload_file", "uf"]:
            status_code = upload_files(command_parts, login_client)
            if status_code == 1:
                print(f"{command} 命令执行未成功，你可以使用{command} --help获取该命令的帮助")
            continue

        elif command in ["todo_list", "tl", "ddl"]:
            status_code = todo_list(command_parts, login_client)
            if status_code == 1:
                print(f"{command} 命令执行未成功，你可以使用{command} --help获取该命令的帮助")
            continue

        elif command in ["quit", "qq"]:
            status_code = quit(command_parts)
            if status_code == 1:
                print(f"{command} 命令执行未成功，你可以使用{command} --help获取该命令的帮助")
            continue

        elif command in ["list_cloud_files", "lcf"]:
            status_code = list_cloud_files(command_parts, login_client)
            if status_code == 1:
                print(f"{command} 命令执行未成功，你可以使用{command} --help获取该命令的帮助")
            continue

        print(f"{command} 不存在！你可以使用'help'命令获取帮助！")