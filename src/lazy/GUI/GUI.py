from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .views.MainContent import MainContent
from .views.Sidebar import Sidebar
from .views.Statusbar import StatusBar


class SubWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout()
        
        layout.addWidget(Sidebar())
        layout.addWidget(MainContent())

        self.setLayout(layout)
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("LAZY GUI")

        main_layout = QVBoxLayout()
        main_layout.addWidget(StatusBar())
        main_layout.addWidget(SubWidget())
        self.setLayout(main_layout)