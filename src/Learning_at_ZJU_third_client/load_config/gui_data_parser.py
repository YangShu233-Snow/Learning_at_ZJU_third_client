import requests
from . import load_config, parse_config
from printlog.print_log import print_log

class RecentVisitCoursesData:
    queries = {
        "course_name": ["name"],
        "course_schedule": ["course_attributes", "teaching_class_name"],
        "cover": ["cover"]
    }
    
    def __init__(self):
        self.recent_visit_courses_data: list[dict] = load_config.apiConfig("user_index", "recent_visit_courses").load_config().get("visited_courses")
        self.results = []
        
        # 获取所有最近浏览课程的课名、课程时间安排与课程封面url
        for recent_visit_course_data in self.recent_visit_courses_data:
            recent_visit_course = parse_config.RecentVisitCourses(recent_visit_course_data, self.queries)
            self.results.extend(recent_visit_course.get_config_data())

        # 加载所有课程的封面图
        for index, recent_visit_course_result in enumerate(self.results):
            recent_visit_course_avatar_url = recent_visit_course_result.get("cover", "")
             
            if recent_visit_course_avatar_url == "":
                print_log("Warning", f"{recent_visit_course_result.get("course_name")}缺少封面url!", "gui_data_parser.RecentVisitCoursesData.__init__")
                self.results[index]["cover"] = None
                continue

            recent_visit_course_avatar = requests.get(recent_visit_course_avatar_url).content
            self.results[index]["cover"] = recent_visit_course_avatar

        print_log("Info", "UserWelcomePage.RecentVisitCourses数据加载完成", "gui_data_parser.RecentVisitCoursesData.__init__")