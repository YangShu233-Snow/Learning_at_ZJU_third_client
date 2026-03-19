from PySide6.QtWidgets import QStackedWidget, QWidget

class MainContent(QWidget):
    def __init__(self):
        super().__init__()

        self.stackwidget = QStackedWidget()