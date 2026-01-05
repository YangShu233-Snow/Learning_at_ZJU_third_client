from .printlog.print_log import setup_global_logging
from .CLI.CLI import app


def main():
    setup_global_logging()
    app()


if __name__ == "__main__":
    main()
