# Learning_at_ZJU_third_client

*Not lazy, laz yes!*

学在浙大第三方客户端，争取实现绝大部分网页端功能，并且获得比网页端更加流畅的体验。

当前项目计划实现 CLI 与 GUI 两个客户端，当前 CLI 版本将以包形式分发，GUI 已新建文件夹。

## Installation CLI

以下均为 LAZY CLI 安装指南。

### 预构建的二进制文件

LAZY CLI 预构建好的二进制文件现已发布！[点击这里](https://github.com/YangShu233-Snow/Learning_at_ZJU_third_client/releases)获取最新版本！

使用预构建的二进制文件安装是最方便，也是最推荐的安装 LAZY 的方式！

```bash
# 下载文件至本地后将其解压，这里仅以 Linux 举例
# Windows 用户推荐使用直观好用的资源管理器找到你的文件，并用压缩软件把.zip文件解压出来。
wget https://github.com/YangShu233-Snow/Learning_at_ZJU_third_client/releases/download/v0.1.0-beta.5/lazy-cli-linux.tar.gz
tar tar -zxvf ./lazy-cli-linux.tar.gz

# 在当前目录下会有一个 lazy 文件夹
# MacOS 与 Linux 用户可以通过软链接或环境变量的方式来配置
# 将 lazy 文件夹移动至一个永久存放的位置，我们推荐~/.local/share
mkdir ~/.local/share/lazy -p
mv /path/to/your/Learning_at_ZJU_third_client/dist/lazy/* ~/.local/share/lazy

# 创建一个软链接
sudo ln -s ~/.local/share/lazy/lazy /usr/local/bin/lazy

# 如果你更喜欢环境变量，可以参考以下指引
# 添加至环境变量
# Linux & MacOS
echo 'export PATH="/path/to/your/Learning_at_ZJU_third_client/dist/lazy:$PATH"' >> ~/.bashrc # 如果你用的是bash
echo 'export PATH="/path/to/your/Learning_at_ZJU_third_client/dist/lazy:$PATH"' >> ~/.zshrc # 如果你用的是zsh

source ~/.bashrc # 应用修改
source ~/.zshrc  # 应用修改
```

对于 Windows 用户来说，在解压软件包后，我们更推荐你将 LAZY 添加至环境变量当中。通过设置-高级设置-环境变量-系统-Path，加入 LAZY 可执行文件所在文件夹的路径即可。

完成以上修改后，你的 LAZY 应该就正确安装到系统当中了。

```bash
# 验证是否安装
lazy --help

# （可选）为 LAZY 配置补全
lazy --install-completion
```

### Arch Linux (AUR)

> 感谢社区贡献者 [@Gvrzizo](https://github.com/Gvrzizo)，LAZY CLI 现已登陆 [Arch User Repository (AUR)](https://aur.archlinux.org/)！

Arch Linux 及其衍生版的用户，现在可以通过你喜欢的 AUR 助手（如 `yay` 或 `paru`）一键安装 LAZY CLI：

```bash
# 如果你使用 yay
yay -S lazy-cli

# 如果你使用 paru
paru -S lazy-cli
```

该包 `lazy-cli` 会自动安装 LAZY CLI 最新的 `beta` 版预编译二进制文件~

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
# 接下来开始打包 LAZY，请确保你在 LAZY 项目根目录下，首先pyinstaller会分析 LAZY 项目。
pyinstaller --name lazy src/lazy_cli_main.py --noconfirm
# 使用单文件模式可以将 LAZY 打包为单个可执行文件，但是会带来不可避免的启动延迟。
pyinstaller --onefile --name lazy src/lazy_cli_main.py --noconfirm
```

接下来你需要修改 LAZY 项目根目录下生成的 `lazy.spec`，具体的需求可见下方。

```
# -*- mode: python ; coding: utf-8 -*-

# --- 内容请新增在文件开头 ---
import os
import glob
import sys

data_files=[]
for f in glob.glob('data/*'):
    if os.path.isfile(f):
        data_files.append((f, 'data'))

platform_hiddenimports = []
if sys.platform.startswith('linux'):
    platform_hiddenimports = [
        'keyring.backends.SecretService',
        'keyring.backends.chainer',
        'shellingham.posix',
    ]
elif sys.platform.startswith('darwin'): # macOS
    platform_hiddenimports = [
        'keyring.backends.macOS.Keyring',
        'shellingham.posix',
    ]
elif sys.platform.startswith('win32'): # Windows
    platform_hiddenimports = [
        'keyring.backends.Windows.WinVaultKeyring',
        'shellingham.windows',
	    'shellingham.nt'
    ]
# --- 内容请新增在文件开头 ---

a = Analysis(
    ['src/lazy_cli_main.py'],
    pathex=[],
    binaries=[],
    datas=data_files, # <--这里请将变量赋值为 data_files
    # ....
    hiddenimports=platform_hiddenimports, # <--这里请将变量赋值为platform_hiddenimports
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
```

打包成功后，我们推荐你进行进一步的配置，以享受最好的使用体验。

如果你是 MacOS/Linux 用户，并且使用的单文件模式打包的 LAZY，可以直接将 `lazy`可执行文件移动至 `/usr/local/bin`下。如果你使用文件夹模式打包的 LAZY，可以通过软链接的方式方便 LAZY 的调用（通常这也是我们所推荐的方式），当然使用环境变量也是一个可行的方案。

```bash
# 如果你采用文件夹模式打包，可以参考以下指引
# 将打包后的 LAZY 文件夹移动至一个永久存放的位置，我们推荐~/.local/share
mkdir ~/.local/share/lazy -p
mv /path/to/your/Learning_at_ZJU_third_client/dist/lazy/* ~/.local/share/lazy

# 创建一个软链接
sudo ln -s ~/.local/share/lazy/lazy /usr/local/bin/lazy

# 如果你更喜欢环境变量，可以参考以下指引
# 添加至环境变量
# Linux & MacOS
echo 'export PATH="/path/to/your/Learning_at_ZJU_third_client/dist/lazy:$PATH"' >> ~/.bashrc # 如果你用的是bash
echo 'export PATH="/path/to/your/Learning_at_ZJU_third_client/dist/lazy:$PATH"' >> ~/.zshrc # 如果你用的是zsh

source ~/.bashrc # 应用修改
source ~/.zshrc  # 应用修改
```

对于 Windows 用户来说，我们更推荐你将 LAZY 添加至环境变量当中。通过设置-高级设置-环境变量-系统-Path，加入 LAZY 可执行文件所在文件夹的路径即可。

完成以上修改后，你的 LAZY 应该就正确安装到系统当中了。

```bash
# 验证是否安装
lazy --help

# （可选）为 LAZY 配置补全
lazy --install-completion
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

- ~~实现assignment、course命令组~~
- ~~zjuAPI重构，整合与封装~~
- GUI实现
- 完善 CLI Help 文档
- 计划另外分发API模块
- ~~研究 CI/CD (Github Action)~~
