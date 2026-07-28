
__all__ = ["PROJECT_ROOT", "WRITE_ROOT", "USER_DATA_DIR", "HAS_TK"]

"""
San7ModMaker 全局配置常量
由 main.py 和 routes/ 共同导入，避免循环依赖

- PROJECT_ROOT: 项目根目录（开发模式 = 源码目录，打包后 = sys._MEIPASS 只读）
- WRITE_ROOT:   可写根目录（打包后 = exe 所在目录）
- USER_DATA_DIR: 用户配置目录（打包后 = %APPDATA%/San7ModMaker）
- HAS_TK:       tkinter 是否可用
"""

import os
import sys

# tkinter 仅在桌面端需要（文件对话框），无GUI环境跳过
try:
    import tkinter as tk  # noqa: F401
    from tkinter import filedialog  # noqa: F401
    HAS_TK = True
except ImportError:
    HAS_TK = False


# 项目根目录
# PyInstaller 打包后:
#   PROJECT_ROOT = sys._MEIPASS (只读，存放打包的资源文件：data/ web/ core/)
#   WRITE_ROOT   = exe所在目录 (可写，存放用户数据：mods/ exports/ sandbox/ backup/)
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = sys._MEIPASS
    WRITE_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    WRITE_ROOT = PROJECT_ROOT

sys.path.insert(0, PROJECT_ROOT)


def _get_user_data_dir():
    """获取用户配置目录"""
    if getattr(sys, 'frozen', False):
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        data_dir = os.path.join(base, 'San7ModMaker')
    else:
        data_dir = PROJECT_ROOT
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


USER_DATA_DIR = _get_user_data_dir()