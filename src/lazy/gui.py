from .printlog.print_log import setup_global_logging
from .GUI.GUI import app


def main():
    setup_global_logging()
    app.launch()


if __name__ == "__main__":
    main()
