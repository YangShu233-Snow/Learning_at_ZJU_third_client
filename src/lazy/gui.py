from .GUI.GUI import app
from .printlog.print_log import setup_global_logging


def main():
    setup_global_logging()
    app.launch()


if __name__ == "__main__":
    main()
