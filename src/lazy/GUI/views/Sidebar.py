import os
import pathlib
from pathlib import Path

from PySide6.QtWidgets import QPushButton, QWidget, QButtonGroup, QSpacerItem, QVBoxLayout
from PySide6.QtGui import QIcon, QPixmap

CURRENT_DIR = Path(__file__).parent
ASSETS_BASEDIR = CURRENT_DIR / ".." / "assets" / "Sidebar"

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
        group = QButtonGroup(self)
        group.addButton(self.home_button)
        group.addButton(self.course_button)
        group.addButton(self.resource_button)
        group.addButton(self.rollcall_button)

class Sidebar(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        layout.addWidget(SidebarButtonsWidget())
        layout.addStretch()
        layout.addWidget(SettingsButton())

        self.setLayout(layout)

        self.setMaximumWidth(80)