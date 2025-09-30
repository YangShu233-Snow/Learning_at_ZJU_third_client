import time
from ..load_config import load_config

def print_log(log_type: str, log_message: str, log_from: str = None):
    # return 
    if log_from == None:
        print_log(log_type="Error", log_message="log_from不可为空！", log_from="print_log")
        return

    log_type_config = ["Info", "Warning", "Error", "Debug"]
    if log_type not in log_type_config:
        print_log(log_type="Error", log_message=f"来自{log_from}的log请求有误！log类型不存在！", log_from="print_log")
        return
    
    print(f"[{log_type} {time.strftime('%H:%M:%S', time.localtime())}]{log_from}: {log_message}")

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_global_logging():
    """
    设置全局日志系统
    """

    # 全局日志文件配置
    log_dir = Path(__file__).parent.parent.parent / "log"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "lazy_cli.log"

    # 日志文件格式
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 初始化日志记录器
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 初始化日志处理器
    log_file_hanlder = RotatingFileHandler(
        log_file, 
        maxBytes = 5 * 1024 * 1024, 
        backupCount = 3,
        encoding = 'utf-8'
    )
    log_file_hanlder.setFormatter(log_format)
    log_file_hanlder.setLevel(logging.DEBUG)

    log_console_handler = logging.StreamHandler()
    log_console_handler.setFormatter(log_format)
    log_console_handler.setLevel(logging.WARNING)

    if not logger.handlers:
        logger.addHandler(log_file_hanlder)
        logger.addHandler(log_console_handler)