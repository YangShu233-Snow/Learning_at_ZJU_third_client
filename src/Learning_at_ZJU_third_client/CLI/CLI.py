from login import login
from zjuAPI import zju_api, courses_search
from load_config import load_config

def login_zju():
    # 执行登录
    print("登录中...")
    login_fit = login.LoginFit()
    login_client = login_fit.login()
    print("登录成功！！！")

    return login_client

def main():
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
            # 检验参数
            if len(command_parts) != 2:
                print(f"'{command}'命令参数不合法！")
                continue
            
            keyword = command_parts[1]
            courses_searcher = courses_search.CoursesSearcher(keyword)
            courses_searcher.search_courses(login_client)

            result = load_config.searchCoursesResults().load_config()

            course_results_count = result.get("total")
            print(f"搜索结果共 {course_results_count} 个")
            
            if course_results_count == 0:
                continue

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
            
            continue