from PySide6.QtWidgets import QStackedWidget, QWidget, QHBoxLayout, QLabel, QVBoxLayout

class HomeContentWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("首页内容"))

class CourseContentWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("课程内容"))

class ResourceContentWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("资源内容"))

class RollcallContentWidget(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("点名内容"))


class MainContent(QWidget):
    def __init__(self):
        super().__init__()

        self.stackwidget = QStackedWidget()
        for widget in [
            HomeContentWidget(),
            CourseContentWidget(), 
            ResourceContentWidget(), 
            RollcallContentWidget()
        ]:
            self.stackwidget.addWidget(widget)

        layout = QVBoxLayout(self)
        layout.addWidget(self.stackwidget)