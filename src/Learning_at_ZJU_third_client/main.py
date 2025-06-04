import requests
import json
from load_config import load_config, parse_config
from login import login
from zjuAPI import zju_api
from printlog import print_log


login = login.LoginFit()
login_session = login.login()

userAPI = zju_api.userIndexAPIFits(login_session=login_session)
userAPI.get_api_data()
coursesAPI = zju_api.coursesAPIFits(login_session=login_session)
coursesAPI.get_api_data()

my_courses_config = load_config.apiConfig("my_courses").load_config()
my_courses_query = {
    "academic_year": ["academic_year", "name"],
    "teaching_class_name": ["course_attributes", "teaching_class_name"],
    "course_code": ["course_code"],
    "department": ["department", "name"],
    "course_id": "id",
    "instructors": ["instructors", "name"],
    "start_date": ["start_date"]
}
my_courses = parse_config.myCoursesConfigParser(my_courses_config, my_courses_query).get_config_data()
load_config.coursesMessageConfig("my_courses").update_config(config_data=my_courses)
# hello tetst