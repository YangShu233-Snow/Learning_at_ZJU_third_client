# 将版本号打包到源码中

import tomllib
from pathlib import Path

def builder():
    with open("pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
        version = pyproject["project"]["version"]

    Path("src/lazy/_version.py").write_text(f"__version__ = \"{version}\"\n")

if __name__ == "__main__":
    builder()