import os
import requests
import json
import mimetypes
import datetime
from pathlib import Path
from load_config import load_config, parse_config
from login import login
from zjuAPI import zju_api
from printlog import print_log
from upload import file_upload, submit
from search import courses_search

CURRENT_PROGRAM_PATH = Path(__file__).resolve().parent.parent.parent
files_name = ["黄浩旸-基础医学研究方向职业生涯规划书.doc"]

# 执行登录
login = login.LoginFit()
login_session = login.login()

# # 搜索课程名称
# courses_search.CoursesSearcher("先秦诸子").search_courses(login_session=login_session)
if False:
    files = []
    for file_name in files_name:
        files.append(Path(CURRENT_PROGRAM_PATH / file_name))

    to_upload_fils = file_upload.uploadFile(*files)
    files_id = to_upload_fils.upload(login_session)
    files_id_value = list(files_id.values())


    for key, value in files_id.items():
        print(f"{key}: {value}")

    to_submit_assignment = submit.submitAssignment(
        activity_id=1009609,
        comment="我已阅读须知，会准时携带证件参加考试，并严格遵守考试纪律",
        files_id=files_id_value,
        )

    to_submit_assignment.submit(login_session=login_session)



# # 请求userAPI组，本请求一共获得notification(LAZ主页中间部分)，todo_list(LAZ主页右下部分)和recent_visit_courses(LAZ主页右上部分)
# userAPI = zju_api.userIndexAPIFits(login_session=login_session)
# userAPI.get_api_data()

# # 请求coursesAPI组，本请求获得my_courses(我的课程页面信息，有分页)
# coursesAPI = zju_api.coursesAPIFits(login_session=login_session)
# coursesAPI.get_api_data()

# # 请求resourcesList组，本请求获得云盘文件信息（我的资源，有分页）
# resourcesListAPI = zju_api.resourcesListAPIFits(login_session=login_session)
# resourcesListAPI.get_api_data()

# # 通过课程id查询指定课程页面的信息
# key = "79813"
# course_search_result = load_config.coursesMessageConfig("my_courses").load_config().get(key)
# print(course_search_result)
# coursePageAPI = zju_api.coursePageAPIFits(login_session=login_session, course_id=key)
# coursePageAPI.get_api_data()