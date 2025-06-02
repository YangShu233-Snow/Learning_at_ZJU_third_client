from login import login
import requests

username = " "
password = " "
base_url = "https://courses.zju.edu.cn/user/index#/"
login = login.LoginFit(username=username, password=password, base_url=base_url)
login_session = login.login()