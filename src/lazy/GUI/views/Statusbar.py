import os

from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSpacerItem, QToolButton, QWidget


class UserAvater(QImage):
    def __init__(self):
        avater_path = self._check_avater()
        
        super().__init__(avater_path)
    
    def _check_avater(self)->str:
        user_avater_path = "../assets/avater.jpg"
        default_avater_path = "../assets/default_avater.jpg"
        if os.path.exists(user_avater_path):
            return user_avater_path
        
        return default_avater_path

class StatusBar(QWidget):
    def __init__(self):
        super().__init__()

        # 用户头像
        self.user_avater_label = QLabel()
        self.user_avater_pixmap = QPixmap(UserAvater())
        self.user_avater_label.setPixmap(self.user_avater_pixmap)

        # 明暗主题
        self.light_or_dark_mode_button = QToolButton()
        self.light_mode = QPixmap("../assets/light_mode.svg")
        self.light_mode_icon = QIcon(self.light_mode)
        self.light_or_dark_mode_button.setIcon(self.light_mode_icon)

        layout = QHBoxLayout()
        layout.addWidget(self.user_avater_label)
        layout.addWidget(QSpacerItem())
        layout.addWidget(self.light_or_dark_mode_button)

        self.setLayout(layout)