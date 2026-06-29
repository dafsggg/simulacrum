"""轻量 API 服务：联网拉取最新赛果/赔率 → 生成预测数据 → 返回 JSON。

运行方式（无窗口）：
    pythonw api_server.py

前端点"更新预测"时 fetch 以下端点：
    GET  /api/latest   → 返回当前缓存数据（秒回）
    POST /api/refresh  → 联网同步 + 重新计算 + 返回最新数据（耗时 10~60 秒）
"""

from __future__ import annotations

import json
import multiprocessing
import os
import socketserver
import sys
import threading
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

if getattr(sys, "frozen", False):
    multiprocessing.freeze_support()
    try:
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
    except Exception:
        pass

    import subprocess
    _orig_Popen = subprocess.Popen
    def _patched_Popen(*args, **kwargs):
        flags = kwargs.pop("creationflags", 0)
        flags |= 0x08000000
        kwargs["creationflags"] = flags
        return _orig_Popen(*args, **kwargs)
    subprocess.Popen = _patched_Popen
    multiprocessing.context.subprocess.Popen = _patched_Popen
    try:
        import multiprocessing.popen_spawn_posix
    except ImportError:
        pass
    try:
        import multiprocessing.popen_spawn_win32
        multiprocessing.popen_spawn_win32.subprocess.Popen = _patched_Popen
    except ImportError:
        pass

ROOT = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))

USER_ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else ROOT
DATA_FILE = USER_ROOT / "web" / "data.js"
LOG_FILE = USER_ROOT / "api_server.log"
PORT = 8084
HOST = "127.0.0.1"


def _early_log(msg: str) -> None:
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg + "\n")
    except Exception:
        pass


# ── 尝试导入依赖，失败时写日志 ──────────────────────────────────────
try:
    from src import fetch, odds, report
    from src.model import match_probabilities, score_grid
    from src.state import build_state
    from src.update import build_schedule, write_outputs
except Exception as e:
    _early_log(f"导入失败: {e}\n{traceback.format_exc()}")
    sys.exit(1)

# 全局刷新锁，防止并发刷新
_refresh_lock = threading.Lock()
_is_refreshing = False
_last_error = None
_debug_log = []


def _log(msg: str) -> None:
    """写日志到文件和内存缓冲。"""
    global _debug_log
    ts = time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg
    _debug_log.append(ts)
    if len(_debug_log) > 100:
        _debug_log = _debug_log[-100:]
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(ts + "\n")
    except Exception:
        pass


def _load_current_data() -> dict | None:
    """从 web/data.js 加载当前数据，无则返回 None。"""
    if not DATA_FILE.exists():
        return None
    try:
        text = DATA_FILE.read_text(encoding="utf-8")
        if text.startswith("window.WC_DATA = "):
            json_str = text[len("window.WC_DATA = "):].rstrip(";\n ")
        else:
            json_str = text
        return json.loads(json_str)
    except Exception:
        return None


def _do_refresh() -> dict:
    """执行完整刷新：联网同步 → 模拟 → 生成数据 → 写入文件。"""
    from src.update import run as run_update
    return run_update(
        sims=300_000,      # 30万次模拟（速度与精度平衡）
        seed=int(time.strftime("%Y%m%d")),
        do_fetch=True,     # 联网拉取最新赛果和赔率
        workers=None,      # 自动使用所有CPU核心（多进程并行）
        refresh_all=False, # 只刷新最近 10 场
    )


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, msg: str, status: int = 400):
        self._send_json({"error": msg}, status)

    def do_GET(self):
        if self.path == "/api/latest":
            data = _load_current_data()
            if data:
                self._send_json(data)
            else:
                self._error("暂无缓存数据，请先 POST /api/refresh", 404)
        elif self.path == "/api/status":
            self._send_json({
                "refreshing": _is_refreshing,
                "error": _last_error,
                "debug_log": _debug_log[-20:],
            })
        else:
            self._error("未知路径", 404)

    def do_OPTIONS(self):
        """处理 CORS 预检请求（浏览器在 POST 前自动发送）。"""
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_POST(self):
        global _is_refreshing

        if self.path != "/api/refresh":
            self._error("未知路径", 404)
            return

        # 检查是否正在刷新
        if _is_refreshing:
            self._error("刷新进行中，请稍后重试", 409)
            return

        # 后台执行刷新
        def bg():
            global _is_refreshing, _last_error
            with _refresh_lock:
                _is_refreshing = True
            _log("开始刷新...")
            try:
                result = _do_refresh()
                _log(f"刷新完成: {result['meta']['updated_at']}")
                _last_error = None
            except Exception as e:
                err_msg = f"刷新失败: {e}\n{traceback.format_exc()}"
                _log(err_msg)
                _last_error = str(e)
            finally:
                with _refresh_lock:
                    _is_refreshing = False

        # 立即返回 202 Accepted，前端可轮询 /api/status
        body = b'{"status": "refreshing"}'
        self.send_response(202)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

        # 后台线程执行实际刷新
        t = threading.Thread(target=bg, daemon=True)
        t.start()

    def log_message(self, fmt, *args):
        # 静默，不往 stderr 写东西（pythonw 会吞掉 stderr 但保险起见）
        pass


class _ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _main():
    try:
        server = _ThreadedHTTPServer((HOST, PORT), _Handler)
        _log(f"启动于 http://{HOST}:{PORT}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
    except Exception as e:
        _log(f"启动失败: {e}\n{traceback.format_exc()}")
        raise


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _main()
