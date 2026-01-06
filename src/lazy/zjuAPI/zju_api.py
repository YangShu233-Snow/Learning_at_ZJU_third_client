import asyncio
import json
import logging
import mimetypes
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional
from urllib.parse import unquote

import aiofiles
import httpx
import requests
from httpx import ConnectTimeout, HTTPError, HTTPStatusError

from ..load_config import load_config

DOWNLOAD_DIR = Path.home() / "Downloads"

logger = logging.getLogger(__name__)

class fileUploadProgressWrapper:
    def __init__(self,
                 file,
                 progress_callback: Optional[Callable[[int, int], None]] = None):
        self._file = file
        self._callback = progress_callback
        self._total_size = os.fstat(self._file.fileno()).st_size
        self._bytes_read = 0

    def read(self, size=-1):
        """request库会调用这个方法流式读取
        """
        chunk = self._file.read(size)
        if chunk:
            self._bytes_read += len(chunk)
            # 如果给出了回调函数
            if self._callback:
                # 向上报告进度
                try:
                    self._callback(self._bytes_read, self._total_size)
                except Exception as e:
                    logger.error(f"{e}")

        return chunk
    
    def __len__(self):
        """request库通过这个方法获知文件大小
        """

        return self._total_size

class APIFits:
    def __init__(self, login_session: requests.Session, name, apis_name: List[str]|None = None, apis_config: dict|None = None, parent_dir = None, data = None):
        self.login_session = login_session
        self.name = name
        self.config = load_config.apiListConfig().load_config().get(self.name, None)
        self.apis_name = apis_name
        self.apis_config = apis_config
        self.parent_dir = parent_dir if parent_dir else name
        self.data = data
    
    def _load_api_config(self):
        if self.config == None:
            logger.error(f"{self.name}配置项不存在！")
        else:
            if self.apis_name == None:
                self.apis_name = self.config.get("apis_name", None)
            
            if self.apis_config == None:
                self.apis_config = self.config.get("apis_config", None)

        if self.apis_name == None:
            logger.error(f"{self.name}配置项\"apis_name\"不存在！")
        
        if self.apis_config == None:
            logger.error(f"{self.name}配置项\"apis_config\"不存在！")

    def get_api_data(self, auto_load: bool = False)->List[dict]:
        results_json = []
        
        if self.apis_name == None or self.apis_config == None:
            self._load_api_config()

        for api_name in self.apis_name:
            api_config: dict = self.apis_config.get(api_name, None)
            if api_config == None:
                logger.error(f"{api_name}不存在！")
                continue
            
            api_url = self._make_api_url(api_config, api_name)
            if api_url == None:
                logger.error(f"{api_name}的{api_url}不存在！")
                continue

            api_params = self._make_api_params(api_config = api_config, api_name=api_name)
            logger.info(f"请求 {api_url} 中...")
            logger.info(f"参数为 {api_config.items()}")
            
            try:
                api_respone = self.login_session.get(url = api_url, params = api_params)
                api_respone.raise_for_status()
            except HTTPError as e:
                logger.error(f"请求{api_respone.url}时发生错误。{e}")
                results_json.append({})
                continue
            
            api_respone_json = api_respone.json()

            if auto_load:
                api_json_file = load_config.apiConfig(self.parent_dir, api_name)
                api_json_file.update_config(config_data = api_respone_json)

            results_json.append(api_respone_json)

        return results_json

    def post_api_data(self)->List[dict]:
        all_api_response = []
        if self.apis_name == None or self.apis_config == None:
            self._load_api_config()
        
        for api_name in self.apis_name:
            api_config: dict = self.apis_config.get(api_name, None)
            if api_config == None:
                logger.error(f"{api_name}不存在！")
                continue
                
            if not self.check_api_method(api_config, "POST"):
                logger.error("该方法只适用POST请求！")
                raise RuntimeError

            api_url = self._make_api_url(api_config, api_name)
            if api_url == None:
                logger.error(f"{api_name}的{api_url}不存在！")
                continue

            logger.info(f"请求 {api_url} 中...")
            if self.data:
                logger.info(f"载荷为 {self.data.items()}")
            
            try:
                api_respone = self.login_session.post(url = api_url, json = self.data)
                api_respone.raise_for_status()
            except HTTPError as e:
                logger.error(f"请求{api_respone.url}时发生错误。{e}")
                all_api_response.append({})
                continue

            all_api_response.append(api_respone.json())

        return all_api_response
    
    def put_api_data(self)->List[dict|bool]:
        all_api_response = []
        if self.apis_name == None or self.apis_config == None:
            self._load_api_config()

        for api_name in self.apis_name:
            api_config: dict = self.apis_config.get(api_name, None)
            
            if not api_config:
                logger.error(f"{api_name}不存在！")
                continue

            if not self.check_api_method(api_config, "PUT"):
                logger.error("该方法只适用PUT请求！")
                raise RuntimeError
            
            api_url = self._make_api_url(api_config, api_name)
            if api_url == None:
                logger.error(f"{api_name}的{api_url}不存在！")
                continue
            
            logger.info(f"请求 {api_url} 中...")
            api_response = self.login_session.put(url = api_url, json = self.data)
            try:
                api_response.raise_for_status()
            except HTTPError as e:
                logger.error(f"Put请求失败！{api_response.url}: {e}")
                all_api_response.append(False)
            else:
                all_api_response.append(api_response.json())

        return all_api_response

    def _make_api_url(self, api_config: dict, api_name):
        return api_config.get("url")
    
    def _make_api_params(self, api_config: dict, api_name: str):
        return api_config.get("params")
    
    def check_api_method(self, apis_config: dict, method: str)->bool:
        for value in apis_config.values():
            if value == method:
                return True
            
            if isinstance(value, dict):
                return self.check_api_method(value, method)
            
        return False

class APIFitsAsync:
    def __init__(self, login_session: httpx.AsyncClient, name, apis_name: List[str]|None = None, apis_config: dict|None = None, parent_dir = None, data = None):
        self.login_session = login_session
        self.name = name
        self.config = load_config.apiListConfig().load_config().get(self.name, None)
        self.apis_name = apis_name
        self.apis_config = apis_config
        self.parent_dir = parent_dir if parent_dir else name
        self.data = data
    
    def _load_api_config(self):
        if self.config == None:
            logger.error(f"{self.name}配置项不存在！")
        else:
            if self.apis_name == None:
                self.apis_name = self.config.get("apis_name", None)
            
            if self.apis_config == None:
                self.apis_config = self.config.get("apis_config", None)

        if self.apis_name == None:
            logger.error(f"{self.name}配置项\"apis_name\"不存在！")
        
        if self.apis_config == None:
            logger.error(f"{self.name}配置项\"apis_config\"不存在！")

    async def get_api_data(self, auto_load: bool = False)->List[dict]:
        if self.apis_name == None or self.apis_config == None:
            self._load_api_config()

        tasks = []
        api_urls = []
        for api_name in self.apis_name:
            api_config: dict = self.apis_config.get(api_name, None)
            if api_config == None:
                logger.error(f"{api_name}不存在！")
                continue
            
            api_url    = self._make_api_url(api_config, api_name)
            api_params = self._make_api_params(api_config = api_config, api_name=api_name)

            if api_url == None:
                logger.error(f"{api_name}的{api_url}不存在！")
                continue

            tasks.append(self.login_session.get(url=api_url, params=api_params, follow_redirects=True))
            api_urls.append(api_url)

        logger.info(f"开始请求API: {', '.join(api_urls)}")
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        results_json = []
        for index, api_response in enumerate(responses):
            if isinstance(api_response, Exception):
                error_url = api_urls[index] if index < len(api_urls) else "Unkown_URL"
                logger.error(f"请求时发生错误 | URL: {error_url} | 异常: {type(api_response)} | 详情: {repr(api_response)}")
                results_json.append({})
                continue

            try:    
                api_response.raise_for_status()
                api_respone_json = api_response.json()
            except HTTPStatusError as e:
                logger.error(f"请求{api_response.url}时发生错误。{e}")
                results_json.append({})
                continue
            except ConnectTimeout as e:
                logger.error(f"请求{api_response.url}超时！{e}")
                results_json.append({})
                continue

            if auto_load:
                api_json_file = load_config.apiConfig(self.parent_dir, api_name)
                api_json_file.update_config(config_data = api_respone_json)

            results_json.append(api_respone_json)

        return results_json

    async def post_api_data(self)->List[dict]:
        if self.apis_name == None or self.apis_config == None:
            self._load_api_config()
        
        tasks = []
        api_urls = []
        for api_name in self.apis_name:
            api_config: dict = self.apis_config.get(api_name, None)
            if api_config == None:
                logger.error(f"{api_name}不存在！")
                continue
                
            if not self.check_api_method(api_config, "POST"):
                logger.error("该方法只适用POST请求！")
                continue

            api_url = self._make_api_url(api_config, api_name)
            if api_url == None:
                logger.error(f"{api_name}的{api_url}不存在！")
                continue
            
            if not self.data:
                self.data = self._make_api_data(api_config, api_name)
            
            tasks.append(self.login_session.post(url=api_url, json=self.data, follow_redirects=True))
            api_urls.append(api_url)

        logger.info(f"请求 {', '.join(api_urls)}")
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"发生未知错误！{e}")
        
        all_api_response = []
        for api_response in responses:
            if isinstance(api_response, Exception):
                logger.error(f"请求时发生错误: {api_response}")
                all_api_response.append({})
                continue

            try:
                api_response.raise_for_status()
                all_api_response.append(api_response.json())
            except HTTPError as e:
                logger.error(f"请求{api_response.url}时发生错误。{e}")
                all_api_response.append({})
            except ConnectTimeout as e:
                logger.error(f"请求 {api_response.url} 超时！{e}")
                all_api_response.append({})
            except Exception as e:
                logger.error(f"未知错误！{e}")
                all_api_response.append({})

        return all_api_response
    
    async def put_api_data(self)->List[dict|bool]:
        all_api_response = []
        if self.apis_name == None or self.apis_config == None:
            self._load_api_config()

        for api_name in self.apis_name:
            api_config: dict = self.apis_config.get(api_name, None)
            
            if not api_config:
                logger.error(f"{api_name}不存在！")
                continue

            if not self.check_api_method(api_config, "PUT"):
                logger.error("该方法只适用PUT请求！")
                raise RuntimeError
            
            api_url = self._make_api_url(api_config, api_name)
            if api_url == None:
                logger.error(f"{api_name}的{api_url}不存在！")
                continue
            
            logger.info(f"请求 {api_url} 中...")
            api_response = await self.login_session.put(url = api_url, json = self.data, follow_redirects=True)
            try:
                api_response.raise_for_status()
            except HTTPError as e:
                logger.error(f"Put请求失败！{api_response.url}: {e}")
                all_api_response.append(False)
            except ConnectTimeout as e:
                logger.error(f"请求 {api_response.url} 超时！{e}")
                all_api_response.append({})
            except Exception as e:
                logger.error(f"未知错误！{e}")
            else:
                all_api_response.append(api_response.json())

        return all_api_response

    def _make_api_url(self, api_config: dict, api_name):
        return api_config.get("url")
    
    def _make_api_params(self, api_config: dict, api_name: str):
        return api_config.get("params")
    
    def _make_api_data(self, api_config: dict, api_name: str):
        return api_config.get("data", {})
    
    def check_api_method(self, apis_config: dict, method: str)->bool:
        for value in apis_config.values():
            if value == method:
                return True
            
            if isinstance(value, dict):
                return self.check_api_method(value, method)
            
        return False

# --- Course API ---
class coursesAPIFits(APIFitsAsync):
    def __init__(self, 
                 login_session: requests.Session, 
                 apis_name = None,
                 apis_config = None,
                 parent_dir: str = "course",
                 data = None
                 ):
        if apis_name is None:
            apis_name = ["list", "view", "modules", "activities", "exams", "exam-scores", "completeness", "classrooms", "activities_reads", "coursewares", "rollcalls"]
        super().__init__(login_session, "course", apis_name, apis_config, parent_dir, data)

class coursesListAPIFits(coursesAPIFits):
    def __init__(self, 
                 login_session, 
                 keyword: str|None,
                 page: int = 1,
                 show_amount: int = 10,
                 apis_name=None
                 ):
        if apis_name is None:
            apis_name = ["list"]
        super().__init__(login_session, apis_name)
        self.keyword = keyword
        self.page = page
        self.show_amount = show_amount

    def _make_api_params(self, api_config, api_name: str):
        api_params: dict = api_config.get("params")

        # 修改conditions中的keyword参数为搜索关键词
        conditions: dict = api_params.get("conditions")
        conditions["keyword"] = self.keyword
        # 我的course查询 api 的 conditions 需要为字符串
        api_params["conditions"] = json.dumps(conditions, separators=(',', ':'), ensure_ascii=True)

        api_params["page"] = self.page
        api_params["page_size"] = self.show_amount

        return api_params

class coursePreviewAPIFits(coursesAPIFits):
    def __init__(self, 
                 login_session, 
                 course_id: int,
                 apis_name=None
                ):
        if apis_name is None:
            apis_name = ["view", "modules"]
        super().__init__(login_session, apis_name)
        self.course_id = course_id

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url", None)
        if not base_api_url:
            logger.error(f"{api_name}参数url缺失！")
            return None
        
        return base_api_url.replace("<placeholder>", str(self.course_id))

class courseViewAPIFits(coursesAPIFits):
    def __init__(self, 
                 login_session: requests.Session, 
                 course_id: int,
                 apis_name=None
                ):
        if apis_name is None:
            apis_name = ["activities", "exams", "classrooms", "activities_reads", "homework-completeness", "exam-completeness"]
        super().__init__(login_session, apis_name)
        self.course_id = course_id

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url", None)
        if not base_api_url:
            logger.error(f"{api_name}参数url缺失！")
            return None
        
        return base_api_url.replace("<placeholder>", str(self.course_id))

class coursewaresViewAPIFits(coursesAPIFits):
    def __init__(self, 
                 login_session, 
                 course_id: int,
                 page: int,
                 page_size: int,
                 apis_name=None
                 ):
        if apis_name is None:
            apis_name = ["coursewares"]
        super().__init__(login_session, apis_name)
        self.course_id = course_id
        self.page = page
        self.page_size = page_size

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")
        
        if not base_api_url:
            logger.error(f"{api_name}参数url缺失！")
            return None 

        if api_name == "coursewares":
            return base_api_url.replace("<placeholder>", str(self.course_id))

        return super()._make_api_url(api_config, api_name)
    
    def _make_api_params(self, api_config, api_name):
        api_params: dict = api_config.get("params")

        if not api_params:
            logger.error(f"{api_name}参数params缺失！")
            return None 
        
        if api_name == "coursewares":
            conditions: dict         = api_params.get("conditions", {})
            conditions["category"]   = "null"
            api_params["conditions"] = json.dumps(conditions)
            api_params["page"]       = self.page
            api_params["page_size"]  = self.page_size
            return api_params

        return super()._make_api_params(api_config, api_name)

class courseMembersViewAPIFits(coursesAPIFits):
    def __init__(self, 
                 login_session, 
                 course_id: int,
                 apis_name=None
                 ):
        if apis_name is None:
            apis_name = ["enrollments"]
        super().__init__(login_session, apis_name)
        self.course_id = course_id

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")

        if not base_api_url:
            logger.error(f"{api_name}参数url缺失！")
            return None
        
        if api_name == "enrollments":
            return base_api_url.replace("<placeholder>", str(self.course_id))
        
        return super()._make_api_url(api_config, api_name)

class courseRollcallsViewAPIFits(coursesAPIFits):
    def __init__(self, 
                 login_session,
                 course_id: int,
                 student_id: int,
                 apis_name=None
                 ):
        if apis_name is None:
            apis_name = ["rollcalls"]
        super().__init__(login_session, apis_name)
        self.course_id = course_id
        self.student_id = student_id

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url", None)
        if not base_api_url:
            logger.error(f"{api_name}参数url缺失！")
            return None

        return base_api_url.replace("<placeholder1>", str(self.course_id)).replace("<placeholder2>", str(self.student_id))

# --- Assignment API ---
class assignmentAPIFits(APIFitsAsync):
    def __init__(self, 
                 login_session, 
                 apis_name = None, 
                 apis_config = None, 
                 parent_dir = "assignment", 
                 data = None
                 ):
        if apis_name is None:
            apis_name = ["activity", "activity_read", "submission_list", "todo", "exam", "exam_submission_list", "exam_subjects_summary", "exam_distribute", "classroom", "classroom_submissions"]
        super().__init__(login_session, "assignment", apis_name, apis_config, parent_dir, data)

class assignmentPreviewAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 activity_id,
                 apis_name=None
                ):
        if apis_name is None:
            apis_name = ["activity_read"]
        super().__init__(login_session, apis_name)
        self.activity_id = activity_id

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")
        if not base_api_url:
            logger.error(f"{api_name} 缺乏'url'参数")
            return None
        
        return base_api_url.replace("<placeholder>", str(self.activity_id))


class assignmentViewAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 activity_id,
                 apis_name=None
                 ):
        if apis_name is None:
            apis_name = ["activity"]
        super().__init__(login_session, apis_name)
        self.activity_id = activity_id

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")
        if not base_api_url:
            logger.error(f"{api_name} 缺乏'url'参数！")
            return None
        
        if api_name == "activity":
            return base_api_url.replace("<placeholder>", str(self.activity_id))

        return super()._make_api_url(api_config, api_name)

class assignmentSubmissionListAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 activity_id,
                 student_id,
                 apis_name=None
                 ):
        if apis_name is None:
            apis_name = ["submission_list"]
        super().__init__(login_session, apis_name)
        self.activity_id = activity_id
        self.student_id = student_id

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")
        if not base_api_url:
            logger.error(f"{api_name} 缺乏'url'参数！")
            return None
        
        if api_name == "submission_list":
            # return base_api_url.replace("<placeholder1>", str(self.activity_id)).replace("<placeholder2>", str(self.student_id))
            return base_api_url.replace("<placeholder1>", str(self.activity_id)).replace("<placeholder2>", str(self.student_id))
        return super()._make_api_url(api_config, api_name)

class assignmentTodoListAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 apis_name=None, 
                 ):
        if apis_name is None:
            apis_name = ["todo"]
        super().__init__(login_session, apis_name)

class assignmentExamViewAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 exam_id: int,
                 apis_name=None 
    ):
        if apis_name is None:
            apis_name = ["exam", "exam_submission_list", "exam_distribute"]
        super().__init__(login_session, apis_name)
        self.exam_id = exam_id

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")

        if not base_api_url:
            logger.error(f"{api_name} 缺乏'url'参数！")
            return None
        
        if api_name in ["exam", "exam_submission_list", "exam_distribute"]:
            return base_api_url.replace("<placeholder>", f"{self.exam_id}")

        return super()._make_api_url(api_config, api_name)

class assignmentExanSubmissionViewAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 exam_id: int,
                 submission_id: int,
                 apis_name=None):
        if apis_name is None:
            apis_name = ["exam_submission"]
        super().__init__(login_session, apis_name)
        self.exam_id       = exam_id
        self.submission_id = submission_id

    def _make_api_url(self, api_config, api_name)->str|None:
        base_api_url: str = api_config.get("url")

        if not base_api_url:
            logger.error(f"{api_name} 缺乏'url'参数")
            return None
        
        if api_name == "exam_submission":
            return base_api_url.replace("<placeholder1>", str(self.exam_id)).replace("<placeholder2>", str(self.submission_id))
        
        return super()._make_api_url(api_config, api_name)

class assignmentClassroomViewAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 classroom_id: int,
                 apis_name=None, 
                 ):
        if apis_name is None:
            apis_name = ["classroom", "classroom_submissions", "classroom_subject_result", "classroom_subject"]
        super().__init__(login_session, apis_name)
        self.classroom_id = classroom_id

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")

        if not base_api_url:
            logger.error(f"{api_name} 缺乏'url'参数！")

        if api_name in ["classroom", "classroom_submissions", "classroom_subject", "classroom_subject_result"]:
            return base_api_url.replace("<placeholder>", str(self.classroom_id))
        
        return super()._make_api_url(api_config, api_name)

class assignmentSubmitAPIFits(assignmentAPIFits):
    def __init__(self, 
                 login_session, 
                 assignment_id: int,
                 comment: str = None,
                 uploads: List[int] = None,
                 apis_name=None, 
                ):
        if apis_name is None:
            apis_name = ["submissions"]
        if uploads is None:
            uploads = []
        super().__init__(login_session, apis_name)
        self.assignment_id = assignment_id
        self.comment = comment
        self.uploads = uploads

    def _make_api_url(self, api_config, api_name)->str|None:
        base_api_url: str = api_config.get("url")

        if not base_api_url:
            logger.error(f"{api_name} 缺少url！")
            return None
        
        if api_name == "submissions":
            return base_api_url.replace("<placeholder>", str(self.assignment_id))

        return super()._make_api_url(api_config, api_name)
    
    def _make_api_data(self, api_config, api_name)->dict|None:
        default_api_data = api_config.get("data")

        if not default_api_data:
            logger.error(f"{api_name} 缺少data！")
            return None
        
        if api_name == "submissions":
            api_data = default_api_data
            if self.comment:
                api_data["comment"] = api_data.get("comment", "").replace("{{{comment}}}", self.comment)
            else:
                api_data["comment"] = None
                
            api_data["uploads"].extend(self.uploads)
            return api_data
        
        return super()._make_api_data(api_config, api_name)
    
    async def submit(self)->bool:
        if not self.apis_name or not self.apis_config:
            self._load_api_config()

        api_name = "submissions"
        api_config: dict = self.apis_config.get(api_name, None)
        if api_config == None:
            logger.error(f"{api_name}不存在！")
            return False
            
        if not self.check_api_method(api_config, "POST"):
            logger.error("该方法只适用POST请求！")
            return False
        
        api_config: dict = self.apis_config.get(api_name)
        if not api_config:
            logger.error(f"{api_name}不存在！")
            return False

        api_url = self._make_api_url(api_config, api_name)
        if not api_url:
            logger.error(f"{api_name}的url不存在！")
            return False
        
        api_data = self._make_api_data(api_config, api_name)
        if not api_data:
            logger.error(f"{api_name}的data不存在！")
            return False

        try:
            response = await self.login_session.post(
                url=api_url,
                json=api_data
            )

            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(f"请求 {api_url} 时发生错误！{e}")
            return False
        except Exception as e:
            logger.error(f"发生未知错误！{e}")
            return False
        
        return True

# --- Resource API ---
class resourcesAPIFits(APIFitsAsync):
    def __init__(self, 
                 login_session, 
                 apis_name=None, 
                apis_config=None, 
                parent_dir="resources", 
                data=None
                ):
        if apis_name is None:
            apis_name = ["list", "download", "remove", "batch_remove", "upload"]
        super().__init__(login_session, "resource", apis_name, apis_config, parent_dir, data)

class resourcesListAPIFits(resourcesAPIFits):
    def __init__(self, 
                 login_session, 
                 keyword: str,
                 page: int = 1,
                 show_amount: int = 10,
                 file_type: str = "all",
                 apis_name=None,
                ):
        if apis_name is None:
            apis_name = ["list"]
        super().__init__(login_session, apis_name)
        self.keyword = keyword
        self.page = page
        self.show_amount = show_amount
        self.file_type = file_type

    def _make_api_params(self, api_config: str, api_name: str):
        api_params: dict = api_config.get("params")

        if api_params == None:
            logger.error(f"{api_name}缺乏params参数配置！")
        
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
                 basename: str|None = None,
                 apis_name=None
                ):
        if apis_name is None:
            apis_name = ["download", "batch_download"]
        super().__init__(login_session, apis_name)
        if output_path:
            self.output_path = output_path
        else:
            self.output_path = DOWNLOAD_DIR

        self.resource_id = resource_id
        self.resources_id = resources_id
        self.basename = basename

    def _make_api_url(self, api_config, api_name):    
        base_api_url: str = api_config.get("url", None)
        if not base_api_url:
            logger.error(f"{api_name}参数url缺失！")
            return None

        if api_name == "download": 
            return base_api_url.replace("<placeholder>", str(self.resource_id))
        
        return super()._make_api_url(api_config, api_name)
    
    def _make_api_params(self, api_config, api_name):
        api_params: dict = api_config.get("params", None)
        if not api_params:
            logger.error(f"{api_name}参数url缺失！")
            return None
        
        if api_name == "batch_download":
            api_params["upload_ids"]= ",".join(map(str, self.resources_id))
            return api_params
        
        return super()._make_api_params(api_config, api_name)
    
    async def download(self, 
                 progress_callback: Optional[Callable[[int, int, str], None]] = None
                 )->bool:
        
        if self.apis_name == None or self.apis_config == None:
            self._load_api_config()

        if not self.output_path.exists():
            Path(self.output_path).mkdir()

        if not self.output_path.is_dir():
            logger.error(f"{self.output_path} 不是一个文件夹路径！")
            return False

        api_name = "download"
        api_config: dict = self.apis_config.get(api_name)
        if not api_config:
            logger.error(f"{api_name}不存在！")

        api_url = self._make_api_url(api_config, api_name)
        if not api_url:
            logger.error(f"{api_name}的{api_url}不存在！")
            return None 

        try:
            # 鉴于启用 stream 模式，使用上下文管理器来管理 TCP 连接
            async with self.login_session.stream("GET", api_url, timeout=20, follow_redirects=True) as response:
                response.raise_for_status()

                # 获取文件名
                filename = None
                content_disposition = response.headers.get('Content-Disposition')
                if content_disposition:
                    logger.info(f"获取到'content_disposition': {content_disposition}")
                    fn_match = re.search(r'filename\*\s*=\s*utf-?8''([^;]+)', content_disposition)
                    
                    if fn_match:
                        potential_filename = fn_match.group(1).strip('"')
                        filename = unquote(potential_filename)
                    # 如果没有找到 filename*，再尝试匹配非标准的 filename="..."
                    else:
                        fn_match = re.search(r'filename="?(.+)"', content_disposition)
                        if fn_match:
                            try:
                                filename = fn_match.group(1).encode('latin-1').decode('utf-8')
                            except UnicodeError:
                                filename = fn_match.group(1) # 如果解码失败，使用原始字符串
                else:
                    logger.warning("未获取到content_disposition")
                
                if not filename:
                    response_url = Path(str(response.url))
                    filename = unquote(response_url.name)

                if not filename:
                    filename = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if self.basename:
                    filename = f"{self.basename}_{filename}"

                logger.info(f"获取到文件名: {filename}")

                file_path = self.output_path / filename

                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                download_size = 0

                logger.info(f"开始下载文件: {filename}")
                # 分块读取
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        if chunk:
                            await f.write(chunk)
                            download_size += len(chunk)

                            # 如果上层提供了进度回调，则通知状态
                            if progress_callback:
                                try:
                                    progress_callback(download_size, total_size, filename)
                                except Exception as e:
                                    logger.warning(f"进度回调函数出错: {e}")

                logger.info(f"{filename} 下载完成")
                return True

        except HTTPError as e:
            logger.error(f"请求过程中发生 HTTP 错误！错误原因: {e}")
            return False
        except Exception as e:
            logger.error(f"请求过程中发生未知错误！错误原因: {e}")
            return False
            
    async def batch_download(self,
                       progress_callback: Optional[Callable[[int, int, str], None]]|None = None
                       )->bool:
        
        if self.apis_name == None or self.apis_config == None:
            self._load_api_config()

        if not self.output_path.exists():
            Path(self.output_path).mkdir()

        if not self.output_path.is_dir():
            logger.error(f"{self.output_path} 不是一个文件夹路径！")
            return False
            
        api_name = "batch_download"
        api_config: dict = self.apis_config.get(api_name)

        if not api_config:
            logger.error(f"{api_name}不存在！")
            return False

        api_url = self._make_api_url(api_config, api_name)
        if api_url == None:
            logger.error(f"{api_name}缺少 url 参数！")
            return False

        api_params = self._make_api_params(api_config=api_config, api_name=api_name)
        if not api_params:
            logger.error(f"{api_name}缺少 params 参数！")

        try:
            async with self.login_session.stream("GET", api_url, timeout=20, follow_redirects=True) as response:
                response.raise_for_status()

                # 获取文件名
                filename = None
                content_disposition = response.headers.get('Content-Disposition')
                if content_disposition:
                    fn_match = re.search(r"filename\*\s*=\s*utf-?8''([^;]+)", content_disposition)
                    if fn_match:
                        filename = fn_match.group(1).strip('"')
                        filename = unquote(filename)

                if not filename and 'name=' in response.url:
                    filename = unquote(response.url.split("name=")[-1])

                if not filename and 'name=' not in response.url:
                    filename = unquote(response.url.split('/')[-1])

                if not filename:
                    filename = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                if self.basename:
                    filename = f"{self.basename}_{filename}"

                logger.info(f"获取到文件名: {filename}")

                file_path = self.output_path / filename

                # 获取文件大小
                total_size = int(response.headers.get('content-length', 0))
                download_size = 0
                
                logger.info(f"开始下载文件: {filename}")
                
                # 分块读取
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.iter_bytes(chunk_size=8192):
                        if chunk:
                            await f.write(chunk)
                            download_size += len(chunk)

                            # 如果上层传入进度回调，则通知状态
                            if progress_callback:
                                try:
                                    progress_callback(download_size, total_size, filename)
                                except Exception as e:
                                    logger.warning(f"进度回调函数出错: {e}")

                logger.info(f"{filename} 下载完成")
                return True

        except HTTPError as e:
            logger.error(f"请求过程中发生 HTTP 错误！错误原因: {e}")
            return False
        except Exception as e:
            logger.error(f"请求过程中发生未知错误！错误原因: {e}")
            return False

class resourcesRemoveAPIFits(resourcesAPIFits):
    def __init__(self, 
                 login_session,
                 apis_name = None,
                 resource_id: int|None = None, 
                 resources_id: List[int]|None = None
                 ):
        if apis_name is None:
            apis_name = ["remove", "batch_remove"]
        super().__init__(login_session)
        self.resource_id = resource_id
        self.resources_id = resources_id

    def _make_api_params(self, api_config, api_name):
        api_params = api_config.get("params")

        if api_params == None:
            logger.error(f"{api_name}缺乏params参数配置！")
        
        if api_name == "batch_remove":
            api_params["upload_ids"] = self.resources_id
            return api_params

        return super()._make_api_params(api_config, "")


    def _make_api_url(self, api_config, api_name):
        base_api_url = api_config.get("url")
        if base_api_url == None:
            logger.error(f"{api_name}参数url缺失！")
            return None 
        if api_name == "remove":
            return base_api_url.replace("<placeholder>", str(self.resource_id))
        return super()._make_api_url(api_config, api_name)

    async def delete(self)->bool:
        if self.apis_config == None:
            self._load_api_config()

        api_name = "remove"
        api_config: dict = self.apis_config.get(api_name, None)

        if not self.check_api_method(api_config, "DELETE"):
            logger.error("该方法只适用DELET请求！")
            raise RuntimeError

        if api_config == None:
            logger.error(f"{api_name}不存在！")
            return False
        
        api_url = self._make_api_url(api_config, api_name)
        if api_url == None:
            logger.error(f"{api_name}的{api_url}不存在！")
            return False
        
        try:
            api_respone = await self.login_session.delete(url=api_url, follow_redirects=True)
            api_respone.raise_for_status()
            logger.info("删除成功")
            return True
        except HTTPError as e:
            if api_respone.status_code == 404:
                logger.error("删除失败")
                return False
            
            logger.error(f"未知请求错误！错误原因: {e}")
            return False
        except Exception as e:
            logger.error(f"未知错误！错误原因: {e}")
            return False
        
    async def batch_delete(self):
        if self.apis_config == None:
            self._load_api_config()

        api_name = "batch_remove"
        api_config: dict = self.apis_config.get(api_name, None)

        if not self.check_api_method(api_config, "DELETE"):
            logger.error("该方法只适用DELET请求！")
            raise RuntimeError
        
        if api_config == None:
            logger.error(f"{api_name}不存在！")
            return False
        
        api_url = self._make_api_url(api_config, api_name)
        if api_url == None:
            logger.error(f"{api_name}的{api_url}不存在！")
            return False

        api_params = self._make_api_params(api_config, api_name)
        
        try:
            api_respone = await self.login_session.delete(url=api_url, json=api_params, follow_redirects=True)
            api_respone.raise_for_status()
            logger.info("删除成功")
            return True
        except HTTPError as e:
            if api_respone.status_code == 404:
                logger.error("删除失败")
                return False
            
            logger.error(f"未知请求错误！错误原因: {e}")
            return False
        except Exception as e:
            logger.error(f"未知错误！错误原因: {e}")
            return False

class resourceUploadAPIFits(resourcesAPIFits):
    def __init__(self, 
                 login_session, 
                 apis_name=None):
        if apis_name is None:
            apis_name = ["upload"]
        super().__init__(login_session, apis_name)
        self.upload_headers = {
            'Accept': 'application/json, text/plain, */*',
            'Origin': 'https://courses.zju.edu.cn',
            'Referer': 'https://courses.zju.edu.cn/user/resources/files',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36'
        }

    async def upload(self, 
               file_path: Path,
               progress_callback: Optional[Callable[[int, int, str], None]] = None
               )->bool:
        self.file_path = self._check_file_paths(file_path)

        # --- 准备阶段 ---
        if not self.file_path:
            logger.error(f"加载 {file_path} 的时候发生错误！")
            return False
        
        if not self.apis_name or not self.apis_config:
            self._load_api_config()

        api_name   = "upload"
        api_config = self.apis_config.get(api_name)
        api_url    = self._make_api_url(api_config, api_name)

        if not api_config:
            logger.error(f"{api_name}不存在！")
            return False

        self.file_name = self.file_path.name
        self.file_size = self.file_path.stat().st_size
        upload_data    = self._make_api_data(api_config, api_name)

        logger.info(f"请求上传文件 {self.file_name} 中...")
        progress_callback(0, self.file_size, self.file_name)

        # --- 申请阶段 ---
        # POST文件上传请求，以获得文件上传的实际位置
        try:
            upload_response = await self.login_session.post(
                url     = api_url,
                json    = upload_data,
                headers = self.upload_headers,
                follow_redirects=True
            )
            
        except Exception as e:
            logger.error(f"向服务器申请上传文件 {self.file_name} 时候发生错误！{e}")
            return False
        
        logger.info(f"文件 {self.file_name} 请求上传文件成功！")
        logger.info(f"文件 {self.file_name} 开始上传...")

        # --- 上传阶段 ---
        upload_url    = upload_response.json().get("upload_url")
        file_mimetype = mimetypes.guess_type(self.file_path)[0] or 'application/octet-stream'

        try:
            with open(self.file_path, 'rb') as f:
                # # 适配上层需求文件名
                # def sub_progress_callback(uploaded: int, total: int):
                #     progress_callback(uploaded, total, self.file_name)
               
                # 包装文件
                # uploader = fileUploadProgressWrapper(f, sub_progress_callback)
                file_bytes = f.read()

                # 构建payload
                file_payload = {
                    "file": (self.file_name, file_bytes, file_mimetype)
                }

                response = await self.login_session.put(
                    url = upload_url,
                    files = file_payload,
                    follow_redirects=True
                )
            logger.info(f"{response.cookies}")
            response.raise_for_status()
        except Exception as e:
            logger.error(f"向服务器上传文件 {self.file_name} 时候发生错误！{e}")
            return False
        
        progress_callback(self.file_size, self.file_size, self.file_name)
        logger.info(f"文件 {self.file_name} 上传成功！")
        return True

    def _make_api_data(self, api_config, api_name):
        api_data = api_config.get("params", {})

        if api_name == "upload":
            api_data["name"] = self.file_name
            api_data["size"] = self.file_size
            return api_data
        
        return super()._make_api_params(api_config, api_name)


    def _check_file_paths(self, file_path: Path)->Path|None:
        """检查文件路径的有效性与待上传文件的合法性
        """

        # 定义合法文件类型
        video_formats    = ["avi", "flv", "m4v", "mkv", "mov", "mp4", "3gp", "3gpp", "mpg", "rm", "rmvb", "swf", "webm", "wmv"]
        audio_formats    = ["mp3", "m4a", "wav", "wma"]
        image_formats    = ["jpeg", "jpg", "png", "gif", "bmp", "heic", "webp"]
        document_formats = ["txt", "pdf", "csv", "xls", "xlsx", "doc", "ppt", "pptx", "docx", "odp", "ods", "odt", "rtf"]
        archive_formats  = ["zip", "rar", "tar"]

        main_formats     = video_formats + audio_formats + image_formats + document_formats + archive_formats
        other_formats    = ["mat", "dwg", "m", "mlapp", "slx", "mlx"]

        # 定义合法文件大小，主要文件类型为3GB，其他为2GB
        legal_file_max_size = (3*1024**3, 2*1024**3)
  
        # 检查路径合法性
        if not isinstance(file_path, Path):
            logger.error(f"{file_path} 不是一个 Path 类型对象！")
            return None

        if not Path(file_path).exists():
            logger.error(f"{file_path} 不存在！")
            return None
        
        if not Path(file_path).is_file():
            logger.error(f"{file_path} 不是一个文件！")
            return None
        
        # 检查文件合法性
        file_size = file_path.stat().st_size
        file_type = file_path.suffix.replace('.', '')

        if file_type in main_formats:
            if file_size > legal_file_max_size[0]:
                logger.error(f"{file_path.name} 大小超出上限3GB！")
                return None
        elif file_type in other_formats:
            if file_size > legal_file_max_size[1]:
                logger.error(f"{file_path.name} 大小超出上限2GB！")
                return None
        else:
            logger.error(f"{file_path.name} 的文件类型 {file_type} 暂不支持上传！")
            return None
            
        return file_path

# --- rollcall API ---
class rollcallAPIFits(APIFitsAsync):
    def __init__(self, 
                 login_session, 
                 apis_name = None,
                 apis_config = None, 
                 parent_dir=None, 
                 data=None
                 ):
        if apis_name is None:
            apis_name = ["rollcall", "answer"]
        super().__init__(login_session, "rollcall", apis_name, apis_config, parent_dir, data)

class rollcallListAPIFits(rollcallAPIFits):
    def __init__(self, 
                 login_session, 
                 apis_name = None,
                 ):
        if apis_name is None:
            apis_name = ["rollcall"]
        super().__init__(login_session, apis_name)

class rollcallAnswerRadarAPIFits(rollcallAPIFits):
    def __init__(self, 
                 login_session, 
                 rollcall_id: int,
                 rollcall_data,
                 apis_name = None):
        if apis_name is None:
            apis_name = ["answer_radar"]
        super().__init__(login_session, apis_name, data=rollcall_data)
        self.rollcall_id = rollcall_id

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")
        if not base_api_url:
            logger.error(f"{api_name}参数url缺失！")
            return None
        
        if api_name == "answer_radar":
            return base_api_url.replace("<placeholder>", str(self.rollcall_id))
        
        return super()._make_api_url(api_config, api_name)

class rollcallAnswerNumberAPIFits(rollcallAPIFits):
    def __init__(self, 
                 login_session, 
                 rollcall_id,
                 rollcall_data,
                 apis_name=None
                 ):
        if apis_name is None:
            apis_name = ["answer_number"]
        super().__init__(login_session, apis_name, data=rollcall_data)
        self.rollcall_id = rollcall_id

    def _make_api_url(self, api_config, api_name):
        base_api_url: str = api_config.get("url")
        if not base_api_url:
            logger.error(f"{api_name}参数url缺失！")
            return None
        
        if api_name == "answer_number":
            return base_api_url.replace("<placeholder>", str(self.rollcall_id))
        return None