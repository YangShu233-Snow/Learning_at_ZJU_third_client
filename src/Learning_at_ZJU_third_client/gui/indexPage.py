from PySide6.QtWidgets import QWidget, QLineEdit, QLabel, QHBoxLayout, QVBoxLayout, QPushButton


class IndexSearchBoxWidget(QWidget):
    """首页搜索框
    """    
    def __init__(self, parent = None):
        super().__init__(parent)
        self.setLayout(self.initialize_search_box())

    def initialize_search_box(self):
        # 创建搜索框布局，包含输入框与搜索按钮
        search_box_layout = QHBoxLayout()
        search_box_layout.setContentsMargins(0, 0, 0, 0)

        # 创建输入框
        self.search_box_input_line = QLineEdit(self)
        self.search_box_input_line.setPlaceholderText("按课程名或课号搜索...")
        self.search_box_input_line.setMinimumWidth(500)

        # 创建搜索按钮
        self.search_button = QPushButton("搜索", self)
        self.search_button.clicked.connect(self.search_func)
        self.search_box_input_line.returnPressed.connect(self.search_func)

        # 构建布局内容
        search_box_layout.addStretch(1)
        search_box_layout.addWidget(self.search_box_input_line)
        search_box_layout.addWidget(self.search_button)
        search_box_layout.addStretch(1)

        return search_box_layout

    def search_func(self):
        query = self.search_box_input_line.text()
        print(f"搜索{query}中...")
        self.search_box_input_line.clear()

class IndexPage(QWidget):
    """首页组件，登录后显示的第一个页面。包括一个可以搜索课程的搜索框，提示未完成任务的通知条，展示最新动态的组件和展示最近访问课程的组件。
    """    
    def __init__(self, recent_visit_courses: list[dict], new_updates: list[dict], todo_list_counts: int,parent=None):
        super.__init__(parent)
        self.recent_visit_courses = recent_visit_courses
        self.new_updates = new_updates

    def _init_index_page(self):
        index_page_layout = QVBoxLayout()

