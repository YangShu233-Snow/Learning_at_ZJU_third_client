from .MainContent import MainContent
from .Sidebar import Sidebar
from .Statusbar import StatusBar
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout


class SubWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        self.sidebar = Sidebar()
        self.maincontent = MainContent()

        layout = QHBoxLayout()
        layout.addWidget(self.sidebar)
        layout.addWidget(self.maincontent)

        self.setLayout(layout)

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("LAZY GUI")

        self.statusbar = StatusBar()
        self.subwidget = SubWidget()

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.statusbar)
        main_layout.addWidget(self.subwidget)
        self.setLayout(main_layout)