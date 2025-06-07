from requests import Response
from load_config import load_config
from printlog.print_log import print_log
from zjuAPI import zju_api

class CoursesSearcher:
    def __init__(self, keyword: str = ""):
        if keyword == "":
            print_log("Warning", "查询字符串为空！", "courses_search.CoursesSearcher.__init__")

        self.keyword = keyword

    def search_courses(self, login_session: Response):
        courses_api_searcher = zju_api.coursesAPIFits(login_session = login_session, keyword = self.keyword, parent_dir = "search_results")
        courses_api_searcher.get_api_data()