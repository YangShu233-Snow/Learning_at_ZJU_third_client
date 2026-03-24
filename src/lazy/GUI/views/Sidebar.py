from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QButtonGroup, QLabel, QPushButton, QVBoxLayout, QWidget

from .utils.get_round_icon import get_round_icon

CURRENT_DIR = Path(__file__).parent
ASSETS_BASEDIR = CURRENT_DIR / ".." / "assets" / "Sidebar"

class UserAvater(QLabel):
    def __init__(self):
        super().__init__()
        avater_path = self._check_avater()
        avater = QPixmap(avater_path)
        if not avater.isNull():
            round_pixmap = get_round_icon(avater, 30)
            self.setPixmap(round_pixmap)

        self.setFixedSize(30, 30)
        
    
    def _check_avater(self)->Path:
        user_avater_path = ASSETS_BASEDIR / "avater.jpg"
        default_avater_path = ASSETS_BASEDIR / "default_avater.jpg"
        if user_avater_path.exists():
            return user_avater_path
        
        return default_avater_path

class SideBarButton(QPushButton):
    def __init__(self, icon_name: str, icon_dir: str|Path = None):
        super().__init__()
        if not icon_dir:
            icon_dir = Path(ASSETS_BASEDIR)

        icon_path = icon_dir / icon_name

        self.setIcon(QIcon(QPixmap(icon_path)))
        self.setCheckable(True)

        self.setMaximumWidth(25)
        self.setMaximumHeight(25)


class HomeButton(SideBarButton):
    def __init__(self):
        super().__init__("home.svg")

class CourseButton(SideBarButton):
    def __init__(self):
        super().__init__("course.svg")

class ResourseButton(SideBarButton):
    def __init__(self):
        super().__init__("resource.svg")

class RollcallButton(SideBarButton):
    def __init__(self):
        super().__init__("rollcall.svg")

class SettingsButton(QPushButton):
    def __init__(self):
        super().__init__()

        self.setIcon(QIcon(QPixmap(ASSETS_BASEDIR / "settings.svg")))

        self.setMaximumWidth(25)
        self.setMaximumHeight(25)
        
class SidebarButtonsWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.home_button = HomeButton()
        self.course_button = CourseButton()
        self.resource_button = ResourseButton()
        self.rollcall_button = RollcallButton()

        # 布局
        layout = QVBoxLayout(self)
        layout.addWidget(self.home_button)
        layout.addSpacing(5)
        layout.addWidget(self.course_button)
        layout.addSpacing(5)
        layout.addWidget(self.resource_button)
        layout.addSpacing(5)
        layout.addWidget(self.rollcall_button)
        
        # 逻辑组
        self.group = QButtonGroup(self)
        self.group.addButton(self.home_button, id=0)
        self.group.addButton(self.course_button, id=1)
        self.group.addButton(self.resource_button, id=2)
        self.group.addButton(self.rollcall_button, id=3)

class Sidebar(QWidget):
    def __init__(self):
        super().__init__()
        self.user_avater_label = UserAvater()
        self.sidebar_buttons_widgets = SidebarButtonsWidget()

        layout = QVBoxLayout()
        layout.addWidget(self.user_avater_label)
        layout.addSpacing(10)
        layout.addWidget(self.sidebar_buttons_widgets)
        layout.addStretch()
        layout.addWidget(SettingsButton())

        self.setLayout(layout)

        self.setMaximumWidth(80)