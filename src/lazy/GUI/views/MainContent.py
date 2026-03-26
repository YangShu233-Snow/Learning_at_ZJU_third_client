from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .utils.get_round_icon import get_round_icon

CURRENT_DIR = Path(__file__).parent
ASSETS_BASEDIR = CURRENT_DIR / ".." / "assets"

class HomeContentUserInfoWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.user_avater_label = self._generate_user_avater_label()
        self.username_label = self._get_username()
        self.greating_label = self._generate_greeting_label()

        self.sub_user_info_layout = QVBoxLayout()
        self.sub_user_info_layout.addWidget(self.username_label)
        self.sub_user_info_layout.addSpacing(20)
        self.sub_user_info_layout.addWidget(self.greating_label)
        
        self.user_info_layout = QHBoxLayout(self)
        self.user_info_layout.addWidget(self.user_avater_label)
        self.user_info_layout.addSpacing(20)
        self.user_info_layout.addLayout(self.sub_user_info_layout)

    def _generate_greeting_label(self)->QLabel:
        now_time = datetime.now().hour

        if 0 <= now_time < 6:
            return QLabel("夜深了，早点睡吧~")
        if 6 <= now_time < 12:
            return QLabel("早上好，今天也要活力满满！")
        if 12 <= now_time < 18:
            return QLabel("下午好，今天的天气怎么样？")
        if 18 <= now_time < 24:
            return QLabel("晚上好，今天辛苦啦。")
        return QLabel("Wrong Time Format")
        
    def _generate_user_avater_label(self)->QLabel:
        avater_label = QLabel()
        avater_path = self._get_avater_path()
        avater = QPixmap(avater_path)

        if not avater.isNull():
            round_pixmap = get_round_icon(avater, 30)
            
        avater_label.setPixmap(round_pixmap)

        return avater_label

    def _get_avater_path(self)->Path:
        user_avater_path = ASSETS_BASEDIR / "avater.jpg"
        default_avater_path = ASSETS_BASEDIR / "default_avater.jpg"
        if user_avater_path.exists():
            return user_avater_path
        
        return default_avater_path
    
    def _get_username(self)->QLabel:
        return QLabel("")

class HomeContentWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        # 主布局：水平排列，分为左右两部分
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setSpacing(20)
        self.main_layout.setContentsMargins(20, 20, 20, 20)

        # --- 左侧布局 ---
        self.left_layout = QVBoxLayout()
        self.left_layout.setSpacing(20)

        # 1. 左上角：用户信息 (头像 + 问候语)
        self.user_info_widget = HomeContentUserInfoWidget()

        # 2. 左下角：今日课程 (滑动组件)
        self.course_section = QWidget()
        self.course_section_layout = QVBoxLayout(self.course_section)
        self.course_section_layout.setContentsMargins(0, 0, 0, 0)
        
        self.course_title = QLabel("今日课程")
        self.course_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.course_scroll = QScrollArea()
        self.course_scroll.setWidgetResizable(True)
        self.course_scroll.setFrameShape(QFrame.NoFrame)
        
        self.course_container = QWidget()
        self.course_list_layout = QVBoxLayout(self.course_container)
        self.course_list_layout.setAlignment(Qt.AlignTop)
        
        # 预留添加课程条目的方法
        self._add_course_placeholder("示例课程 1 - 8:00 AM", "主楼 101")
        self._add_course_placeholder("示例课程 2 - 10:00 AM", "实验楼 202")
        self._add_course_placeholder("示例课程 3 - 2:00 PM", "西教 303")
        self._add_course_placeholder("示例课程 4 - 4:00 PM", "西教 404")
        
        self.course_scroll.setWidget(self.course_container)
        
        self.course_section_layout.addWidget(self.course_title)
        self.course_section_layout.addWidget(self.course_scroll)

        self.left_layout.addWidget(self.user_info_widget)
        self.left_layout.addWidget(self.course_section, stretch=1)

        # --- 右侧布局 ---
        self.right_layout = QVBoxLayout()
        self.right_layout.setSpacing(10)
        
        self.todo_title = QLabel("待办事项")
        self.todo_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        
        self.todo_list = QListWidget()
        self.todo_list.addItem("完成作业 1")
        self.todo_list.addItem("准备展示 PPT")
        self.todo_list.addItem("回复导师邮件")
        
        self.right_layout.addWidget(self.todo_title)
        self.right_layout.addWidget(self.todo_list)

        # 组合到主布局
        self.main_layout.addLayout(self.left_layout, stretch=2)
        self.main_layout.addLayout(self.right_layout, stretch=1)

    def _add_course_placeholder(self, name, location):
        """用于测试的课程项占位符"""
        item = QFrame()
        item.setFrameShape(QFrame.StyledPanel)
        item.setMinimumHeight(80)
        l = QVBoxLayout(item)
        l.addWidget(QLabel(name))
        l.addWidget(QLabel(location))
        self.course_list_layout.addWidget(item)

class CourseContentWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("课程内容"))

class ResourceContentWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("资源内容"))

class RollcallContentWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("点名内容"))


class MainContent(QWidget):
    def __init__(self):
        super().__init__()

        self.stackwidget = QStackedWidget()
        for widget in [
            HomeContentWidget(),
            CourseContentWidget(), 
            ResourceContentWidget(), 
            RollcallContentWidget()
        ]:
            self.stackwidget.addWidget(widget)

        layout = QVBoxLayout(self)
        layout.addWidget(self.stackwidget)