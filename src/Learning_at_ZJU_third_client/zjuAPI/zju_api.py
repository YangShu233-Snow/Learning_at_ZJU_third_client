import requests
import time
from load_config import load_config
from printlog.print_log import print_log

class APIFits:
    def __init__(self, login_session: requests.Session, name):
        self.login_session = login_session
        self.name = name
        self.config = load_config.apiListConfig().load_config().get(self.name, None)
        self.apis_name = None
        self.apis_config = None
        self.parent_dir = name
    
    def load_api_config(self):
        if self.config == None:
            print_log("Error", f"{self.name}配置项不存在！", "zju_api.load_api_config")
        else:
            self.apis_name = self.config.get("apis_name", None)
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

            api_params = api_config.get("params", None)
            api_respone = self.login_session.get(url=api_url, params=api_params)
            api_json_file = load_config.apiConfig(self.parent_dir, api_name)
            api_json_file.update_config(config_data=api_respone.json())

    def make_api_url(self, api_config: dict, api_name):
        return api_config.get("url", None)

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
    def __init__(self, login_session: requests.Response):
        super().__init__(login_session, "courses")

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