import requests
import time
from lxml import etree
from pathlib import Path
from encrypt import LoginRSA
from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException
from load_config import load_config
from printlog.print_log import print_log

CURRENT_SCRIPT_PATH = Path(__file__)
USER_AVATAR_PATH = CURRENT_SCRIPT_PATH.parent.parent.parent.parent / "images/user_avatar.png"

class LoginFit:
    def __init__(self, studentid: str = None, password: str = None, base_url: str = None, cookies: dict[str:str] = None, headers=None):
        user_config = load_config.userConfig().load_config()
        self.password = None
        
        if base_url == None:
            self.base_url = "https://courses.zju.edu.cn/user/index#/"
        else:
            self.base_url = base_url

        if studentid == None:
            self.studentid = user_config.get("studentid", None)
            while self.studentid == None:
                self.studentid = input("请输入学号：")
                if self.studentid == None:
                    print_log("Error", "学号不能为空！", "login.LoginFit.__init__")

        self.headers = headers
        self.login_session = creat_login_session(headers=headers)
        
        if cookies == None:
            self.cookies = user_config.get("cookies", None)
            if password == None and self.cookies == None:
                self.password = input("请输入密码: ")
            else:
                self.login_session.cookies.update(self.cookies)

    def login(self)->requests.Session:
        """学在浙大登录方法

        Returns
        -------
        requests.Session
            已登录的会话
        """        
        login_response = self.login_session.get(url=self.base_url)

        if "学在浙大" in login_response.text:
            print_log("Info", f"登录成功！学号: {self.studentid}", "login.LoginFit.login")
            self.update_user_config(login_response)
            print_log("Info", "User Config配置更新成功", "login.LoginFit.login")
            self.get_user_avatar(login_response)
            print_log("Info", "用户头像更新成功", "login.LoginFit.login")
            return self.login_session
        else:
            print_log("Info", f"未登录，尝试登录中......", "login.LoginFit.login")
            if self.password == None:
                self.password = input("请输入密码:")
        
        # 准备登录POST表单内容
        # 请求加密password所需的exponent和modulus
        try: 
            pubkey_json = self.login_session.get(url="https://zjuam.zju.edu.cn/cas/v2/getPubKey")
            pubkey_json.raise_for_status()
            data  = pubkey_json.json()
            
            # 解析，获取exponent和modulus
            exponent = data["exponent"]
            modulus = data["modulus"]

        except HTTPError as errh:
            print(f"HTTP错误: {errh}")

        except ConnectionError as errc:
            print(f"连接错误: {errc}")

        except Timeout as errt:
            print(f"超时错误: {errt}")

        except RequestException as err:
            print(f"发生了其他请求错误: {err}")

        except ValueError as e: # 当响应不是有效JSON时，.json()会抛出json.JSONDecodeError，它是ValueError的子类
            print(f"无法解析JSON数据: {e}")
            print(f"响应内容: {pubkey_json.text}") # 打印原始响应内容进行调试

        # 加密passwrod
        try:
            encrypted_password = self.encrypt_password(exponent=exponent, modulus=modulus)
        
        except ValueError as e:
            print_log("Error", f"密码值错误！发生在RSA加密时。", "login.LoginFit.login")

        # 获取execution
        execution = self.get_execution(response=login_response)

        # 构建POST表单
        print_log("Info", f"构建POST表单中...", "login.LoginFit.login")
        data = {
            'username': self.studentid,
            'password': encrypted_password,
            'authcode': '',
            'execution': execution[0],
            '_eventId': 'submit'
        }
        
        print_log("Info", f"构建成功！使用POST表单:", "login.LoginFit.login")
        for key, value in data.items():
            if len(value) >= 200:
                value = value[:200] + "..."
            print(f"{key}: {value}")

        # POST登录
        print_log("Info", f"POST登录请求中...", "login.LoginFit.login")
        login_response = self.login_session.post(url=login_response.url, headers=self.headers, data=data)
        
        if "学在浙大" in login_response.text:
            print_log("Info", f"登录成功！学号: {self.studentid}", "login.LoginFit.login")
            self.update_user_config(login_response)
            print_log("Info", "User Config配置更新成功", "login.LoginFit.login")
            self.get_user_avatar(login_response)
            print_log("Info", "用户头像更新成功", "login.LoginFit.login")
        else:
            print_log("Error", f"登录失败！", "login.LoginFit.login")

        return self.login_session
    
    def update_user_config(self, response: requests.Response):
        user_config_file = load_config.userConfig()
        user_config = user_config_file.load_config()
        user_config["url"] = response.url
        user_config["studentid"] = self.studentid
        user_config["userid"] = self.get_userid(response)
        user_config["cookies"] = self.login_session.cookies.get_dict()
        user_config["username"] = self.get_username(response)
        user_config_file.update_config(config_data=user_config)
        
    def get_user_avatar(self, response: requests.Response)->str:
        html = etree.HTML(response.text)
        xpath_pattern = r'//root-scope-variable/@value'
        result = html.xpath(xpath_pattern)
        
        if result != []:
            avatar_url = result[0].split('?')[0]
            with open(USER_AVATAR_PATH, "wb") as f:
                f.write(requests.get(avatar_url).content)

    def get_userid(self, response: requests.Response)->str:
        html = etree.HTML(response.text)
        xpath_pattern = r'//span[@id="userId"]/@value'
        result = html.xpath(xpath_pattern)
        return result[0]

    def encrypt_password(self, exponent:str, modulus:str)->str:
        """encrypt password by RSA

        Returns
        -------
        str
            return the encrypted password for POST
        """        

        key_obj = LoginRSA.RSAKeyPython(public_exponent_hex=exponent, modulus_hex=modulus)
        reversed_password = self.password[::-1]
        encrypted_password = LoginRSA.encrypted_string_python(key=key_obj, s=reversed_password)

        return encrypted_password
    
    def get_execution(self, response: requests.Response)->str:
        """get the execution for POST

        Parameters
        ----------
        response : requests.Response
            the response of the requests from the base url

        Returns
        -------
        str
            return the execution
        """        

        html = etree.HTML(response.text)
        xpath_pattern = r'//input[@name="execution"]/@value'
        
        return html.xpath(xpath_pattern)

    def get_username(self, response: requests.Response)->str:
        """从index.html获取用户的姓名

        Parameters
        ----------
        response : requests.Response
            login返回的已登录index

        Returns
        -------
        str
            用户姓名
        """        
        html = etree.HTML(response.text)
        xpath_pattern = r'//root-scope-variable[@name="currentUserName"]/@value'
        username = html.xpath(xpath_pattern)
        return username[0]

def creat_login_session(headers=None)->requests.Session:
    """create a session for login

    Parameters
    ----------
     headers : dict[str:str], optional
        headers for login, by default None

    Returns
    -------
    requests.Session
        _description_
    """    

    default_headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
    }
    login_session = requests.session()

    if headers == None:
        print_log("Info", f"未检测到登录需求headers，启用默认headers", "login.creat_login_session")
        headers = default_headers
        print_log("Info", f"已启用默认headers", "login.creat_login_session")
        for key, value in headers.items():
            print(f"{key}: {value}")

    login_session.headers.update(headers)
    
    return login_session