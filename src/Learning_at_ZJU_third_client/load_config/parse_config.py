from printlog.print_log import print_log

class ConfigParser:
    def __init__(self, config, querys):
        self.config = config
        self.querys = querys
        self.result = {}

    def get_config_data(self):
        return self.construct_data()
    
    def make_query(self):
        pass
    
    def get_base_message(self):
        pass

class CourseModulesConfigParser(ConfigParser):
    def __init__(self, course_modules_config, course_modules_querys):
        self.course_modules_config = course_modules_config
        self.course_modules_message = self.course_modules_config.get("modules", None)
        self.course_modules_querys = course_modules_querys
        self.result = {}

    def get_config_data(self) -> dict:
        pass
    
class myCoursesConfigParser(ConfigParser):
    def __init__(self, my_courses_config: dict, my_courses_querys: dict[str: list[str]]):
        self.my_courses_config = my_courses_config
        self.my_courses_message: list[dict] = self.my_courses_config.get("courses", None)
        self.my_courses_querys = my_courses_querys
        self.result = {}

    def get_config_data(self)->dict:
        print_log("Info", f"正在从my_courses_config.json中提取数据...", "parse_config.myCoursesConfigParser.get_config_data")
        for course in self.my_courses_message:
            course_id = course.get("id", "0")
            self.result[course_id] = self.make_query(course=course)
        
        print_log("Info", "提取完成！", "parse_config.myCoursesConfigParser.get_config_data")
        return self.result

    def make_query(self, course: dict) -> dict:
        course_message = {}
        for query_name, query_config_path in self.my_courses_querys.items():
            current_val = course
            
            # 标准化查询路径为一个列表
            path_keys = []
            if isinstance(query_config_path, str):
                path_keys = [query_config_path]
            elif isinstance(query_config_path, list):
                path_keys = list(query_config_path) # 创建副本
            else:
                print_log("Warning", f"查询'{query_config_path}'的路径配置类型不受支持！", "parse_config.myCoursesConfigParser.make_query")
                course_message[query_name] = None
                continue

            for k_idx, key in enumerate(path_keys):
                if current_val is None: # 如果上一步没有获取到值，则跳出
                    break

                if isinstance(current_val, dict):
                    current_val = current_val.get(key)
                elif isinstance(current_val, list):
                    # 如果当前值是列表，并且当前键是路径中的最后一个键
                    # 这意味着这个键应该应用于列表中的每个字典元素
                    if k_idx == len(path_keys) - 1:
                        try:
                            new_list = []
                            for item in current_val:
                                if isinstance(item, dict):
                                    new_list.append(item.get(key))
                                else:
                                    new_list.append(None) # 列表中的项不是字典
                            current_val = new_list
                        except Exception as e:
                            # print(f"错误：在处理列表时提取键 '{key}' 失败：{e}")
                            current_val = None 
                    else:
                        # 如果当前值是列表，但路径中还有更多键，
                        # 当前的查询结构不支持这种深度查询列表内部的复杂结构
                        # print(f"警告：查询 '{query_name}' 在列表后还有更深的路径，当前逻辑不支持。")
                        current_val = None
                    break # 已经处理了列表（或发生错误），结束当前路径的键遍历
                else:
                    # 当前值不是字典也不是列表，无法继续用键获取值
                    current_val = None
                    break
            
            course_message[query_name] = current_val
        return course_message
    
    def get_base_message(self):
        pass