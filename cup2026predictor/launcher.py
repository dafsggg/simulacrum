"""世界杯预测系统 - 一体化启动器。

单进程、单端口（8080），同时提供静态页面和API服务。
PyInstaller 打包后无黑窗口、无弹窗。
"""
from __future__ import annotations

import multiprocessing
import os
import sys
import time
import threading
import webbrowser
import traceback
import json
import socket
from pathlib import Path

from paths import APP_ROOT, USER_ROOT, IS_FROZEN

LOG_FILE = USER_ROOT / "launcher.log"


def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg + "\n")
    except Exception:
        pass


if IS_FROZEN:
    multiprocessing.freeze_support()
    import subprocess as _sp_sub
    _orig_sp = _sp_sub.Popen
    def _patched_sp(*args, **kwargs):
        flags = kwargs.pop("creationflags", 0)
        flags |= 0x08000000
        kwargs["creationflags"] = flags
        return _orig_sp(*args, **kwargs)
    _sp_sub.Popen = _patched_sp


def init_user_data():
    """首次运行时，将打包进EXE的用户数据复制到exe同目录。"""
    if not IS_FROZEN:
        return

    marker = USER_ROOT / ".initialized"
    if marker.exists():
        return

    log("首次运行，初始化用户数据...")
    import shutil

    dirs_to_copy = ["data", "knowledge"]
    for d in dirs_to_copy:
        src = APP_ROOT / d
        dst = USER_ROOT / d
        if src.exists():
            try:
                if src.is_dir():
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    dst.mkdir(parents=True, exist_ok=True)
                log(f"  复制 {d}/ 完成")
            except Exception as e:
                log(f"  复制 {d}/ 失败: {e}")

    web_dst = USER_ROOT / "web"
    web_src = APP_ROOT / "web"
    if web_src.exists():
        web_dst.mkdir(parents=True, exist_ok=True)
        dynamic_files = [
            "data.js", "reports.js", "blurbs.js",
            "teams.json", "calibration.json", "predictor-data.js",
        ]
        for fname in dynamic_files:
            src = web_src / fname
            dst = web_dst / fname
            if src.exists():
                try:
                    shutil.copy2(src, dst)
                    log(f"  复制 web/{fname} 完成")
                except Exception as e:
                    log(f"  复制 web/{fname} 失败: {e}")

    try:
        marker.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
        log("用户数据初始化完成")
    except Exception as e:
        log(f"写入初始化标记失败: {e}")


def build_server():
    """构建集成了静态文件服务和API的HTTP服务器。"""
    import http.server
    import socketserver

    APP_WEB = APP_ROOT / "web"
    USER_WEB = USER_ROOT / "web"
    DATA_FILE = USER_WEB / "data.js"

    DYNAMIC_FILES = {
        "data.js", "reports.js", "blurbs.js",
        "teams.json", "calibration.json", "predictor-data.js",
    }

    sys.path.insert(0, str(APP_ROOT))

    from src import fetch, odds, report
    from src.update import run as run_update

    _refresh_lock = threading.Lock()
    _is_refreshing = False
    _last_error = None
    _debug_log = []

    def _api_log(msg: str) -> None:
        nonlocal _debug_log
        ts = time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg
        _debug_log.append(ts)
        if len(_debug_log) > 100:
            _debug_log = _debug_log[-100:]
        log(f"[API] {msg}")

    def _load_current_data():
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

    def _do_refresh():
        _api_log("开始刷新...")
        worker_count = 1 if IS_FROZEN else max(1, multiprocessing.cpu_count() - 1)
        
        def update_task():
            _api_log(f"步骤1: run_update 开始, workers={worker_count}")
            result = run_update(
                sims=300_000,
                seed=None,
                do_fetch=True,
                workers=worker_count,
                refresh_all=False,
            )
            _api_log("步骤2: run_update 完成")
            return result
        
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(update_task)
            try:
                result = future.result(timeout=600)
                _api_log(f"刷新完成")
                return result
            except concurrent.futures.TimeoutError:
                _api_log("刷新超时（10分钟），已强制终止")
                raise TimeoutError("刷新超时")
            except Exception as e:
                _api_log(f"刷新过程中出错: {e}")
                raise

    class UnifiedHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(APP_WEB), **kwargs)

        def translate_path(self, path):
            path = path.lstrip("/")
            if "?" in path:
                path = path.split("?", 1)[0]
            if "#" in path:
                path = path.split("#", 1)[0]

            if path.startswith("api/"):
                return ""

            filename = os.path.basename(path)

            if filename in DYNAMIC_FILES:
                user_file = USER_WEB / path
                if user_file.exists() and user_file.is_file():
                    return str(user_file)

            app_file = APP_WEB / path
            if app_file.exists() and app_file.is_file():
                return str(app_file)

            user_file = USER_WEB / path
            if user_file.exists() and user_file.is_file():
                return str(user_file)

            return str(APP_WEB / path)

        def end_headers(self):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            super().end_headers()

        def log_message(self, fmt, *args):
            pass

        def _send_json(self, obj, status=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            if self.path.startswith("/api/"):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
            else:
                self.send_error(404)

        def do_GET(self):
            if self.path == "/api/status":
                self._send_json({
                    "refreshing": _is_refreshing,
                    "error": _last_error,
                    "debug_log": _debug_log[-20:],
                })
                return
            if self.path == "/api/latest":
                data = _load_current_data()
                if data:
                    self._send_json({"ok": True, "data": data})
                else:
                    self._send_json({"ok": False, "error": "no data yet"}, status=404)
                return
            if self.path.startswith("/api/"):
                self._send_json({"error": "not found"}, status=404)
                return
            super().do_GET()

        def do_POST(self):
            nonlocal _is_refreshing, _last_error
            if self.path == "/api/refresh":
                with _refresh_lock:
                    if _is_refreshing:
                        self._send_json({"ok": False, "error": "already refreshing"}, status=409)
                        return
                    _is_refreshing = True
                    _last_error = None

                def worker():
                    nonlocal _is_refreshing, _last_error
                    try:
                        _do_refresh()
                    except Exception as e:
                        _last_error = str(e)
                        _api_log(f"刷新失败: {e}\n{traceback.format_exc()}")
                    finally:
                        _is_refreshing = False

                threading.Thread(target=worker, daemon=True).start()
                self._send_json({"ok": True, "started": True})
                return
            if self.path.startswith("/api/"):
                self._send_json({"error": "not found"}, status=404)
                return
            self.send_error(405)

    class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
        allow_reuse_address = True

    server = ThreadedServer(("", 8080), UnifiedHandler)
    _api_log("服务启动于 http://127.0.0.1:8080")
    return server


def main():
    log(f"启动器开始运行, frozen={IS_FROZEN}")
    log(f"APP_ROOT={APP_ROOT}")
    log(f"USER_ROOT={USER_ROOT}")

    init_user_data()

    def port_open(port):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            return False

    if port_open(8080):
        log("服务已在运行，直接打开浏览器")
        try:
            webbrowser.open("http://localhost:8080/zh/index.html")
        except Exception:
            pass
        return

    server = build_server()

    def run_server():
        try:
            server.serve_forever()
        except Exception as e:
            log(f"服务器错误: {e}")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    log("服务器线程已启动")

    deadline = time.time() + 20
    ready = False
    while time.time() < deadline:
        if port_open(8080):
            ready = True
            log("服务就绪")
            break
        time.sleep(0.3)

    if ready:
        try:
            webbrowser.open("http://localhost:8080/zh/index.html")
            log("浏览器已打开")
        except Exception as e:
            log(f"打开浏览器失败: {e}")

    while True:
        time.sleep(5)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        main()
    except Exception as e:
        log(f"致命错误: {e}\n{traceback.format_exc()}")
