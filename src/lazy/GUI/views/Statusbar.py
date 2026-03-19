from pathlib import Path

from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSpacerItem, QToolButton, QWidget

from .utils.get_round_icon import get_round_icon

CURRENT_DIR = Path(__file__).parent
ASSETS_BASEDIR = CURRENT_DIR / ".." / "assets" / "Statusbar"

class UserAvater(QLabel):
    def __init__(self):
        super().__init__()
        avater_path = self._check_avater()
        avater = QPixmap(avater_path)
        if not avater.isNull():
            round_pixmap = get_round_icon(avater, 80)
            self.setPixmap(round_pixmap)

        self.setFixedSize(80, 80)
        
    
    def _check_avater(self)->Path:
        user_avater_path = ASSETS_BASEDIR / "avater.jpg"
        default_avater_path = ASSETS_BASEDIR / "default_avater.jpg"
        if user_avater_path.exists():
            return user_avater_path
        
        return default_avater_path

class StatusBar(QWidget):
    def __init__(self):
        super().__init__()

        # 用户头像
        self.user_avater_label = UserAvater()

        # 明暗主题
        self.light_or_dark_mode_button = QToolButton()
        self.light_mode = QPixmap(ASSETS_BASEDIR / "light_mode.svg")
        self.light_mode_icon = QIcon(self.light_mode)
        self.light_or_dark_mode_button.setIcon(self.light_mode_icon)
        self.light_or_dark_mode_button.setAutoRaise(True)

        layout = QHBoxLayout()
        layout.addWidget(self.user_avater_label)
        layout.addStretch()
        layout.addWidget(self.light_or_dark_mode_button)

        self.setLayout(layout)