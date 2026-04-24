from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .MainContent import MainContent
from .Sidebar import Sidebar
from .TopBar import TopBar


class SubWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        self.topbar = TopBar()
        self.maincontent = MainContent()

        layout = QVBoxLayout()
        layout.addWidget(self.topbar)
        layout.addWidget(self.maincontent)

        self.setLayout(layout)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("LAZY GUI")

        self.sidebar = Sidebar()
        self.subwidget = SubWidget()

        main_layout = QHBoxLayout()
        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.subwidget)
        self.setLayout(main_layout)