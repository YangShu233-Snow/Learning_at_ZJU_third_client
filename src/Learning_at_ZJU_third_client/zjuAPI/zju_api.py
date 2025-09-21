import requests
import json
import rich
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import unquote
from requests import Response
from requests.exceptions import HTTPError, RequestException
from typing_extensions import List
from load_config import load_config
from printlog.print_log import print_log

DOWNLOAD_DIR = Path.home() / "Downloads"

class APIFits:
    def __init__(self, login_session: requests.Session, name, apis_name: List[str]|None = None, apis_config: dict|None = None, parent_dir = None, data = None):
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

    def get_api_data(self, auto_load: bool = False)->List[dict]:
        results_json = []
        
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

            api_params = self.make_api_params(api_config = api_config, api_name=api_name)
            api_respone = self.login_session.get(url = api_url, params = api_params)
            api_respone_json = api_respone.json()

            if auto_load:
                api_json_file = load_config.apiConfig(self.parent_dir, api_name)
                api_json_file.update_config(config_data = api_respone_json)

            results_json.append(api_respone_json)

        return results_json

    def post_api_data(self)->List[Response]:
        all_api_response = []
        if self.apis_name == None or self.apis_config == None:
            self.load_api_config()
        
        for api_name in self.apis_name:
            api_config: dict = self.apis_config.get(api_name, None)
            if api_config == None:
                print_log("Error", f"{api_name}不存在！", "zju_api.post_api_data")
                continue
                
            if not self.check_api_method(api_config, "POST"):
                print_log("Error", "该方法只适用POST请求！", "zju_api.APIFits.post_api_data")
                raise RuntimeError

            api_url = self.make_api_url(api_config, api_name)
            if api_url == None:
                print_log("Error", f"{api_name}的{api_url}不存在！", "zju_api.post_api_data")
                continue

            api_respone = self.login_session.post(url = api_url, json = self.data)
            all_api_response.append(api_respone.json())

        return all_api_response

    def make_api_url(self, api_config: dict, api_name):
        return api_config.get("url", None)
    
    def make_api_params(self, api_config: dict, api_name: str):
        return api_config.get("params", None)
    
    def check_api_method(self, apis_config: dict, method: str)->bool:
        for value in apis_config.values():
            if value == method:
                return True
            
            if isinstance(value, dict):
                return self.check_api_method(value, method)
            
        return False

class submissionAPIFits(APIFits):
    def __init__(self, login_session, activity_id, data):
        self.activity_id = activity_id
        super().__init__(login_session, "resources_submission", apis_name=["submissions"], data = data)

    def make_api_url(self, apis_config, api_name):
        return apis_config.get("url", None) + f"/{self.activity_id}/submissions"

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

# --- Course API ---
class coursesAPIFits(APIFits):
    def __init__(self, 
                 login_session: requests.Session, 
                 apis_name = [
                    "list",
                    "view",
                    "modules",
                    "activities",
                    "exams",
                    "exam-scores",
                    "completeness"
                 ],
                 apis_config = None,
                 parent_dir: str = "course",
                 data = None
                 ):
        super().__init__(login_session, "course", apis_name, apis_config, parent_dir, data)

class coursesListAPIFits(coursesAPIFits):
    def __init__(self, 
                 login_session, 
                 keyword: str|None,
                 page: int = 1,
                 show_amount: int = 10,
                 apis_name=["list"]
                 ):
        super().__init__(login_session, apis_name)
        self.keyword = keyword
        self.page = page
        self.show_amount = show_amount

    def make_api_params(self, api_config, api_name: str):
        api_params: dict = api_config.get("params")

        # 修改conditions中的keyword参数为搜索关键词
        conditions: dict = api_params.get("conditions")
        conditions["keyword"] = self.keyword
        # 我的course查询 api 的 conditions 需要为字符串
        api_params["conditions"] = json.dumps(conditions, separators=(',', ':'), ensure_ascii=True)

        api_params["page"] = self.page
        api_params["page_size"] = self.show_amount

        return api_params

class courseViewAPIFits(coursesAPIFits):
    def __init__(self, 
                 login_session: requests.Session, 
                 course_id: int,
                 apis_name=[
                    "view",
                    "modules",
                    "activities",
                    "exams",
                    "completeness",
                    "classrooms",
                    "activities_reads"
                ]
                ):
        super().__init__(login_session, apis_name)
        self.course_id = course_id

    def make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url", None)
        if not base_api_url:
            print_log("Error", f"{api_name}参数url缺失！", "zju_api.courseViewAPIFits.make_api_url")
            return None
        
        api_url = base_api_url.replace("<placeholder>", str(self.course_id))
        return api_url

# --- Assignment API ---
class assignmentAPIFits(APIFits):
    def __init__(self, 
                 login_session, 
                 apis_name = [
                    "activity",
                    "activity_read",
                    "submission_list"
                 ], 
                 apis_config = None, 
                 parent_dir = "assignment", 
                 data = None
                 ):
        super().__init__(login_session, "assignment", apis_name, apis_config, parent_dir, data)

class assignmentPreviewAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 activity_id,
                 apis_name=[
                     "activity_read"
                    ]
                ):
        super().__init__(login_session, apis_name)
        self.activity_id = activity_id

    def make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")
        if not base_api_url:
            print_log("Error", f"{api_name} 缺乏'url'参数", "zju_api.assignmentViewAPIFits.make_api_url")
            return None
        
        api_url = base_api_url.replace("<placeholder>", str(self.activity_id))

        return api_url

class assignmentViewAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 activity_id,
                 apis_name=[
                     "activity"
                     ]
                 ):
        super().__init__(login_session, apis_name)
        self.activity_id = activity_id

    def make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")
        if not base_api_url:
            print_log("Error", f"{api_name} 缺乏'url'参数！", "zju_api.assignmentSubmissionViewAPIFits.make_api_url")
            return None
        
        if api_name == "activity":
            return base_api_url.replace("<placeholder>", str(self.activity_id))

        return super().make_api_url(api_config, api_name)

class assignmentSubmissionListAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 activity_id,
                 student_id,
                 apis_name=["submission_list"]
                 ):
        super().__init__(login_session, apis_name)
        self.activity_id = activity_id
        self.student_id = student_id

    def make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")
        if not base_api_url:
            print_log("Error", f"{api_name} 缺乏'url'参数！", "zju_api.assignmentSubmissionViewAPIFits.make_api_url")
            return None
        
        if api_name == "submission_list":
            return base_api_url.replace("<placeholder1>", str(self.activity_id)).replace("<placeholder2>", str(self.student_id))

        return super().make_api_url(api_config, api_name)

class assignmentTodoListAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 apis_name=["todo"], 
                 ):
        super().__init__(login_session, apis_name)
    
# --- Resource API ---
class resourcesAPIFits(APIFits):
    def __init__(self, 
                 login_session, 
                 apis_name=[
                    "list",
                    "download",
                    "remove",
                    "batch_remove"
                ], 
                apis_config=None, 
                parent_dir="resources", 
                data=None
                ):
        super().__init__(login_session, "resource", apis_name, apis_config, parent_dir, data)

class resourcesListAPIFits(resourcesAPIFits):
    def __init__(self, 
                 login_session, 
                 keyword: str,
                 page: int = 1,
                 show_amount: int = 10,
                 file_type: str = "all",
                 apis_name=["list"],
                ):
        super().__init__(login_session, apis_name)
        self.keyword = keyword
        self.page = page
        self.show_amount = show_amount
        self.file_type = file_type

    def make_api_params(self, api_config: str, api_name: str):
        api_params: dict = api_config.get("params")

        if api_params == None:
            print_log("Error", f"{api_name}缺乏params参数配置！", "zju_api.resourcesListAPIFits.make_api_params")
        
        # conditions这里需要是字符串，所以要解码-赋值-编码来处理
        api_params_conditions: dict = api_params.get("conditions")
        api_params_conditions["keyword"] = self.keyword
        api_params_conditions["fileType"] = self.file_type
        api_params["conditions"] = json.dumps(api_params_conditions, separators=(',', ':'), ensure_ascii=False)
        api_params["page"] = self.page
        api_params["page_size"] = self.show_amount
        return api_params
    
class resourcesDownloadAPIFits(resourcesAPIFits):
    def __init__(self, 
                 login_session, 
                 output_path: Path,
                 resource_id: int|None = None,
                 resources_id: List[int]|None = None,
                 apis_name=["download", "batch_download"]
                ):
        super().__init__(login_session, apis_name)
        if output_path:
            self.output_path = output_path
        else:
            self.output_path = DOWNLOAD_DIR

        self.resource_id = resource_id
        self.resources_id = resources_id

    def make_api_url(self, api_config, api_name):    
        base_api_url: str = api_config.get("url", None)
        if not base_api_url:
            print_log("Error", f"{api_name}参数url缺失！", "zju_api.resourcesDownloadAPIFits.make_api_url")
            return None

        if api_name == "download": 
            return base_api_url.replace("<placeholder>", str(self.resource_id))
        
        return super().make_api_url(api_config, api_name)
    
    def make_api_params(self, api_config, api_name):
        api_params: dict = api_config.get("params", None)
        if not api_params:
            print_log("Error", f"{api_name}参数url缺失！", "zju_api.resourcesDownloadAPIFits.make_api_url")
            return None
        
        if api_name == "batch_download":
            api_params["upload_ids"]= ",".join(map(str, self.resources_id))
            return api_params
        
        return super().make_api_params(api_config, api_name)
    
    def download(self)->bool:
        if self.apis_name == None or self.apis_config == None:
            self.load_api_config()

        if not self.output_path.exists():
            Path(self.output_path).mkdir()

        if not self.output_path.is_dir():
            print_log("Error", f"{self.output_path} 不是一个文件夹路径！", "zju_api.resourcesDownloadAPIFits.download")
            return False

        api_name = "download"
        api_config: dict = self.apis_config.get(api_name)
        if not api_config:
            print_log("Error", f"{api_name}不存在！", "zju_api.resourcesDownloadAPIFits.download")

        api_url = self.make_api_url(api_config, api_name)
        if not api_url:
            print_log("Error", f"{api_name}的{api_url}不存在！", "zju_api.get_api_data")
            return 

        try:
            # 鉴于启用 stream 模式，使用上下文管理器来管理 TCP 连接
            with self.login_session.get(api_url, stream=True, timeout=10) as response:
                response.raise_for_status()

                filename = None
                content_disposition = response.headers.get('Content-Disposition')
                if content_disposition:
                    fn_match = re.search('filename="?(.+)"?', content_disposition)
                    if fn_match:
                        filename = fn_match.group(1).strip('"')
                        filename = filename.encode("latin-1").decode("utf-8")

                if not filename and 'name=' in response.url:
                    filename = unquote(response.url.split("name=")[-1])

                if not filename and 'name=' not in response.url:
                    filename = unquote(response.url.split('/')[-1])

                if not filename:
                    filename = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                print_log("Info", f"获取到文件名: {filename}", "zju_api.resourcesDownloadAPIFits.download")

                file_path = self.output_path / filename

                print_log("Info", f"开始下载文件: {filename}", "zju_api.resourcesDownloadAPIFits.download")
                # 分块读取
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print_log("Info", f"{filename} 下载完成", "zju_api.resourcesDownloadAPIFits.download")
                return True

        except HTTPError as e:
            print_log("Error", f"请求过程中发生 HTTP 错误！错误原因: {e}", "zju_api.resourcesDownloadAPIFits.download")
            return False
        except Exception as e:
            print_log("Error", f"请求过程中发生未知错误！错误原因: {e}", "zju_api.resourcesDownloadAPIFits.download")
            return False
            
    def batch_download(self)->bool:
        if self.apis_name == None or self.apis_config == None:
            self.load_api_config()

        if not self.output_path.exists():
            Path(self.output_path).mkdir()

        if not self.output_path.is_dir():
            print_log("Error", f"{self.output_path} 不是一个文件夹路径！", "zju_api.resourcesDownloadAPIFits.batch_download")
            return False
            
        api_name = "batch_download"
        api_config: dict = self.apis_config.get(api_name)

        if not api_config:
            print_log("Error", f"{api_name}不存在！", "zju_api.resourcesDownloadAPIFits.batch_download")
            return False

        api_url = self.make_api_url(api_config, api_name)
        if api_url == None:
            print_log("Error", f"{api_name}缺少 url 参数！", "zju_api.resourcesDownloadAPIFits.batch_download")
            return False

        api_params = self.make_api_params(api_config=api_config, api_name=api_name)
        if not api_params:
            print_log("Error", f"{api_name}缺少 params 参数！", "zju_api.resourcesDownloadAPIFits.batch_download")

        try:
            with self.login_session.get(api_url, params=api_params, stream=True, timeout=10) as response:
                response.raise_for_status()

                filename = None
                content_disposition = response.headers.get('Content-Disposition')
                if content_disposition:
                    fn_match = re.search(r"filename\*\s*=\s*utf-?8''([^;]+)", content_disposition)
                    if fn_match:
                        filename = fn_match.group(1).strip('"')
                        filename = filename.encode("utf-8").decode("unicode_escape")

                if not filename and 'name=' in response.url:
                    filename = unquote(response.url.split("name=")[-1])

                if not filename:
                    # 默认打包文件的格式为.zip
                    filename = datetime.now().strftime('%Y-%m-%d %H:%M:%S') + ".zip"

                print_log("Info", f"获取到文件名: {filename}", "zju_api.resourcesDownloadAPIFits.download")

                file_path = self.output_path / filename

                print_log("Info", f"开始下载文件: {filename}", "zju_api.resourcesDownloadAPIFits.download")
                # 分块读取
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                print_log("Info", f"{filename} 下载完成", "zju_api.resourcesDownloadAPIFits.download")
                return True

        except HTTPError as e:
            print_log("Error", f"请求过程中发生 HTTP 错误！错误原因: {e}", "zju_api.resourcesDownloadAPIFits.batch_download")
            return False
        except Exception as e:
            print_log("Error", f"请求过程中发生未知错误！错误原因: {e}", "zju_api.resourcesDownloadAPIFits.batch_download")
            return False

class resourcesRemoveAPIFits(resourcesAPIFits):
    def __init__(self, 
                 login_session,
                 resource_id: int|None = None, 
                 resources_id: List[int]|None = None
                 ):
        super().__init__(login_session)
        self.resource_id = resource_id
        self.resources_id = resources_id

    def make_api_params(self, api_config, api_name):
        api_params = api_config.get("params")

        if api_params == None:
            print_log("Error", f"{api_name}缺乏params参数配置！", "zju_api.resourcesListAPIFits.make_api_params")
        
        if api_name == "batch_remove":
            api_params["upload_ids"] = self.resources_id
            return api_params

        return super().make_api_params(api_config, "")


    def make_api_url(self, api_config, api_name):
        base_api_url = api_config.get("url")
        if base_api_url == None:
            print_log("Error", f"{api_name}参数url缺失！", "zju_api.resourcesRemoveAPIFits.make_api_url")
            return 
        if api_name == "remove":
            return base_api_url.replace("<placeholder>", str(self.resource_id))
        return super().make_api_url(api_config, api_name)

    def delete(self)->bool:
        if self.apis_config == None:
            self.load_api_config()

        api_name = "remove"
        api_config: dict = self.apis_config.get(api_name, None)

        if not self.check_api_method(api_config, "DELETE"):
            print_log("Error", "该方法只适用DELET请求！", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            raise RuntimeError

        if api_config == None:
            print_log("Error", f"{api_name}不存在！", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            return False
        
        api_url = self.make_api_url(api_config, api_name)
        if api_url == None:
            print_log("Error", f"{api_name}的{api_url}不存在！", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            return False
        
        try:
            api_respone = self.login_session.delete(url=api_url)
            api_respone.raise_for_status()
            print_log("Info", f"删除成功", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            return True
        except HTTPError as e:
            if api_respone.status_code == 404:
                print_log("Error", "删除失败", "zju_api.resourcesRemoveAPIFits.delete_api_data")
                return False
            
            print_log("Error", f"未知请求错误！错误原因: {e}", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            return False
        except Exception as e:
            print_log("Error", f"未知错误！错误原因: {e}", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            return False
        
    def batch_delete(self):
        if self.apis_config == None:
            self.load_api_config()

        api_name = "batch_remove"
        api_config: dict = self.apis_config.get(api_name, None)

        if not self.check_api_method(api_config, "DELETE"):
            print_log("Error", "该方法只适用DELET请求！", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            raise RuntimeError
        
        if api_config == None:
            print_log("Error", f"{api_name}不存在！", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            return False
        
        api_url = self.make_api_url(api_config, api_name)
        if api_url == None:
            print_log("Error", f"{api_name}的{api_url}不存在！", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            return False

        api_params = self.make_api_params(api_config, api_name)
        
        try:
            api_respone = self.login_session.delete(url=api_url, json=api_params)
            api_respone.raise_for_status()
            print_log("Info", f"删除成功", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            return True
        except HTTPError as e:
            if api_respone.status_code == 404:
                print_log("Error", "删除失败", "zju_api.resourcesRemoveAPIFits.delete_api_data")
                return False
            
            print_log("Error", f"未知请求错误！错误原因: {e}", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            return False
        except Exception as e:
            print_log("Error", f"未知错误！错误原因: {e}", "zju_api.resourcesRemoveAPIFits.delete_api_data")
            return False