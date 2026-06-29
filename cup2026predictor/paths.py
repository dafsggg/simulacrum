"""路径工具：统一处理 PyInstaller 打包后和开发环境下的路径。

打包后（onefile 模式）：
- 程序资源（web/、src/）在 sys._MEIPASS（临时解压目录，只读）
- 用户数据（data/、knowledge/、log文件）在 exe 同目录

开发环境：
- 所有文件都在项目根目录
"""

from __future__ import annotations

import sys
from pathlib import Path


def get_app_root() -> Path:
    """获取程序资源根目录（只读，包含web/、src/等打包进去的资源）。"""
    if getattr(sys, "frozen", False):
        # onefile 模式: 资源在 sys._MEIPASS 临时目录
        # onedir 模式: 资源在 exe 同目录的 _internal 子目录
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        # onedir 模式
        internal = Path(sys.executable).parent / "_internal"
        if internal.exists():
            return internal
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


def get_user_root() -> Path:
    """获取用户数据根目录（可写，存放data/、knowledge/、日志等）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


APP_ROOT = get_app_root()
USER_ROOT = get_user_root()
IS_FROZEN = getattr(sys, "frozen", False)
