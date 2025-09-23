import time
from ..load_config import load_config

def print_log(log_type: str, log_message: str, log_from: str = None):
    return 
    if log_from == None:
        print_log(log_type="Error", log_message="log_from不可为空！", log_from="print_log")
        return

    log_type_config = ["Info", "Warning", "Error", "Debug"]
    if log_type not in log_type_config:
        print_log(log_type="Error", log_message=f"来自{log_from}的log请求有误！log类型不存在！", log_from="print_log")
        return
    
    print(f"[{log_type} {time.strftime('%H:%M:%S', time.localtime())}]{log_from}: {log_message}")