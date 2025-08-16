import sys
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QRect, QSize, QByteArray
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QLineEdit, QHBoxLayout, QPushButton, QSizePolicy
from load_config import load_config
from .QtExtention.QFlowLayout import FlowLayout

DEFAULT_USER_AVATAR_SVG = """<svg viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
  <path fill="#4A90E2" d="M27.5,27.2c1.5-1.5,2.6-3.2,3.4-5.1c0,0,0-0.1,0-0.1c0.2-0.4,0.3-0.9,0.5-1.4c0-0.1,0-0.2,0.1-0.3 c0.1-0.4,0.2-0.8,0.3-1.2c0-0.2,0.1-0.4,0.1-0.6c0-0.3,0.1-0.6,0.1-0.9c0.1-0.5,0.1-1,0.1-1.6c0-4.3-1.7-8.3-4.7-11.3 c-3-3-7-4.7-11.3-4.7C11.7,0,7.7,1.7,4.7,4.7c-3,3-4.7,7-4.7,11.3c0,0.5,0,1,0.1,1.5c0,0.3,0.1,0.5,0.1,0.8c0,0.2,0.1,0.5,0.1,0.7 c0.1,0.4,0.2,0.7,0.3,1c0,0.1,0.1,0.3,0.1,0.4c0.1,0.4,0.3,0.8,0.4,1.2c0,0.1,0,0.1,0.1,0.2c0.2,0.4,0.4,0.9,0.6,1.3c0,0,0,0,0,0.1 c0.7,1.3,1.5,2.6,2.6,3.7c0,0,0,0,0,0l0,0c0.1,0.1,0.2,0.3,0.4,0.4c3,3,7,4.7,11.3,4.7c4.3,0,8.3-1.7,11.3-4.7 C27.4,27.3,27.4,27.2,27.5,27.2L27.5,27.2C27.5,27.2,27.5,27.2,27.5,27.2z M5.4,5.4C8.2,2.6,12,1,16,1s7.8,1.6,10.6,4.4S31,12,31,16 c0,0.5,0,1-0.1,1.5c0,0.2-0.1,0.5-0.1,0.7c0,0.2-0.1,0.5-0.1,0.7c-0.1,0.3-0.2,0.7-0.2,1c0,0.1-0.1,0.2-0.1,0.4 c-0.1,0.4-0.2,0.8-0.4,1.1c0,0.1,0,0.1-0.1,0.2c-0.2,0.4-0.3,0.8-0.6,1.2c0,0,0,0,0,0c-0.6,1.2-1.5,2.4-2.4,3.4 c-1-1.3-3.3-2.2-6-2.2c-3,0-3-1.1-2.7-2.3c0.4-1.5,3.1-0.8,3.9-4.8c0,0,1.5-1.1,1.7-2.3s-0.7-1.8-1.6-1.2c0,0,1-6.7-4-7.8 c-0.7-0.2-1.6-0.3-2.4-0.3c-1.1,0-2,0.2-2.8,0.4c-0.4,0.1-0.8,0.3-1.1,0.6c-0.6,0-1.6,0.1-2.4-0.1c0,0,0.1,1.4,0.3,2.4 c0,0.1-0.5-0.1-0.7,0.6C9,9.7,9.2,11.4,9.4,12.4c0,0.6,0.1,1.1,0.1,1.1c-0.9-0.5-1.7,0-1.6,1.2C8,15.9,9.5,17,9.5,17 c0.8,3.9,3.4,3.2,3.9,4.8c0.3,1.2,0.3,2.2-2.7,2.3c-2.6,0-4.7,0.9-5.8,2.1C4.6,25.7,4.3,25.4,4,25c0,0,0,0,0,0 c-0.3-0.4-0.5-0.7-0.8-1.1c0,0,0,0,0-0.1c-0.2-0.4-0.4-0.7-0.6-1.1c0,0,0-0.1-0.1-0.1c-0.2-0.4-0.3-0.7-0.5-1.1 c0-0.1-0.1-0.2-0.1-0.3c-0.1-0.3-0.2-0.7-0.3-1c0-0.2-0.1-0.3-0.1-0.5c-0.1-0.3-0.2-0.6-0.2-0.9c0-0.2-0.1-0.5-0.1-0.7 c0-0.2-0.1-0.4-0.1-0.7C1,17,1,16.5,1,16C1,12,2.6,8.2,5.4,5.4z" />
</svg>
"""

CURRENT_SCRIPT_PATH = Path(__file__)
USER_AVATAR_PATH = CURRENT_SCRIPT_PATH.parent.parent.parent.parent / "images/user_avatar.png"
DEFAULT_COURSE_COVER_PATH = CURRENT_SCRIPT_PATH.parent.parent.parent.parent / "images/default_course_cover.png"

TIME_DIVISION_RANGE = [
    (5, 7, "早安"),
    (7, 12, "上午好"),
    (12, 14, "中午好"),
    (14, 17, "下午好"),
    (17, 19, "傍晚好"),
    (19, 24, "晚上好")
]

class UserWelcomeGreetingsLabel(QLabel):
    """欢迎页问候语

    Parameters
    ----------
    QLabel : _type_
        _description_
    """    
    def __init__(self, parent = None):
        super().__init__(parent)
        self.username = load_config.userConfig().load_config().get("username")
        self.setText(self._init_user_welcome_greetings())
        self.setProperty("class", "UserWelcomeGreetingsLabel")

    def _init_user_welcome_greetings(self):
        current_hour = datetime.now().hour
        for start_time, end_time, greetings in TIME_DIVISION_RANGE:
            if start_time <= current_hour < end_time:
                greetings = greetings + f"{self.username}"
                break
        else:
            greetings = "夜深了，注意休息"

        return greetings


class UserWelcomeProfileAvatarLabel(QLabel):
    """欢迎页用户头像组件

    Parameters
    ----------
    QLabel : _type_
        _description_
    """    
    def __init__(self, pixmap: QPixmap, parent = None):
        super().__init__(parent)
        self.setPixmap(self._create_circular_pixmap(pixmap))
        
    def _create_circular_pixmap(self, src_pixmap: QPixmap)->QPixmap:
        size = min(src_pixmap.width(), src_pixmap.height())

        # 创建空白圆形模板
        template_circle = QPixmap(size, size)
        template_circle.fill(Qt.GlobalColor.transparent)

        # 绘制
        painter = QPainter(template_circle)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 设置蒙版区域
        path = QPainterPath()
        path.addEllipse(0, 0, size, size)
        painter.setClipPath(path)

        # 将原图片裁剪
        source_rect = QRect(0, 0, src_pixmap.width(), src_pixmap.height())
        painter.drawPixmap(template_circle.rect(), src_pixmap, source_rect)
        
        painter.end()
        
        return template_circle

class WelcomeSearchBoxWidget(QWidget):
    """欢迎页课程搜索框

    Parameters
    ----------
    QWidget : _type_
        _description_
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
        self.search_box_input_line.setMaximumWidth(500)
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

class subRecentVisitCourse(QWidget):
    """单个最近浏览课程的组件

    Parameters
    ----------
    QWidget : _type_
        _description_
    """    
    def __init__(self, course_name : str, course_schedule : str, course_avatar: QPixmap, parent = None):
        """单个最近浏览课程的组件

        Parameters
        ----------
        course_name : str
            课名
        course_schedule : str
            课程时间安排
        course_avatar : QPixmap
            课程封面
        parent : _type_, optional
            _description_, by default None
        """        
        super().__init__(parent)
        self.course_name = course_name
        self.course_schedule = course_schedule
        
        # 初始化图片对象，并加载二进制数据
        self.course_avatar = QPixmap()
        self.course_avatar.loadFromData(course_avatar)
        
        # 初始化单个最近浏览课程
        self._init_sub_recent_visit_course()
        self.setFixedSize(350, 125)
        self.setProperty("class", "RecentVisitCourseCard")

    def _init_sub_recent_visit_course(self):
        """单个最近浏览课程
        """        
        # 最近浏览课程的布局
        sub_recent_visit_course_layout = QHBoxLayout()
        
        # 构建课程封面标签与课程信息组件
        course_avatar_label = self._init_course_avatar()
        course_message_widget = self._init_course_message()

        sub_recent_visit_course_layout.addWidget(course_avatar_label, 1)
        sub_recent_visit_course_layout.addWidget(course_message_widget, 2)

        self.setLayout(sub_recent_visit_course_layout)

    def _init_course_message(self):
        """最近浏览课程的基本信息：课名和课程时间安排

        Returns
        -------
        _type_
            _description_
        """        
        course_message_widget = QWidget(self)
        course_message_layout = QVBoxLayout()
        
        # 创建课名与课程时间label
        course_name_label = QLabel(self.course_name)
        course_schedule_label = QLabel(self.course_schedule)

        course_name_label.setWordWrap(True)
        course_schedule_label.setWordWrap(True)

        # 构建布局并加载入组件
        course_message_layout.addStretch(1)
        course_message_layout.addWidget(course_name_label)
        course_message_layout.addWidget(course_schedule_label)
        course_message_layout.setSpacing(45)
        course_message_layout.addStretch(1)
        course_message_widget.setLayout(course_message_layout)

        return course_message_widget

    def _init_course_avatar(self):
        """加载最近浏览的课程的封面

        Returns
        -------
        _type_
            _description_
        """        
        # 尺寸不符合要求，则缩放
        if self.course_avatar.width() != 135 or self.course_avatar.height() != 75:
            default_size = QSize(135, 75)
            self.course_avatar = self.course_avatar.scaled(default_size,
                                                           Qt.AspectRatioMode.IgnoreAspectRatio,
                                                           Qt.TransformationMode.SmoothTransformation)
        
        course_avatar_label = QLabel()
        course_avatar_label.setPixmap(self.course_avatar)
        
        return course_avatar_label

class RecentVisitCourses(QWidget):
    """最近浏览的课程组件

    Parameters
    ----------
    QWidget : _type_
        _description_
    """    
    def __init__(self, recent_visit_courses: list[dict], parent = None):
        super().__init__(parent)
        self.recent_visit_courses = recent_visit_courses
        self._init_recent_visit_courses()

    def _init_recent_visit_courses(self):
        """加载所有最近浏览课程，并组装为最近浏览的组件
        """        
        recent_visit_courses_layout = FlowLayout(self, margin=10, h_spacing=15, v_spacing=15, alignment=Qt.AlignCenter)
        
        if not self.recent_visit_courses:
            # 如果没有课程，可以显示一个提示
            no_course_label = QLabel("最近没有浏览过课程哦~")
            no_course_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            recent_visit_courses_layout.addWidget(no_course_label)
        else:
            for recent_visit_course in self.recent_visit_courses:
                course_name = recent_visit_course.get("course_name")
                course_schedule = recent_visit_course.get("course_schedule")
                course_avatar = recent_visit_course.get("cover")
                
                if course_avatar is None:
                    with open(DEFAULT_COURSE_COVER_PATH, "rb") as f:
                        course_avatar = f.read()
                
                # 组装单个最近课程的组件
                recent_visit_course_widget = subRecentVisitCourse(course_name, course_schedule, course_avatar)
                recent_visit_courses_layout.addWidget(recent_visit_course_widget)
            
        self.setLayout(recent_visit_courses_layout)

class UserWelcomePage(QWidget):
    def __init__(self, recent_visit_courses: list[dict], parent = None):
        super().__init__(parent)
        self.recent_visit_courses = recent_visit_courses
        self._init_user_index_page()

    def _init_user_index_page(self):
        user_welcome_page_layout = QVBoxLayout()

        # 创建头像实例
        user_avater_label = self._init_avatar()

        # 创建问候语实例
        greetings_label = self._init_greetings_label()

        # 创建搜索框实例
        search_box_widget = self._init_search_box()

        # 创建最近访问课程实例
        recent_visit_courses_widget = self._init_recent_visit_courses()
        recent_visit_courses_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        user_welcome_page_layout.addStretch(1)

        # 构建布局
        user_welcome_page_layout.addWidget(user_avater_label, 0, Qt.AlignmentFlag.AlignCenter)
        user_welcome_page_layout.addWidget(greetings_label, 0, Qt.AlignmentFlag.AlignCenter)
        user_welcome_page_layout.addWidget(search_box_widget)
        user_welcome_page_layout.addWidget(recent_visit_courses_widget)

        user_welcome_page_layout.setSpacing(20)

        user_welcome_page_layout.addStretch(1)

        # 加载布局进组件
        self.setLayout(user_welcome_page_layout)

    def _init_avatar(self):
        """初始化头像

        Returns
        -------
        _type_
            _description_
        """        
        # 加载头像
        if Path(USER_AVATAR_PATH).exists():
            avatar_pixmap = QPixmap(USER_AVATAR_PATH)
        else:
            avatar_pixmap = self._draw_default_avatar()
            
        # 缩放
        target_size = 150
        avatar_pixmap = avatar_pixmap.scaled(target_size, target_size, 
                                             Qt.AspectRatioMode.KeepAspectRatio,
                                             Qt.TransformationMode.SmoothTransformation)
        
        return UserWelcomeProfileAvatarLabel(avatar_pixmap)
    
    def _init_greetings_label(self):
        """初始化问候语

        Returns
        -------
        _type_
            _description_
        """        
        return UserWelcomeGreetingsLabel()

    def _init_search_box(self):
        """初始化搜索框

        Returns
        -------
        _type_
            _description_
        """        
        return WelcomeSearchBoxWidget()
    
    def _init_recent_visit_courses(self):
        """初始化并加载最近浏览课程

        Returns
        -------
        _type_
            _description_
        """        
        return RecentVisitCourses(self.recent_visit_courses)
    
    def _draw_default_avatar(self):
        # 初始化svg渲染器
        user_avatar_render = QSvgRenderer(QByteArray(DEFAULT_USER_AVATAR_SVG.encode("utf-8")))
        user_avatar_size = QSize(150, 150)

        # 初始化pixmap，填充透明背景
        user_avatar_pixmap = QPixmap(user_avatar_size)
        user_avatar_pixmap.fill(Qt.GlobalColor.transparent)

        # 绘制svg
        user_avatar_painter = QPainter(user_avatar_pixmap)
        user_avatar_render.render(user_avatar_painter)
        user_avatar_painter.end()

        return user_avatar_pixmap