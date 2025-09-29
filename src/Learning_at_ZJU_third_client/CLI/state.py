from ..login.login import ZjuClient, ZjuAsyncClient

# 维护全局登录状态
class State:
    def __init__(self):
        # self.client: ZjuClient = None
        self.client: ZjuAsyncClient = None

state = State()