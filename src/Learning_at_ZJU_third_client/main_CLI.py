import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from Learning_at_ZJU_third_client.CLI.CLI import app

if __name__ == "__main__":
    app()