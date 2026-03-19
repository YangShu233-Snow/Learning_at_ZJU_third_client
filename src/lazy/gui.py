import sys

from PySide6.QtWidgets import QApplication

from .GUI.GUI import MainWindow
from .printlog.print_log import setup_global_logging


def main():
    setup_global_logging()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
