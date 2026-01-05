import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_global_logging():
    """
    设置全局日志系统
    """

    # 全局日志文件配置
    log_dir = Path.home() / ".lazy_cli_logs"
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

    if not logger.handlers:
        logger.addHandler(log_file_hanlder)