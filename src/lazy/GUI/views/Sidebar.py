import os

from PySide6.QtWidgets import (
    QPushButton,
    QWidget,
)

ASSETS_BASEDIR = "../assets/Sidebar"

class HomeButton(QPushButton):
    def __init__(self):
        super().__init__()

        self.setIcon(os.path.join(ASSETS_BASEDIR, "home.svg"))
        self.setDefault(True)

class CourseButton(QPushButton):
    def __init__(self):
        super().__init__()

        self.setIcon(os.path.join(ASSETS_BASEDIR, "course.svg"))

class ResourseButton(QPushButton):
    def __init__(self):
        super().__init__()

        self.setIcon(os.path.join(ASSETS_BASEDIR, "resource.svg"))

class rollcallButton(QPushButton):
    def __init__(self):
        super().__init__()

        self.setIcon(os.path.join(ASSETS_BASEDIR, "rollcall.svg"))

class Sidebar(QWidget):
    def __init__(self):
        super().__init__()

