# Learning_at_ZJU_third_client

*Not lazy, laz yes!*

学在浙大第三方客户端，争取实现绝大部分网页端功能，并且获得比网页端更加流畅的体验。

当前项目计划实现 CLI 与 GUI 两个客户端，当前正在开发 CLI 版本。

## Installation

### 从源码开始打包

LAZY 支持从项目源码打包为一个可执行文件，通常这能使得 LAZY 的启动速度得到提升，同时如果你想对 LAZY 做一些个性的修改，这个安装方法就是最适合你的。

```bash
# 克隆本仓库
git clone https://github.com/YangShu233-Snow/Learning_at_ZJU_third_client

# 进入LAZY根目录
cd Learning_at_ZJU_third_client/

# 建立虚拟环境，可选，但是强烈推荐
python -m venv .venv

# 在Linux/MacOS下
source .venv/bin/activate

# 在Windows下
.venv\Scripts\activate

# Conda也是非常推荐的选择
# Python版本>=3.8均可，但3.12.3是一个比较稳妥的版本，因为LAZY就是在这个版本下开发的
conda create -n LAZY python=3.12.3
conda activate LAZY

# 将LAZY挂载到当前Python环境下，同时下载必要的开发者依赖
pip install -e '.[dev]'

# 如果你想做一些修改再打包，完全没有问题，记得保存你的修改
# 接下来开始打包 LAZY，请确保你在 LAZY 项目根目录下
pyinstaller --name lazy src/Learning_at_ZJU_third_client/main_CLI.py
```

接下来你需要修改 LAZY 项目根目录下生成的 `lazy.spec`，具体的需求可见下方。

```
# -*- mode: python ; coding: utf-8 -*-

# --- 内容请新增在文件开头 ---
import os
import glob

data_files=[]
for f in glob.glob('data/*'):
    if os.path.isfile(f): # 只添加文件
        data_files.append((f, 'data'))
# --- 内容请新增在文件开头 ---

a = Analysis(
    ['src/Learning_at_ZJU_third_client/main_CLI.py'],
    pathex=[],
    binaries=[],
    datas=data_files, # <--这里请将变量赋值为 data_files
    # ....
    hookspath=[
        'keyring.backends.SecretService',          # 如果你在 Linux 下打包，请补充这个依赖
        'keyring.backends.chainer',                # 如果你在 Linux 下打包，请补充这个依赖
        'keyring.backends.macOS.Keyring'           # 如果你在 MacOS 下打包，请补充这个依赖
        'keyring.backends.Windows.WinVaultKeyring' # 如果你在 Windows 下打包，请补充这个依赖
    ],
    # ....
)
```

当你修改完 `lazy.spec`后，就可以进行进一步的打包了。

```bash
pyinstaller lazy.spec --noconfirm
```

打包好的文件在 `Learning_at_ZJU_third_client/dist/lazy` 下，是一个 `lazy` 名的可执行文件。

```bash
cd ./dist/lazy
./lazy --help

# 出现以下输出，说明LAZY安装成功
# Usage: lazy [OPTIONS] COMMAND [ARGS]...
# LAZY CLI - 学在浙大第三方客户端的命令行工具

# 安装补全
lazy --install-completion

# 添加至环境变量
# Linux & MacOS
echo 'export PATH="/path/to/your/Learning_at_ZJU_third_client/dist/lazy:$PATH"' >> ~/.bashrc # 如果你用的是bash
echo 'export PATH="/path/to/your/Learning_at_ZJU_third_client/dist/lazy:$PATH"' >>  ./zshrc # 如果你用的是zsh

source ~/.bashrc # 应用修改
source ~/.zshrc  # 应用修改

# Windows需要在系统高级设置-环境变量-系统Path-新增，加入以下路径
# /path/to/your/Learning_at_ZJU_third_client/dist/lazy
# 保存后请重启终端以应用修改！
```

### 直接从源码运行

LAZY 支持直接从项目源码开始运行，你可以按照如下步骤进行操作。

```bash
# 克隆本仓库
git clone https://github.com/YangShu233-Snow/Learning_at_ZJU_third_client

# 进入LAZY根目录
cd Learning_at_ZJU_third_client/

# 建立虚拟环境，可选，但是强烈推荐
python -m venv .venv

# 在Linux/MacOS下
source .venv/bin/activate

# 在Windows下
.venv\Scripts\activate

# Conda也是非常推荐的选择
# Python版本>=3.8均可，但3.12.3是一个比较稳妥的版本，因为LAZY就是在这个版本下开发的
conda create -n LAZY python=3.12.3
conda activate LAZY

# 将LAZY挂载到当前Python环境下
pip install -e .

# 可选，但是强烈推荐，这将为LAZY提供补全功能
lazy --install-completion
```

完成以上步骤后，**请重启终端**以应用修改，重启终端后，如果你想要使用LAZY，需要启用对应的Python环境。

```bash
# 使用一下命令，检查LAZY是否安装成功
lazy --help

# 出现以下输出，说明LAZY安装成功
# Usage: lazy [OPTIONS] COMMAND [ARGS]...
# LAZY CLI - 学在浙大第三方客户端的命令行工具
```

## Example Usage

## License

- 本项目源代码采用 **GNU Lesser General Public License v3.0**授权。
- 本项目文档（包含 `README.md` 、注释与使用说明等）均采用[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) 许可协议。你可以自由复制、修改与分享此文档，只需 **注明原作者 `YangShu233-Snow`** 和项目链接，即可用于个人或商业用途。

## Todo

- 实现assignment、course命令组
- zjuAPI重构，整合与封装
- GUI实现