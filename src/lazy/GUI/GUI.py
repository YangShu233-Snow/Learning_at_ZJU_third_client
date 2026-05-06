import sys

from PySide6.QtWidgets import QApplication

from .controllers.MainController import MainController
from .views.MainWindow import MainWindow


def app():
    lazy_app = QApplication(sys.argv)
    
    mainwindow = MainWindow()
    controller = MainController(mainwindow.sidebar, mainwindow.subwidget.maincontent)

    mainwindow.show()
    sys.exit(lazy_app.exec())