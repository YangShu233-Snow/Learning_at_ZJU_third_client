import abc
import json
import sys
import zipfile
import logging
from typing import List
from pathlib import Path
from datetime import datetime
from .load_config import userBackupConfig, lazyBackupConfig, logBackupConfig

logger = logging.getLogger(__name__)

def resource_path(relative_path: str|Path = "") -> Path:
    """获取绝对路径，兼容源码和 PyInstaller 打包后环境"""
    try:
        # PyInstaller 创建的临时路径
        base_path = Path(sys._MEIPASS)
    except Exception:
        # 不在 PyInstaller 环境中，使用普通路径
        base_path = Path(__file__).resolve().parent.parent.parent.parent
    
    return base_path / relative_path

# 文件备份抽象基类
class BaseFileBackupHandler(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def backup(self):
        pass

# 日志文件备份
class logFileHandler(BaseFileBackupHandler):
    def __init__(self, 
                 paths: List[str|Path],
                 output: str|Path = Path.home()):
        self.paths: List[Path] = list(map(lambda path: Path.home() / path, paths))
        self.output = output
        self.log_paths = []

        for path in self.paths:
            logs_to_zip = path.glob("lazy_cli.log*")
            self.log_paths.extend(logs_to_zip)

    def backup(self)->bool:
        try:
            with zipfile.ZipFile(self.output, 'w') as zf:
                for path in self.log_paths:
                    zf.write(path)

        except Exception as e:
            logger.error(f"备份出错！{e}")
            return False
        
        logger.info(f"日志备份完成，保存位置: {self.output}")
        return True

# lazy文件备份
class LazyFileHandler(BaseFileBackupHandler):
    def __init__(self, 
                 paths: List[str|Path],
                 output: str|Path = Path.home()):
        self.base_path = resource_path()
        self.paths: List[Path] = list(map(resource_path, paths))
        self.output = output

    def backup(self)->bool:
        try:
            with open(resource_path("mainfest.json"), 'w') as f:
                mainfest = {
                    "backup_time": datetime.now().strftime('%Y-%m-%d'),
                    "files": [
                        dict(
                            archive_path=path.name,
                            original_path=str(path.relative_to(self.base_path))
                        ) for path in self.paths
                    ]
                }

                f.write(json.dumps(mainfest))

            with zipfile.ZipFile(self.output, 'w') as zf:
                for path in self.paths:
                    logger.info(f"正在备份 {path}")
                    zf.write(path, arcname=path.relative_to(self.base_path))

                zf.write(resource_path("mainfest.json"), arcname="mainfest.json")

        except Exception as e:
            logger.error(f"备份出错！{e}")
            return False
        
        logger.info(f"应用配置备份完成，保存位置: {self.output}")
        return True

# 用户文件备份
class LazyUserFileHandler(BaseFileBackupHandler):
    def __init__(self, 
                 paths: List[str|Path],
                 output: str|Path = Path.home()):
        self.base_path = resource_path()
        self.paths: List[Path] = list(map(resource_path, paths))
        self.output = output

    def backup(self)->bool:
        try:
            with open(resource_path("mainfest.json"), 'w') as f:
                mainfest = {
                    "backup_time": datetime.now().strftime('%Y-%m-%d'),
                    "files": [
                        dict(
                            archive_path=path.name,
                            original_path=str(path.relative_to(self.base_path))
                        ) for path in self.paths
                    ]
                }

                f.write(json.dumps(mainfest))

            with zipfile.ZipFile(self.output, 'w') as zf:
                for path in self.paths:
                    logger.info(f"正在备份 {path}")
                    zf.write(path, arcname=path.relative_to(self.base_path))

                zf.write(resource_path("mainfest.json"), arcname="mainfest.json")

        except Exception as e:
            logger.error(f"备份出错！{e}")
            return False
        
        logger.info(f"用户配置备份完成，保存位置: {self.output}")
        return True

class BackupManager:
    def __init__(self,
                 output_dir: str|Path = Path.home()):
        self.user_backup_config = userBackupConfig().load_config()
        self.lazy_backup_config = lazyBackupConfig().load_config()
        self.log_backup_config = logBackupConfig().load_config()
        self.output_dir = output_dir

    def run_for_user(self):
        for task in self.user_backup_config["tasks"]:
            class_name = task["type"]
            sources_list = task["params"]["sources_list"]
            output = self.output_dir / Path(task["params"]["output_name"])

            cls = globals().get(class_name)

            if cls:
                instance = cls(sources_list, output)
                if not instance.backup():
                    break
            else:
                logger.warning(f"未找到 {class_name}")
        else:
            return True
        
        logger.error("用户配置文件备份过程出错！")
        return False
    
    def run_for_lazy(self):
        for task in self.lazy_backup_config["tasks"]:
            class_name = task["type"]
            sources_list = task["params"]["sources_list"]
            output = self.output_dir / Path(task["params"]["output_name"])

            cls = globals().get(class_name)

            if cls:
                instance = cls(sources_list, output)
                if not instance.backup():
                    break
            else:
                logger.warning(f"未找到 {class_name}")
        else:
            return True
        
        logger.error("程序配置文件备份过程出错！")
        return False

    def run_for_log(self):
        for task in self.log_backup_config["tasks"]:
            class_name = task["type"]
            sources_list = task["params"]["sources_list"]
            output = self.output_dir / Path(task["params"]["output_name"])

            cls = globals().get(class_name)

            if cls:
                instance = cls(sources_list, output)
                if not instance.backup():
                    break
            else:
                logger.warning(f"未找到 {class_name}")
        else:
            return True
        
        logger.error("日志文件备份出错！")
        return False
    
class LoadManager:
    def __init__(self,
                 paths: List[str|Path],
                 force: bool = False):
        self.base_path = resource_path()
        self.paths = paths
        self.force = force
        self.lazy_configs = [
            "lazy_backup.json",
            "user_backup.json",
            "log_backup.json",
            "api_list.json"
        ]

    def load(self)->bool:
        for path in self.paths:
            logger.info(f"正在加载文价: {path}")
            try:
                with zipfile.ZipFile(path, 'r') as zf:
                    mainfest = json.loads(zf.read("mainfest.json").decode('utf-8'))
                    files = mainfest["files"]

                    for file in files:
                        if not self.force:
                            if not self._is_valid(file["archive_path"]):
                                logger.warning(f'{file["archive_path"]} 被忽略！')
                                continue
                        
                        file_content = zf.read(file["original_path"]).decode('utf-8')

                        with open(self.base_path / file["original_path"], 'w') as f:
                            f.write(file_content)

                        logger.info(f'{file["archieve_path"]} 已载入！')
            except Exception as e:
                logger.error(f"{path} 配置加载失败。错误原因: {e}")
                return False

        return True

    def _is_valid(self, path: str|Path)->bool:
        filename = Path(path).name
        if filename in self.lazy_configs:
            return False
        
        return True