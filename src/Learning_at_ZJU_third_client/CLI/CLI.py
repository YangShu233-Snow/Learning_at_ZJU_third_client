from login import login
from zjuAPI import zju_api, courses_search
from load_config import load_config
from upload import file_upload
from printlog.print_log import print_log
from pathlib import Path
from requests.exceptions import HTTPError
import sys
from datetime import datetime, timezone
from colorama import Fore, Style, init

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
        course_time = course.get("course_attributes").get("teaching_class_name")
        course_teachers = course.get("instructors")
        teachers_name = []
        for teacher in course_teachers:
            name = teacher.get("name", "null")
            teachers_name.append(name)
        
        print("=========================")
        print(course_name)
        print(f"上课时间：{course_time}")
        print(f"任课教师：{"、".join(teachers_name)}")
        print("=========================")

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

    if len(file_paths) == 0:
        print("没有文件/文件夹可以上传！")
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
        print_log("Error", "上传发生未知错误！", "CLI.CLI.upload_files")
        return 1

    print("文件上传完成！")
    return 0

def print_todo_colorful(todo_attributes: dict):
    # 定义不同紧急程度的颜色和标签
    # (下限天数, 上限天数, 颜色代码, 标签)
    ddl_urgency = (
        (0, 1, '\033[91m', "即将截止"),  # 1天内：红色
        (1, 3, '\033[93m', "略有余地"),  # 3天内：黄色
        (3, 7, '\033[94m', "计划之中")   # 7天内：蓝色
    )
    # 默认颜色（7天以上）：绿色
    color_code = '\033[92m'
    RESET = '\033[0m'
    
    # 从传入的字典中获取截止日期
    todo_deadline = todo_attributes.get("todo_deadline")
    
    # 获取当前的UTC时间，以确保时区匹配
    now_time = datetime.now(timezone.utc)

    # 判断任务是否已经截止
    if todo_deadline > now_time:
        #【修复】正确计算时间差
        time_to_ddl = todo_deadline - now_time
        # 设置一个默认的紧急程度
        todo_attributes["todo_urgency"] = "远在天边"
        
        # 遍历紧急程度定义，设置对应的颜色和标签
        for urgency in ddl_urgency:
            #【修复】使用 time_to_ddl.days 进行正确的总天数比较
            if time_to_ddl.days < urgency[1]:
                color_code = urgency[2]
                todo_attributes["todo_urgency"] = urgency[3]
                break
    else:
        color_code = '\033[1;91m' # 加粗红色
        todo_attributes["todo_urgency"] = "已经截止"

    # 为了更好的视觉效果，将整个任务信息块都着色
    print(f"{color_code}===================={RESET}")
    print(f"{color_code}{todo_attributes.get('todo_title')}{RESET}")
    print(f"{color_code}截止日期: {todo_attributes.get('todo_deadline').strftime('%Y-%m-%d %H:%M:%S')} {todo_attributes.get('todo_urgency')}{RESET}")
    print(f"{color_code}任务id: {todo_attributes.get('todo_id')}{RESET}")
    print(f"{color_code}任务类型: {todo_attributes.get('todo_type')}{RESET}")
    print(f"{color_code}课程名称: {todo_attributes.get('todo_course_name')}{RESET}")
    print(f"{color_code}课程id: {todo_attributes.get('todo_course_id')}{RESET}")

def todo_list(command_parts: list[str], login_client):
    command = command_parts[0]
    show_amount = 5
    offset = 0
    end = 0
    
    # 检验参数
    if "--help" in command_parts:
        HelpManual.todo_list_help()
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
                print("====================")
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
        print("====================")

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