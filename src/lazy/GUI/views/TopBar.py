from pathlib import Path

from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QToolButton, QWidget

from .utils.get_round_icon import get_round_icon

CURRENT_DIR = Path(__file__).parent
ASSETS_BASEDIR = CURRENT_DIR / ".." / "assets" / "TopBar"

class TopSearchBox(QWidget):
    def __init__(self):
        super().__init__()

        self.line_editor = QLineEdit()
        self.line_editor.setPlaceholderText("搜索资源、课程等等……")

        self.search_action = QAction(QIcon(QPixmap(ASSETS_BASEDIR / "search.svg")), "搜索", self)
        self.line_editor.addAction(self.search_action, QLineEdit.ActionPosition.LeadingPosition)

        layout = QHBoxLayout(self)
        layout.addWidget(self.line_editor)

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

class TopBar(QWidget):
    def __init__(self):
        super().__init__()

        self.top_search_box = TopSearchBox()

        # 明暗主题
        self.light_or_dark_mode_button = QToolButton()
        self.light_mode = QPixmap(ASSETS_BASEDIR / "light_mode.svg")
        self.light_mode_icon = QIcon(self.light_mode)
        self.light_or_dark_mode_button.setIcon(self.light_mode_icon)
        self.light_or_dark_mode_button.setAutoRaise(True)

        layout = QHBoxLayout()
        layout.addWidget(self.top_search_box)
        layout.addStretch()
        layout.addWidget(self.light_or_dark_mode_button)

        self.setLayout(layout)