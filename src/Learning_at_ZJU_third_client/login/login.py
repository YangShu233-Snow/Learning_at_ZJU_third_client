import requests
from lxml import etree
import time
from encrypt import LoginRSA
from requests.exceptions import HTTPError, ConnectionError, Timeout, RequestException

class LoginFit:
    def __init__(self, username:str, password:str, base_url:str, headers=None):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.headers = headers
        self.login_session = creat_login_session(headers=headers)

    def login(self)->requests.Session:
        response = self.login_session.get(url=self.base_url)
        
        if self.check_login_status(response=response):
            print(f"[Info {time.strftime('%H:%M:%S', time.localtime())}]登录成功！学号: {self.username}")
            return self.login_session
        else:
            print(f"[Info {time.strftime('%H:%M:%S', time.localtime())}]未登录，尝试登录中......")
            print(response.url)
        
        # 准备登录POST表单内容
        # 请求加密password所需的exponent和modulus
        try: 
            pubkey_json = self.login_session.get(url="https://zjuam.zju.edu.cn/cas/v2/getPubKey")
            pubkey_json.raise_for_status()
            data  = pubkey_json.json()
            
            # 解析，获取exponent和modulus
            exponent = data["exponent"]
            modulus = data["modulus"]

        except requests.exceptions.HTTPError as errh:
            print(f"HTTP错误: {errh}")

        except requests.exceptions.ConnectionError as errc:
            print(f"连接错误: {errc}")

        except requests.exceptions.Timeout as errt:
            print(f"超时错误: {errt}")

        except requests.exceptions.RequestException as err:
            print(f"发生了其他请求错误: {err}")

        except ValueError as e: # 当响应不是有效JSON时，.json()会抛出json.JSONDecodeError，它是ValueError的子类
            print(f"无法解析JSON数据: {e}")
            print(f"响应内容: {pubkey_json.text}") # 打印原始响应内容进行调试

        # 加密passwrod
        try:
            encrypted_password = self.encrypt_password(exponent=exponent, modulus=modulus)
        
        except ValueError as e:
            print(f"[Error {time.strftime('%H:%M:%S', time.localtime())}]密码值错误！发生在RSA加密时。")

        # 获取execution
        execution = self.get_execution(response=response)

        # 构建POST表单
        print(f"[Info {time.strftime('%H:%M:%S', time.localtime())}]构建POST表单中...")
        data = {
            'username': self.username,
            'password': encrypted_password,
            'authcode': '',
            'execution': execution[0],
            '_eventId': 'submit'
        }
        
        print(f"[Info {time.strftime('%H:%M:%S', time.localtime())}]构建成功！使用POST表单:")
        for key, value in data.items():
            if len(value) >= 200:
                value = value[:200] + "..."
            print(f"{key}: {value}")

        # POST登录
        print(f"[Info {time.strftime('%H:%M:%S', time.localtime())}]POST登录请求中...")
        login_response = self.login_session.post(url=response.url, headers=self.headers, data=data)
        
        if "学在浙大" in login_response.text:
            print(f"[Info {time.strftime('%H:%M:%S', time.localtime())}]登录成功！学号: {self.username}")
        else:
            print(f"[Error {time.strftime('%H:%M:%S', time.localtime())}]登录失败！")

        return self.login_session

    def check_login_status(self, response: requests.Response)->bool:
        """check the login status now and determine whether to make a login or already logined

        Parameters
        ----------
        response : requests.Response
            the response of the requests from url

        Returns
        -------
        bool
            True stands for successfully and False means it need to login.
        """        

        if response.url == self.base_url:
            return True
        else:
            return False

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
        print(f"[Info {time.strftime('%H:%M:%S', time.localtime())}]未检测到登录需求headers，启用默认headers")
        headers = default_headers
        print(f"[Info {time.strftime('%H:%M:%S', time.localtime())}]已启用默认headers")
        for key, value in headers.items():
            print(f"{key}: {value}")

    login_session.headers.update(headers)
    
    return login_session