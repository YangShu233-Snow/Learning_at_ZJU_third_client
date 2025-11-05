import requests
import keyring
import pickle
import httpx
import asyncio
import logging
import traceback
from httpx import HTTPStatusError, ConnectTimeout, RequestError
from cryptography.fernet import Fernet, InvalidToken
from lxml import etree
from pathlib import Path
from requests.exceptions import HTTPError, ConnectionError

from ..load_config import load_config
from ..encrypt import LoginRSA

CURRENT_SCRIPT_PATH = Path(__file__)
USER_AVATAR_PATH = CURRENT_SCRIPT_PATH.parent.parent.parent.parent / "images/user_avatar.png"

KEYRING_SERVICE_NAME = "lazy"
KEYRING_STUDENTID_NAME = "studentid"
KEYRING_PASSWORD_NAME = "password"
ENCRYPTION_KEY_NAME = "session_encryption_key"
SESSION_FILE = Path.home() / ".lazy_cli_session.enc"

logger = logging.getLogger(__name__)

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

# 凭据管理器
class CredentialManager():
    """加密、解密、加载与保存会话/Cookies文件
    """
    def __init__(self):
        # 初始化加密器
        logger.info("初始化加密器中...")
        self._encryption_key = self._generate_encryption_key()
        self._fernet = Fernet(self._encryption_key)
        logger.info("初始化加密器成功")

    def _generate_encryption_key(self)->bytes:
        """提取已有的会话加密密钥，如果不存在则创建并保存
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
        
    def save_cookies(self, cookies: dict)->bool:
        """以序列化和加密的方式保存会话Cookies至本地家目录
        """        
        logger.info("会话保存中...")
        try:
            # 序列化
            pickled_cookies = pickle.dumps(cookies)
            # 加密
            encrypted_pickled_cookies = self._fernet.encrypt(pickled_cookies)
            with open(SESSION_FILE, 'wb') as f:
                f.write(encrypted_pickled_cookies)
            logger.info("会话保存成功！")
            return True
        except Exception as e:
            logger.error(f"会话保存未成功！错误信息: {e}")
            return False
        
    def load_cookies(self)->dict|None:
        logger.info("Cookies加载中...")
        if not SESSION_FILE.exists():
            logger.error("Cookies文件不存在！")
            return None

        # 读取文件，解密并反序列化        
        try:
            with open(SESSION_FILE, 'rb') as f:
                encrypted_pickled_cookies =f.read()
            
            decrypted_pickled_cookies = self._fernet.decrypt(encrypted_pickled_cookies)
            cookies = pickle.loads(decrypted_pickled_cookies)
            logger.info("Cookies加载成功！")
            return cookies
        except (InvalidToken, pickle.UnpicklingError, EOFError, FileNotFoundError) as e:
            logger.error(f"Cookies加载失败！错误原因: {e}")
            logger.info(f"Cookies加载未成功，请检查会话文件是否损坏或密钥已更改")
            return None

# 异步架构Client类
class ZjuAsyncClient:
    def __init__(
        self, 
        headers   = None, 
        cookies   = None,
        trust_env = True
    ):
        """初始化会话

        Parameters
        ----------
        headers : dict, optional
            _description_, by default None
        """
        # 初始化会话    
        logger.info("初始化会话中...")
        
        if trust_env:
            logger.info(f"启用全局代理")
        else:
            logger.info(f"全局代理关闭")

        self.session = httpx.AsyncClient(trust_env=trust_env)

        if headers is None:
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
            }

        self.session.headers.update(headers)

        if cookies:
            self.session.cookies.update(cookies)
            
        self.studentid = None
        logger.info("初始化会话成功")

        # # 初始化加密器
        # logger.info("初始化加密器中...")
        # self._encryption_key = generate_encryption_key()
        # self._fernet = Fernet(self._encryption_key)
        # logger.info("初始化加密器成功")
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        await self.session.aclose()

    async def login(self, studentid: str, password: str)->bool:
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
        # 初始化会话
        logger.info("初始化会话...")
        self.session.cookies.clear()

        # 初始化常量
        url = "https://courses.zju.edu.cn/user/index#/"
        pubkey_url = "https://zjuam.zju.edu.cn/cas/v2/getPubKey"
        self.studentid = studentid
        self.password = password
        # 初始化登录POST表单
        # 获取password RSA加密所需的exponent与modulus
        try: 
            login_response = await self.session.get(url=url, follow_redirects=True)
            pubkey_json = await self.session.get(url=pubkey_url, follow_redirects=True)
            pubkey_json.raise_for_status()
            
            # 解析，获取exponent和modulus
            data = pubkey_json.json()
            exponent = data.get("exponent")
            modulus = data.get("modulus")

            if exponent is None or modulus is None:
                logger.error("PubKey API调用存在问题，请将此问题报告给开发者！")

        except HTTPError as errh:
            logger.error(f"HTTP错误: {errh}")
            return False
        except ConnectTimeout as errt:
            logger.error(f"超时错误: {errt}")
            return False
        except ValueError as e: # 当响应不是有效JSON时，.json()会抛出json.JSONDecodeError，它是ValueError的子类
            logger.error(f"无法解析JSON数据: {e}")
            return False
        except Exception as e:
            # 【关键修正】: 打印异常的类型、原始表示(repr)和完整的堆栈信息
            logger.error(f"捕获到未知异常，类型: {type(e)}")
            logger.error(f"异常的 repr: {repr(e)}")
            logger.error(f"完整的 Traceback:\n{traceback.format_exc()}")
            return False
        
        # 加密password
        try:
            encrypted_password = self._encrypt_password(password=self.password, exponent=exponent, modulus=modulus)
        
        except ValueError as e:
            logger.error(f"密码值错误！发生在RSA加密时。")

        # 获取execution
        execution = self._get_execution(response=login_response)

        # 构建POST表单
        logger.info(f"构建POST表单中...")
        data = {
            'username': self.studentid,
            'password': encrypted_password,
            'authcode': '',
            'execution': execution[0],
            '_eventId': 'submit'
        }

        logger.info(f"POST登录请求中...")
        
        try:
            response = await self.session.post(
                url=login_response.url, 
                data=data,
                follow_redirects=True
                )
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(f"请求出错: {e}")
            return False
        except Exception as e:
            logger.error(f"未知错误: {e}")
            return False

        if "学在浙大" in response.text:
            logger.info(f"登录成功！")
            return True
        else:
            logger.error(f"登录失败，可能是学号或密码不正确！")
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

    def _get_execution(self, response: httpx.Response)->str:
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

    # def save_session(self):
    #     """以序列化和加密的方式保存会话Cookies至本地家目录
    #     """        
    #     logger.info("会话保存中...")
    #     try:
    #         # 序列化
    #         pickled_session = pickle.dumps(dict(self.session.cookies))
    #         # 加密
    #         encrypted_pickled_session = self._fernet.encrypt(pickled_session)
    #         with open(SESSION_FILE, 'wb') as f:
    #             f.write(encrypted_pickled_session)
    #         logger.info("会话保存成功！")
    #     except Exception as e:
    #         logger.error(f"会话保存未成功！错误信息: {e}")

    # def load_session(self)->bool:
    #     logger.info("会话加载中...")
    #     if not SESSION_FILE.exists():
    #         logger.error("会话文件不存在！")
    #         return False

    #     # 读取文件，解密并反序列化        
    #     try:
    #         with open(SESSION_FILE, 'rb') as f:
    #             encrypted_pickled_session =f.read()
            
    #         decrypted_pickled_session = self._fernet.decrypt(encrypted_pickled_session)
    #         cookies = pickle.loads(decrypted_pickled_session)
    #         self.session.cookies.update(cookies)
    #         logger.info("会话加载成功！")
    #         return True
    #     except (InvalidToken, pickle.UnpicklingError, EOFError, FileNotFoundError) as e:
    #         logger.error(f"会话加载失败！错误原因: {e}")
    #         logger.info(f"会话加载未成功，请检查会话文件是否损坏或密钥已更改")
    #         return False
        
    # def load_cookies(self)->dict|None:
    #     logger.info("Cookies加载中...")
    #     if not SESSION_FILE.exists():
    #         logger.error("Cookies文件不存在！")
    #         return None

    #     # 读取文件，解密并反序列化        
    #     try:
    #         with open(SESSION_FILE, 'rb') as f:
    #             encrypted_pickled_session =f.read()
            
    #         decrypted_pickled_session = self._fernet.decrypt(encrypted_pickled_session)
    #         cookies = pickle.loads(decrypted_pickled_session)
    #         logger.info("Cookies加载成功！")
    #         return cookies
    #     except (InvalidToken, pickle.UnpicklingError, EOFError, FileNotFoundError) as e:
    #         logger.error(f"Cookies加载失败！错误原因: {e}")
    #         logger.info(f"Cookies加载未成功，请检查会话文件是否损坏或密钥已更改")
    #         return None

    async def is_valid_session(self)->bool:
        if not self.session.cookies:
            logger.info("Session.Cookies不存在，需手动登录")
            return False
        
        # 验证登录状态
        try:
            response = await self.session.get(url="https://courses.zju.edu.cn/api/activities/is-locked", follow_redirects=True)
            response.raise_for_status()
            if response.url == "https://courses.zju.edu.cn/api/activities/is-locked":
                logger.info("会话验证有效")
                return True
            
            return False
        except HTTPStatusError:
            logger.warning("会话已过期失效！")
            return False
        except ConnectTimeout as e:
            logger.error(f"网络问题: {e}")
            return False
        except Exception as e:
            logger.error(f"未知错误: {e}")
            return False

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
        logger.info("初始化会话中...")
        self.session = requests.Session()
        if headers is None:
            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
            }

        self.session.headers.update(headers)
        self.studentid = None
        logger.info("初始化会话成功")

        # 初始化加密器
        logger.info("初始化加密器中...")
        self._encryption_key = generate_encryption_key()
        self._fernet = Fernet(self._encryption_key)
        logger.info("初始化加密器成功")
    
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

        # 初始化登录POST表单
        # 获取password RSA加密所需的exponent与modulus
        try: 
            login_response = self.session.get(url=url)
            pubkey_json = self.session.get(url=pubkey_url)
            pubkey_json.raise_for_status()
            
            # 解析，获取exponent和modulus
            data = pubkey_json.json()
            exponent = data.get("exponent")
            modulus = data.get("modulus")

            if exponent is None or modulus is None:
                logger.error("PubKey API调用存在问题，请将此问题报告给开发者！")

        except HTTPError as errh:
            logger.error(f"HTTP错误: {errh}")

        except ConnectionError as errc:
            logger.error(f"连接错误: {errc}")

        except ConnectTimeout as errt:
            logger.error(f"超时错误: {errt}")

        except RequestError as err:
            logger.error(f"发生了其他请求错误: {err}")

        except ValueError as e: # 当响应不是有效JSON时，.json()会抛出json.JSONDecodeError，它是ValueError的子类
            logger.error(f"无法解析JSON数据: {e}")

        # 加密password
        try:
            encrypted_password = self._encrypt_password(password=password, exponent=exponent, modulus=modulus)
        
        except ValueError as e:
            logger.error(f"密码值错误！发生在RSA加密时。")

        # 获取execution
        execution = self._get_execution(response=login_response)

        # 构建POST表单
        logger.info(f"构建POST表单中...")
        data = {
            'username': self.studentid,
            'password': encrypted_password,
            'authcode': '',
            'execution': execution[0],
            '_eventId': 'submit'
        }

        logger.info(f"POST登录请求中...")
        response = self.session.post(
            url=login_response.url, 
            data=data)
        
        if "学在浙大" in response.text:
            logger.info(f"登录成功！学号: {self.studentid}")
            return True
        else:
            logger.error(f"登录失败，请检查学号与密码是否正确！")
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
        logger.info("会话保存中...")
        try:
            # 序列化
            pickled_session = pickle.dumps(self.session)
            # 加密
            encrypted_pickled_session = self._fernet.encrypt(pickled_session)
            with open(SESSION_FILE, 'wb') as f:
                f.write(encrypted_pickled_session)
            logger.info("会话保存成功！")
        except Exception as e:
            logger.error(f"会话保存未成功！错误信息: {e}")

    def load_session(self)->bool:
        logger.info("会话加载中...")
        if not SESSION_FILE.exists():
            logger.error("会话文件不存在！")
            return False

        # 读取文件，解密并反序列化        
        try:
            with open(SESSION_FILE, 'rb') as f:
                encrypted_pickled_session =f.read()
            
            decrypted_pickled_session = self._fernet.decrypt(encrypted_pickled_session)
            self.session = pickle.loads(decrypted_pickled_session)
            return True
        except (InvalidToken, pickle.UnpicklingError, EOFError, FileNotFoundError) as e:
            logger.error(f"会话加载失败！错误原因: {e}")
            logger.info(f"会话加载未成功，请检查会话文件是否损坏或密钥已更改")
            return False

    def is_valid_session(self)->bool:
        if not self.session.cookies:
            logger.warning("Session.Cookies不存在，需手动登录")
            return False
        
        # 验证登录状态
        try:
            response = self.session.get(url="https://courses.zju.edu.cn/api/activities/is-locked", follow_redirects=False)
            response.raise_for_status()
            if response.status_code == 200:
                logger.info("会话验证有效")
                return True
            
            return False
        except RequestError:
            logger.warning("会话已过期失效！")
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
                logger.error("学号不能为空！")
            else:
                keyring.set_password("lazy", "studentid", self.studentid)

        while self.password == None:
            self.password = input("请输入密码：")
            if self.password == None:
                logger.error("密码不能为空！")
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

        except ConnectTimeout as errt:
            print(f"超时错误: {errt}")

        except RequestError as err:
            print(f"发生了其他请求错误: {err}")

        except ValueError as e: # 当响应不是有效JSON时，.json()会抛出json.JSONDecodeError，它是ValueError的子类
            print(f"无法解析JSON数据: {e}")
            print(f"响应内容: {pubkey_json.text}") # 打印原始响应内容进行调试

        # 加密passwrod
        try:
            encrypted_password = self.encrypt_password(exponent=exponent, modulus=modulus)
        
        except ValueError as e:
            logger.error(f"密码值错误！发生在RSA加密时。")

        # 获取execution
        execution = self.get_execution(response=login_response)

        # 构建POST表单
        logger.info(f"构建POST表单中...")
        data = {
            'username': self.studentid,
            'password': encrypted_password,
            'authcode': '',
            'execution': execution[0],
            '_eventId': 'submit'
        }
        
        logger.info(f"构建成功！")
        
        # POST登录
        logger.info(f"POST登录请求中...")
        login_response = self.login_session.post(url=login_response.url, headers=self.headers, data=data)
        
        if "学在浙大" in login_response.text:
            logger.info(f"登录成功！学号: {self.studentid}")
            self.update_user_config(login_response)
            logger.info("User Config配置更新成功")
            self.get_user_avatar(login_response)
            logger.info("用户头像更新成功")
        else:
            logger.error(f"登录失败！")

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
        logger.info(f"未检测到登录需求headers，启用默认headers")
        headers = default_headers
        logger.info(f"已启用默认headers")

    login_session.headers.update(headers)
    
    return login_session
