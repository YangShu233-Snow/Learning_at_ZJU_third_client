
# 维护全局登录状态
class State:
    """状态类，用于在 LAZY CLI 内共享全局状态
    """
    def __init__(self):
        # self.client: ZjuClient = None
        self.trust_env: bool = True

state = State()