import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from .CLI.CLI import app
from .printlog.print_log import setup_global_logging

# 初始化全局日志记录器
setup_global_logging()

if __name__ == "__main__":
    app()