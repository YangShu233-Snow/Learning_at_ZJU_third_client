from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
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
        self.sub_user_info_layout.addSpacing(5)
        self.sub_user_info_layout.addWidget(self.greating_label)
        
        self.user_info_layout = QHBoxLayout(self)
        self.user_info_layout.addWidget(self.user_avater_label)
        self.user_info_layout.addSpacing(5)
        self.user_info_layout.addLayout(self.sub_user_info_layout)
        self.user_info_layout.addStretch()

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
            round_pixmap = get_round_icon(avater, 50)
            
        avater_label.setPixmap(round_pixmap)

        return avater_label

    def _get_avater_path(self)->Path:
        user_avater_path = ASSETS_BASEDIR / "avater.jpg"
        default_avater_path = ASSETS_BASEDIR / "default_avater.jpg"
        if user_avater_path.exists():
            return user_avater_path
        
        return default_avater_path
    
    def _get_username(self)->QLabel:
        return QLabel("xxx")

class HomeContentTodayCoursesWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        
        self.title = QLabel("今日课程")

        self.today_course_scroll = 0

    def _add_course_placeholder(
        self, 
        course_name: str, 
        teachers: list[str], 
        course_time: str,
        department_name: str
    ):
        """用于测试的课程项占位符"""
        item = TodayCourseFrame(
            course_name,
            teachers,
            course_time,
            department_name
        )
        self.course_list_layout.addWidget(item)

class TodayCourseFrame(QFrame):
    def __init__(
        self,
        course_name: str,
        teachers: list[str],
        course_time: str,
        department_name: str            
    ):
        super().__init__()

        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(80)

        course_layout = QVBoxLayout(self)
        course_main_info_layout = QHBoxLayout(course_layout)
        course_minor_info_layout = QVBoxLayout(course_layout)

        self.course_name_label = QLabel(course_name)
        
        teachers_name = self._format_teachers_name(teachers)
        self.teachers_name_label = QLabel(teachers_name)

        self.course_time = QLabel(course_time)
        self.department_name = QLabel(department_name)

        course_main_info_layout.addWidget(self.course_name_label)
        course_main_info_layout.addWidget(self.department_namel)
        course_minor_info_layout.addWidget(self.course_time)
        course_minor_info_layout.addWidget(self.teachers_name_label)

    def _format_teachers_name(teachers)->str:
        teachers_name = ""
        for teacher in teachers:
            if len(f"{teachers_name}, {teacher}") > 22:
                teachers_name = teachers_name + "..."
                break

            teachers_name = ', '.join((teachers_name, teacher))

        return teachers_name

class HomeContentTodoItem(QFrame):
    def __init__(
            self,
            assignment_name: str,
            course_name: str,
            deadline: datetime,
            type: str
        ):
        super().__init__()
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(80)

        layout = QVBoxLayout(self)

        title_line = QLabel(f"[{type}] {assignment_name}")
        sub_title_line = QLabel(f"{course_name}")
        ddl_line = QLabel(f"截止时间: {deadline}")

        layout.addWidget(title_line)
        layout.addWidget(sub_title_line)
        layout.addWidget(ddl_line)

class HomeContentTodoListWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        self.title = QLabel("待办事项")
        self.todo_list_view = QScrollArea()
        self.todo_list = QWidget()
        self.todo_list_layout = QVBoxLayout(self.todo_list)

        self.todo_list_view.setWidgetResizable(True)
        self.todo_list_view.setWidget(self.todo_list)

        layout.addWidget(self.title)
        layout.addWidget(self.todo_list_view)
    
    def add_todo_item(
        self,
        assignment_name: str,
        course_name: str,
        deadline: datetime,
        type: str
    ):
        self.todo_list_layout.addWidget(
            HomeContentTodoItem(
                assignment_name,
                course_name,
                deadline,
                type
            )
        )
    
    def add_todo_stretch(self):
        self.todo_list_layout.addStretch()

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
            
        self.todo_list = HomeContentTodoListWidget()
        for _ in range(20):
            self.todo_list.add_todo_item(
                "测试1",
                "课程名字",
                datetime.now(),
                "作业"
            )

        self.todo_list.add_todo_stretch()

        self.left_layout.addWidget(self.todo_list)
        self.left_layout.addStretch()

        # --- 右侧布局 ---
        self.right_layout = QVBoxLayout()
        self.right_layout.setSpacing(10)

        
        self.right_layout.addWidget(QLabel("这里留给课表"))
        self.right_layout.addStretch()

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