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

CURRENT_PROGRAM_PATH = Path(__file__).resolve().parent.parent.parent
files_name = ["zuoye.txt", "zuoye copy.txt", "zuoye copy 2.txt"]

# 执行登录
login = login.LoginFit()
login_session = login.login()

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

# submission = {
#     "comment": "<p><span style=\"font-size: 14px;\">我已阅读须知，会准时携带证件参加考试，并严格遵守考试纪律</span><br></p>",
#     "uploads": [17012080],
#     "slides": "",
#     "is_draft": False,
#     "mode": "normal",
#     "other_resources": [],
#     "uploads_in_rich_text": []
# }
# response = login_session.post(url = "https://courses.zju.edu.cn/api/course/activities/1009609/submissions", json = submission)
# print(response.status_code)
# print(response.json)

if False:
    userAPI = zju_api.userIndexAPIFits(login_session=login_session)
    userAPI.get_api_data()
    coursesAPI = zju_api.coursesAPIFits(login_session=login_session)
    coursesAPI.get_api_data()
    resourcesListAPI = zju_api.resourcesListAPIFits(login_session=login_session)
    resourcesListAPI.get_api_data()

    my_courses_config = load_config.apiConfig("courses", "my_courses").load_config()
    my_courses_query = {
        "name": ["name"],
        "academic_year": ["academic_year", "name"],
        "teaching_class_name": ["course_attributes", "teaching_class_name"],
        "course_code": ["course_code"],
        "department": ["department", "name"],
        "instructors": ["instructors", "name"],
        "start_date": ["start_date"]
    }
    my_courses = parse_config.myCoursesConfigParser(my_courses_config, my_courses_query).get_config_data()
    load_config.coursesMessageConfig("my_courses").update_config(config_data=my_courses)

    key = "79813"
    course_search_result = load_config.coursesMessageConfig("my_courses").load_config().get(key)
    print(course_search_result)
    coursePageAPI = zju_api.coursePageAPIFits(login_session=login_session, course_id=key)
    coursePageAPI.get_api_data()