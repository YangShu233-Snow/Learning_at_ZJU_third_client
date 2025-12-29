import json
import sys
import zipfile
from pathlib import Path
from .load_config import backupConfig

def get_base_path() -> Path:
    """获取项目根目录绝对路径，兼容源码和 PyInstaller 打包后环境"""
    try:
        # PyInstaller 创建的临时路径
        base_path = Path(sys._MEIPASS)
    except Exception:
        # 不在 PyInstaller 环境中，使用普通路径
        base_path = Path(__file__).resolve().parent.parent.parent.parent
    
    return base_path

class ConfigBackupManager():
    def __init__(self):
        self._baseurl = get_base_path()
        self._files_path = backupConfig().load_config().get("files_path", None)

        if not self._files_path:
            self._files_path = {
                "api_list": "data/api_list.json",
            }

    def save_config(
        save_all_config: bool = False
    )->Path:
        pass

    def load_config(
        force: bool = False       
    )->bool:
        pass