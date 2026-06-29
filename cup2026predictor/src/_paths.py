"""src 模块共用的路径配置。

PyInstaller 打包后：
- 用户数据（data/、knowledge/、web/data.js 等）在 exe 同目录（可写）
- 资源文件在 _internal 子目录（只读）
"""

from __future__ import annotations

import sys
from pathlib import Path


def _get_root() -> Path:
    """获取项目根目录（用户数据目录，可写）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


ROOT = _get_root()
