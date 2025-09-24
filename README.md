# Learning_at_ZJU_third_client

*Not lazy, laz yes!*

学在浙大第三方客户端，争取实现绝大部分网页端功能，并且获得比网页端更加流畅的体验。

当前项目计划实现 CLI 与 GUI 两个客户端，当前正在开发 CLI 版本。

## Installation

### 直接从源码运行

LAZY 支持直接从项目源码开始运行，你可以按照如下步骤进行操作。

```bash
# 进入LAZY根目录
cd Learning_at_ZJU_third_client/

# 建立虚拟环境，可选，但是强烈推荐
python -m venv .venv
source .venv/bin/activate

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