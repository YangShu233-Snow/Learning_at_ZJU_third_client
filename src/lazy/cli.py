import logging
import httpx
import keyring
import traceback
import sys

import keyring.errors
from rich import print as rprint

from .CLI.CLI import app
from .core.printlog.print_log import setup_global_logging


def main():
    setup_global_logging()
    _logger = logging.getLogger(__name__)

    # 一些兜底
    try:
        app()
    
    except httpx.TimeoutException as e:
        _logger.error(f"Connection Timeout! Detailed: {e}")
        rprint("[yellow]学在浙大服务器连接超时！[/yellow]")
        sys.exit(1)

    except httpx.NetworkError as e:
        _logger.error(f"Network Error! Detailed: {e}")
        rprint("[yellow]无法访问学在浙大！网络设置坏了喵？学在浙大崩了喵？[/yellow]")
        sys.exit(1)

    except httpx.HTTPError as e:
        _logger.error(f"HTTPError occurs! Detailed: {e}")
        rprint("[yellow]未知的网络错误发生了！[/yellow]")

    except keyring.errors.NoKeyringError as e:
        _logger.error(f"Not recommended backends for keyring! Detailed: {e}")
        rprint("[yellow]缺乏推荐的 Keyring 后端，请检查当前环境下是否存在系统 Keyring 服务！[/yellow]")
        rprint("[dim]WSLers look at this: https://github.com/jaraco/keyring/issues/566[/dim]")
        sys.exit(1)

    except Exception as e:
        _logger.error(f"Something Exception occurs!!! Detailed: {e}")
        _logger.info('\n'.join(traceback.format_stack()))
        rprint("[red]一个意外问题发生在了 LAZY CLI 中！请随日志报告给开发者！[/red]")
        rprint("日志路径: ~/.lazy_cli_logs/")
        sys.exit(1)

    return

if __name__ == "__main__":
    main()
