# 常见问题参考

如果你的问题在这里找不到解决方案，可以前往项目 Issue 提出你的问题！不过请确保这个问题在以前的 Issue 中未曾出现或还未完全解决，并在提出 Issue 时 **附带你的操作系统版本**，**LAZY CLI的版本**，**通过什么方式安装的LAZY CLI** 与完整报错内容。

## 使用过程中

### Keyring 缺失 recommended backends on WSL2

LAZY CLI 通过 `keyring` 调用系统密钥服务，其本质是一个抽象层，需要系统提供相应的接口才能调用对应服务。

而在 WSL2 中，其往往缺乏必要的凭据管理器服务接口，导致你在运行 LAZY CLI 时出现相应的报错：

> ModuleNotFoundError: No module named 'shellingham.posix'

我更加推荐为 `keyring` 提供一个系统级的密钥服务，如果你选择 `keyring` 在报错中的提示，安装了 `keyring.alt`，实际上只是使用了一个本地简易的加密服务。

对此你可以通过包管理器补全 `gnome-keyring` 与 `dbus-x11`：

```sh
$ sudo apt update && sudo apt install gnome-keyring dbus-x11
```