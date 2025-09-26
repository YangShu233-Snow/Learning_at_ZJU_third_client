import requests
import keyring
import pickle
from cryptography.fernet import Fernet, InvalidToken
from lxml import etree
from pathlib import Path
from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException

from ..load_config import load_config
from ..printlog.print_log import print_log
from ..encrypt import LoginRSA

CURRENT_SCRIPT_PATH = Path(__file__)
USER_AVATAR_PATH = CURRENT_SCRIPT_PATH.parent.parent.parent.parent / "images/user_avatar.png"

KEYRING_SERVICE_NAME = "lazy"
ENCRYPTION_KEY_NAME = "session_encryption_key"
SESSION_FILE = Path.home() / ".lazy_cli_session.enc"

def generate_encryption_key()->bytes:
    """提取已有的会话加密密钥，如果不存在则创建并保存

    Returns
    -------
    bytes
        _description_
    """    
    key_hex = keyring.get_password(service_name=KEYRING_SERVICE_NAME, username=ENCRYPTION_KEY_NAME)
    if key_hex:
        return bytes.fromhex(key_hex)
    else:
        # 生成新密钥
        new_key = Fernet.generate_key()
        # 保存密钥（十六进制）
        keyring.set_password(service_name=KEYRING_SERVICE_NAME, username=ENCRYPTION_KEY_NAME, password=new_key.hex())
        return new_key        

# 新版Client类
class ZjuClient:
    def __init__(self, headers=None):
        """初始化会话

        Parameters
        ----------
        headers : dict, optional
            _description_, by default None
        """
        # 初始化会话    
        print_log("Info", "初始化会话中...", "login.login.ZjuClient.__init__")
        self.session = requests.Session()

        if headers is None:
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
            }

        self.session.headers.update(headers)
        self.studentid = None
        print_log("Info", "初始化会话成功", "login.login.ZjuClient.__init__")

        # 初始化加密器
        print_log("Info", "初始化加密器中...", "login.login.ZjuClient.__init__")
        self._encryption_key = generate_encryption_key()
        self._fernet = Fernet(self._encryption_key)
        print_log("Info", "初始化加密器成功", "login.login.ZjuClient.__init__")

    def login(self, studentid: str, password: str)->bool:
        """学在浙大登录逻辑，返回bool值表示登录结果是否成功。

        Parameters
        ----------
        studentid : str
            学号
        password : str
            密码

        Returns
        -------
        bool
            登录状态，True为成功，False为失败
        """        
        
        # 初始化常量
        url = "https://courses.zju.edu.cn/user/index#/"
        pubkey_url = "https://zjuam.zju.edu.cn/cas/v2/getPubKey"
        self.studentid = studentid
        login_response = self.session.get(url=url)

        # 初始化登录POST表单
        # 获取password RSA加密所需的exponent与modulus
        try: 
            pubkey_json = self.session.get(url=pubkey_url)
            pubkey_json.raise_for_status()
            
            # 解析，获取exponent和modulus
            data = pubkey_json.json()
            exponent = data.get("exponent")
            modulus = data.get("modulus")

            if exponent is None or modulus is None:
                print_log("Error", "PubKey API调用存在问题，请将此问题报告给开发者！", "login.login.ZjuClient.login")

        except HTTPError as errh:
            print_log("Error", f"HTTP错误: {errh}", "login.login.ZjuClient.login")

        except ConnectionError as errc:
            print_log("Error", f"连接错误: {errc}", "login.login.ZjuClient.login")

        except Timeout as errt:
            print_log("Error", f"超时错误: {errt}", "login.login.ZjuClient.login")

        except RequestException as err:
            print_log("Error", f"发生了其他请求错误: {err}", "login.login.ZjuClient.login")

        except ValueError as e: # 当响应不是有效JSON时，.json()会抛出json.JSONDecodeError，它是ValueError的子类
            print_log("Error", f"无法解析JSON数据: {e}", "login.login.ZjuClient.login")

        # 加密password
        try:
            encrypted_password = self._encrypt_password(password=password, exponent=exponent, modulus=modulus)
        
        except ValueError as e:
            print_log("Error", f"密码值错误！发生在RSA加密时。", "login.login.ZjuClient.login")

        # 获取execution
        execution = self._get_execution(response=login_response)

        # 构建POST表单
        print_log("Info", f"构建POST表单中...", "login.login.ZjuClient.login")
        data = {
            'username': self.studentid,
            'password': encrypted_password,
            'authcode': '',
            'execution': execution[0],
            '_eventId': 'submit'
        }

        print_log("Info", f"POST登录请求中...", "login.login.ZjuClient.login")
        response = self.session.post(
            url=login_response.url, 
            data=data)
        
        if "学在浙大" in response.text:
            print_log("Info", f"登录成功！学号: {self.studentid}", "login.login.ZjuClient.login")
            return True
        else:
            print_log("Error", f"登录失败，请检查学号与密码是否正确！", "login.login.ZjuClient.login")
            return False

    def _encrypt_password(self, password: str, exponent: str, modulus: str)->str:
        """用RSA算法加密password

        Returns
        -------
        str
            return the encrypted password for POST
        """        

        key_obj = LoginRSA.RSAKeyPython(public_exponent_hex=exponent, modulus_hex=modulus)
        reversed_password = password[::-1]
        encrypted_password = LoginRSA.encrypted_string_python(key=key_obj, s=reversed_password)

        return encrypted_password

    def _get_execution(self, response: requests.Response)->str:
        """得到登录的动态口令

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
    
    def _get_username(self, response: requests.Response)->str:
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

    def save_session(self):
        """以序列化和加密的方式保存会话至本地家目录
        """        
        print_log("Info", "会话保存中...", "login.login.ZjuClient.save_session")
        try:
            # 序列化
            pickled_session = pickle.dumps(self.session)
            # 加密
            encrypted_pickled_session = self._fernet.encrypt(pickled_session)
            with open(SESSION_FILE, 'wb') as f:
                f.write(encrypted_pickled_session)
            print_log("Info", "会话保存成功！", "login.login.ZjuClient.save_session")
        except Exception as e:
            print_log("Error", f"会话保存未成功！错误信息: {e}", "login.login.ZjuClient.save_session")

    def load_session(self)->bool:
        print_log("Info", "会话加载中...", "login.login.ZjuClient.load_session")
        if not SESSION_FILE.exists():
            print_log("Error", "会话文件不存在！", "login.login.ZjuClient.load_session")
            return False

        # 读取文件，解密并反序列化        
        try:
            with open(SESSION_FILE, 'rb') as f:
                encrypted_pickled_session =f.read()
            
            decrypted_pickled_session = self._fernet.decrypt(encrypted_pickled_session)
            self.session = pickle.loads(decrypted_pickled_session)
            return True
        except (InvalidToken, pickle.UnpicklingError, EOFError, FileNotFoundError) as e:
            print_log("Error", f"会话加载失败！错误原因: {e}", "login.login.ZjuClient.load_session")
            print_log("Info", f"会话加载未成功，请检查会话文件是否损坏或密钥已更改", "login.login.ZjuClient.load_session")
            return False

    def is_valid_session(self)->bool:
        if not self.session.cookies:
            print_log("Warning", "Session.Cookies不存在，需手动登录", "login.login.ZjuClient.is_valid_session")
            return False
        
        # 验证登录状态
        try:
            response = self.session.get(url="https://courses.zju.edu.cn/api/announcement")
            response.raise_for_status()
            if "announcements" in response.json():
                print_log("Info", "会话验证有效", "login.login.ZjuClient.is_valid_session")
                return True
            
            return False
        except RequestException:
            print_log("Warning", "会话已过期失效！", "login.login.ZjuClient.is_valid_session")
            return False

# 旧版Login类
class LoginFit:
    def __init__(self, base_url: str = None, cookies: dict[str:str] = None, headers=None):
        self.studentid = keyring.get_password("lazy", "studentid")
        self.password = keyring.get_password("lazy", "password")
        
        if base_url == None:
            self.base_url = "https://courses.zju.edu.cn/user/index#/"
        else:
            self.base_url = base_url

        while self.studentid == None:
            self.studentid = input("请输入学号：")
            if self.studentid == None:
                print_log("Error", "学号不能为空！", "login.LoginFit.__init__")
            else:
                keyring.set_password("lazy", "studentid", self.studentid)

        while self.password == None:
            self.password = input("请输入密码：")
            if self.password == None:
                print_log("Error", "密码不能为空！", "login.LoginFit.__init__")
            else:
                keyring.set_password("lazy", "password", self.password)

        self.headers = headers
        self.login_session = creat_login_session(headers=headers)

    def login(self)->requests.Session:
        """学在浙大登录方法

        Returns
        -------
        requests.Session
            已登录的会话
        """        
        login_response = self.login_session.get(url=self.base_url)
        
        # 准备登录POST表单内容
        # 请求加密password所需的exponent和modulus
        try: 
            pubkey_json = self.login_session.get(url="https://zjuam.zju.edu.cn/cas/v2/getPubKey")
            pubkey_json.raise_for_status()
            data = pubkey_json.json()
            
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
        
        print_log("Info", f"构建成功！", "login.LoginFit.login")
        
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
        """更新用户信息文件，记录登录地址，用户学在浙大id和用户姓名。

        Parameters
        ----------
        response : requests.Response
            _description_
        """        
        user_config_file = load_config.userConfig()
        user_config = user_config_file.load_config()
        user_config["url"] = response.url
        user_config["userid"] = self.get_userid(response)
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

    login_session.headers.update(headers)
    
    return login_session