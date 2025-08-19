import json
import os
from pathlib import Path
from printlog.print_log import print_log

class BaseConfig:
    """基本的json加载逻辑，初始化接受一个`config_name`作为文件名字，默认需要带有.json
    """    
    def __init__(self, parent_dir: str ,config_name: str):
        self.config_name:str = config_name
        self.current_script_path = Path(__file__).resolve()
        self.project_root = self.current_script_path.parent.parent.parent.parent
        self.config_parent_dir_path  = self.project_root / "data" / parent_dir
        self.config_path:Path = self.config_parent_dir_path / config_name

    def load_config(self)->dict:
        """加载并读取配置

        Returns
        -------
        dict
            返回一个记录配置的dict
        """        

        config = None
        # print(self.config_path)
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            print_log("Info", f"配置文件 '{self.config_name}'加载成功", "load_config.load_config")
        except FileNotFoundError:
            print_log("Warning", f"配置文件 '{self.config_name}' 未找到！", "load_config.load_config")
        except json.JSONDecodeError: # 处理 JSON 格式错误
            print_log("Warning", f"配置文件 '{self.config_name}' 可能为空！", "load_config.load_config")
        except IOError as e: # 捕获其他 IO 错误
            print_log("Warning", f"配置读取失败，IO错误: {e}", "load_config.load_config")

        if config == None:
            return {}
        
        return config
        
    def update_config(self, config_data: dict):
        """更新配置文件内容，调用此函数会直接在项目data/下相应目录创建对应的.json

        Parameters
        ----------
        config_data : dict
            新的完整配置内容

        Raises
        ------
        IOError
            如果读取不到，则报错
        """        

        # pathlib自动处理文件夹存在问题
        self.config_parent_dir_path.mkdir(parents = True, exist_ok = True)
        print_log("Info", f"配置文件{self.config_name}更新中中...", "load_config.update_config")
        try:
            with open(self.config_path, "w", encoding='utf-8') as f: # 推荐添加 encoding
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            
            print_log("Info", f"{self.config_name}配置更新成功，路径{self.config_path}", "load_config.update_config")

        except IOError:
            print_log("Warning", f"配置更新失败！", "load_config.update_config")
            raise IOError

class userConfig(BaseConfig):
    def __init__(self):
        super().__init__("", "user_config.json")

class globalConfig(BaseConfig):
    def __init__(self):
        super().__init__("", "global_config.json")

class apiListConfig(BaseConfig):
    def __init__(self):
        super().__init__("", "api_list.json")

class apiConfig(BaseConfig):
    def __init__(self, parent_dir: str ,api_name):
        self.config_name = api_name + "_config.json"
        self.parent_dir = "all_api_data/" + parent_dir
        super().__init__(self.parent_dir, self.config_name)

class coursesMessageConfig(BaseConfig):
    def __init__(self, config_name):
        self.config_name = config_name + ".json"
        self.parent_dir = "all_api_data/courses"
        super().__init__(self.parent_dir ,self.config_name)

class APIParseQueryConfig(BaseConfig):
    def __init__(self, config_name):
        self.config_name = config_name + "_query.json"
        super().__init__(self.config_name)

class myResourcesConfig(BaseConfig):
    def __init__(self):
        super().__init__("resources_list", "resources_list")

class searchCoursesResults(BaseConfig):
    def __init__(self):
        super().__init__("all_api_data/search_results", "my_courses_config.json")

class userIndexConfig(BaseConfig):
    def __init__(self, config_name: str):
        self.config_name = config_name + ".json"
        super().__init__("all_api_data/user_index",self.config_name)