# 弃用
from requests import Response
from load_config import load_config
from printlog.print_log import print_log
from . import zju_api

class CoursesSearcher:
    def __init__(self, login_session: Response):
        self.login_session = login_session

    def search_courses(self, keyword: str = "", auto_load: bool = False):
        if keyword == "":
            print_log("Warning", "查询字符串为空！", "courses_search.CoursesSearcher.__init__")
        courses_api_searcher = zju_api.coursesAPIFits(login_session = self.login_session, keyword = keyword, parent_dir = "search_results")
        return courses_api_searcher.get_api_data(auto_load)