# Learning_at_ZJU_third_client

<div align="center">
  <img src="./images/LOGO.png" width="300">
</div>

## 项目简介

学在浙大第三方客户端，项目名为**LAZY**，即 Learning at ZJU yes! 的缩写，期望这个项目可以帮助你获得更好学在浙大使用体验！

当前项目计划实现 CLI 与 GUI 两个客户端，当前 CLI 版本将以包形式分发，GUI 已新建文件夹。

## FAQ

如果你在使用与安装中遇到了某些问题，可以先在项目Issue里找找是否已经有了解决办法，当然你也可以查看[FAQ](https://github.com/YangShu233-Snow/Learning_at_ZJU_third_client/blob/main/FAQ.md)，这里面有一些比较常见的问题。

## LAZY CLI

以下均为 LAZY CLI 安装指南。

### Pre-built Binaries

LAZY CLI 预构建好的二进制文件现已发布！[点击这里](https://github.com/YangShu233-Snow/Learning_at_ZJU_third_client/releases)获取最新版本！

使用预构建的二进制文件安装是最方便，也是最推荐的安装 LAZY 的方式！

```bash
# 下载文件至本地后将其解压，这里仅以 Linux 举例
# Windows 用户推荐使用直观好用的资源管理器找到你的文件，并用压缩软件把.zip文件解压出来。
wget https://github.com/YangShu233-Snow/Learning_at_ZJU_third_client/releases/download/v0.1.0-beta.5/lazy-cli-linux.tar.gz
tar -zxvf ./lazy-cli-linux.tar.gz

# 在当前目录下会有一个 lazy 文件夹
# MacOS 与 Linux 用户可以通过软链接或环境变量的方式来配置
# 将 lazy 文件夹移动至一个永久存放的位置，我们推荐~/.local/share
mkdir ~/.local/share -p
mv /path/to/your/lazy ~/.local/share/

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

### Development Setup

以下步骤适用于 Run from Source 和 Build Executable 两种方式。

```bash
# 克隆本仓库
git clone https://github.com/YangShu233-Snow/Learning_at_ZJU_third_client
cd Learning_at_ZJU_third_client/

# 创建虚拟环境（二选一）
python -m venv .venv         # venv
source .venv/bin/activate     # Linux/macOS
# .venv\Scripts\activate      # Windows

conda create -n LAZY python=3.12.3  # Conda
conda activate LAZY

# 安装 LAZY（开发模式）
pip install -e '.[dev]'
```

### Run from Source

完成 Development Setup 后，直接调用 LAZY 命令即可（无需打包）：

```bash
# （可选）启用命令补全
lazy --install-completion

# 验证
lazy --help
```

> 每次使用前需激活对应的 Python 虚拟环境（`.venv` 或 conda）。

### Build Executable

After completing Development Setup, use PyInstaller to build a standalone executable.

```bash
# Generate lazy.spec
pyinstaller --name lazy src/lazy/__main__.py --noconfirm
# Single-file mode (slower startup)
pyinstaller --onefile --name lazy src/lazy/__main__.py --noconfirm
```

Modify `lazy.spec` to configure `data_files` and `platform_hiddenimports`,
see [docs/PACKAGING.md](docs/PACKAGING.md) for details.

```bash
# Build with modified lazy.spec
pyinstaller lazy.spec --noconfirm
```

Output: `dist/lazy/`. Install it the same way as Pre-built Binaries (symlink or PATH).

## LAZY SERVER

学在浙大服务端代理，提供多用户后台监控、数据缓存和 HTTP API。
适合与 QQ Bot 等外部系统集成。

```bash
# 安装服务端依赖
pip install -e '.[server]'

# 启动（详见部署指南）
lazy-server
```

### API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| `POST` | `/api/auth/register` | 注册新用户 |
| `POST` | `/api/auth/login` | 登录获取 token |
| `GET` | `/api/health` | 服务健康检查 |
| `GET` | `/api/tasks` | 查看监控任务 |
| `PUT` | `/api/tasks/{id}` | 修改任务参数 |
| `DELETE` | `/api/tasks/{id}` | 重置任务为系统模板 |
| `GET` | `/api/data/{task_id}` | 获取缓存数据 |

### 部署

参见 [docs/DEPLOY.md](docs/DEPLOY.md)（支持 systemd 服务 和 Docker 两种部署方式）。

### 安全说明

LAZY SERVER 使用 `~/.lazy_server/master.key` 存储 Fernet 加密主密钥（`chmod 600`），
用于加密 `~/.lazy_server/credentials.enc` 中的用户凭据。

如服务器被入侵，攻击者可解密所有凭据，请做好主机安全防护。
如需更高安全等级，可通过环境变量 `LAZY_SERVER_KEY` 传入主密钥（每次重启需重新提供）。

## License

- **GUI + CLI + Core** (`CLI/`, `core/`, `GUI/`): **GNU Lesser General Public License v3.0** (LGPL-3.0-only)
- **Server** (`server/`): **GNU Affero General Public License v3.0** (AGPL-3.0-only)
- **文档**（`README.md`、注释与使用说明等）: [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)，需注明原作者 `YangShu233-Snow`。

## Todo

- ~~实现assignment、course命令组~~
- ~~zjuAPI重构，整合与封装~~
- GUI实现
- ~~完善 CLI Help 文档~~
- 计划另外分发API模块
- ~~研究 CI/CD (Github Action)~~
- 开发 LAZY SERVER 与配套 QQBot Plugin
