from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from .views.Statusbar import StatusBar
from .views.Sidebar import Sidebar
from .views.MainContent import MainContent

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