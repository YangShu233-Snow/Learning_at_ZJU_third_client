# PyInstaller 打包指南

LAZY CLI 支持通过 PyInstaller 打包为独立可执行文件。

## 生成 spec 文件

```bash
pyinstaller --name lazy src/lazy/__main__.py --noconfirm
```

项目根目录下的 `lazy.spec` 是由 PyInstaller 生成的配置文件，后续打包均依赖此文件。

## 修改 lazy.spec

生成的 `lazy.spec` 需要额外配置 `data_files` 和 `hiddenimports`，否则打包后的程序无法正常运行。

在 `lazy.spec` 的**文件开头**（`a = Analysis(` 之前）添加以下内容：

```python
import os
import glob
import sys

data_files = []
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
elif sys.platform.startswith('darwin'):  # macOS
    platform_hiddenimports = [
        'keyring.backends.macOS.Keyring',
        'shellingham.posix',
    ]
elif sys.platform.startswith('win32'):  # Windows
    platform_hiddenimports = [
        'keyring.backends.Windows.WinVaultKeyring',
        'shellingham.windows',
        'shellingham.nt',
    ]
```

然后将 `a = Analysis(` 中的对应参数替换：

```python
a = Analysis(
    ['src/lazy_cli_main.py'],
    pathex=[],
    binaries=[],
    datas=data_files,               # ← 替换为 data_files
    hiddenimports=platform_hiddenimports,  # ← 替换为 platform_hiddenimports
    # ... 其余参数保持不变
)
```

## 最终打包

```bash
pyinstaller lazy.spec --noconfirm
```

打包好的文件位于 `dist/lazy/`。

## 验证

```bash
cd ./dist/lazy
./lazy --help
```

## 安装打包后的程序

打包成功后，将 `dist/lazy/` 目录移至永久位置，并通过软链接或环境变量配置 PATH。详见 README.md 中「预构建的二进制文件」的安装后配置步骤。
