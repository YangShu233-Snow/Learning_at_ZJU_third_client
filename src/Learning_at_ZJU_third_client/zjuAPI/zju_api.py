import requests
from requests import Response
from load_config import load_config
from printlog.print_log import print_log

class APIFits:
    def __init__(self, login_session: requests.Session, name, apis_name = None, apis_config = None, parent_dir = None, data = None):
        self.login_session = login_session
        self.name = name
        self.config = load_config.apiListConfig().load_config().get(self.name, None)
        self.apis_name = apis_name
        self.apis_config = apis_config
        self.parent_dir = parent_dir if parent_dir else name
        self.data = data
    
    def load_api_config(self):
        if self.config == None:
            print_log("Error", f"{self.name}配置项不存在！", "zju_api.load_api_config")
        else:
            if self.apis_name == None:
                self.apis_name = self.config.get("apis_name", None)
            
            if self.apis_config == None:
                self.apis_config = self.config.get("apis_config", None)

        if self.apis_name == None:
            print_log("Error", f"{self.name}配置项\"apis_name\"不存在！", "zju_api.load_api_config")
        
        if self.apis_config == None:
            print_log("Error", f"{self.name}配置项\"apis_config\"不存在！", "zju_api.load_api_config")

    def get_api_data(self):
        if self.apis_name == None or self.apis_config == None:
            self.load_api_config()

        for api_name in self.apis_name:
            api_config: dict = self.apis_config.get(api_name, None)
            if api_config == None:
                print_log("Error", f"{api_name}不存在！", "zju_api.get_api_data")
                continue
            
            api_url = self.make_api_url(api_config, api_name)
            if api_url == None:
                print_log("Error", f"{api_name}的{api_url}不存在！", "zju_api.get_api_data")
                continue

            api_params = self.make_api_params(api_config = api_config)
            api_respone = self.login_session.get(url = api_url, params = api_params)
            api_json_file = load_config.apiConfig(self.parent_dir, api_name)
            api_json_file.update_config(config_data = api_respone.json())

    def post_api_data(self)->Response:
        if self.apis_name == None or self.apis_config == None:
            self.load_api_config()

        if not self.check_api_method(self.apis_config, "POST"):
            print_log("Error", "该方法只适用POST请求！", "zju_api.APIFits.post_api_data")
            raise RuntimeError
        
        for api_name in self.apis_name:
            api_config: dict = self.apis_config.get(api_name, None)
            if api_config == None:
                print_log("Error", f"{api_name}不存在！", "zju_api.get_api_data")
                continue
            
            api_url = self.make_api_url(api_config, api_name)
            if api_url == None:
                print_log("Error", f"{api_name}的{api_url}不存在！", "zju_api.get_api_data")
                continue

            api_respone = self.login_session.post(url = api_url, json = self.data)
            return api_respone

    def make_api_url(self, api_config: dict, api_name):
        return api_config.get("url", None)
    
    def make_api_params(self, api_config: dict):
        return api_config.get("params", None)
    
    def check_api_method(self, apis_config: dict, method: str):
        for value in apis_config.values():
            if value == method:
                return True
            
            if isinstance(value, dict):
                self.check_api_method(value, method)
                return True
            
        return False

class submissionAPIFits(APIFits):
    def __init__(self, login_session, activity_id, data):
        self.activity_id = activity_id
        super().__init__(login_session, "resources_submission", apis_name=["submissions"], data = data)

    def make_api_url(self, apis_config, api_name):
        return apis_config.get("url", None) + f"/{self.activity_id}/submissions"


class resourcesListAPIFits(APIFits):
    def __init__(self, login_session):
        super().__init__(login_session, "resources_list")

class coursePageAPIFits(APIFits):
    def __init__(self, login_session: requests.Response, course_id: str):
        super().__init__(login_session, "course_page")
        self.course_id = course_id

    def make_api_url(self, api_config, api_name):
        base_api_url = api_config.get("url", None)
        if base_api_url == None:
            print_log("Error", f"{api_name}参数url缺失！", "zju_api.courseContentAPIFits.make_api_url")
            return None
        
        if api_name == "homework":
            print(base_api_url + f"/{self.course_id}/{api_name}/submission-status")
            return base_api_url + f"/{self.course_id}/{api_name}/submission-status"

        return base_api_url + f"/{self.course_id}/{api_name}"

class coursesAPIFits(APIFits):
    def __init__(self, login_session: requests.Response, parent_dir: str = "courses", keyword: str = ""):
        super().__init__(login_session, "courses")
        self.parent_dir = parent_dir
        self.keyword = keyword

    def make_api_params(self, api_config):
        # 修改conditions中的keyword参数为搜索关键词
        api_params: dict = api_config.get("params")
        default_conditions: str = api_params.get("conditions")
        search_conditions = default_conditions.replace("{{{keyword}}}", self.keyword)
        api_params["conditions"] = search_conditions

        return api_params


class userIndexAPIFits(APIFits):
    def __init__(self, login_session: requests.Session):
        super().__init__(login_session, "user_index")
        
    def make_api_url(self, api_config, api_name):
        base_api_url = api_config.get("url", None)
        if base_api_url == None:
            return None
        
        if api_name == "notifications":
            userid = load_config.userConfig().load_config().get("userid", None)

            if userid == None:
                print_log("Error", "User Config配置文件缺少userid参数！", f"zju_api.{self.name}.make_api_url")
                return None
            
            return base_api_url + f"/{userid}/{api_name}"

        return base_api_url
    
class todoListLiteAPIFits(APIFits):
    def __init__(self, login_session: requests.Session):
        super().__init__(login_session, "todo_list_lite", parent_dir="user_index")