"""Web 服务器启动脚本（用 pythonw 静默运行）。

支持双目录查找：
- 静态资源（HTML/JS/CSS/图片）优先从 APP_ROOT/web（打包进EXE的只读资源）
- 动态数据（data.js、reports.js、blurbs.js 等）优先从 USER_ROOT/web（用户目录，可更新）
"""
import http.server
import socketserver
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))

USER_ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else ROOT
LOG_FILE = USER_ROOT / "web_server.log"

def log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg + "\n")
    except Exception:
        pass

APP_WEB = ROOT / "web"
USER_WEB = USER_ROOT / "web"

PORT = 8080

DYNAMIC_FILES = {
    "data.js", "reports.js", "blurbs.js",
    "teams.json", "calibration.json", "predictor-data.js",
}

class DualRootHandler(http.server.SimpleHTTPRequestHandler):
    def translate_path(self, path):
        path = path.lstrip("/")
        if "?" in path:
            path = path.split("?", 1)[0]
        if "#" in path:
            path = path.split("#", 1)[0]

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

class ThreadedServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

try:
    log(f"APP_WEB={APP_WEB}")
    log(f"USER_WEB={USER_WEB}")
    httpd = ThreadedServer(("", PORT), DualRootHandler)
    log(f"启动于 http://127.0.0.1:{PORT}")
    httpd.serve_forever()
except Exception as e:
    log(f"启动失败: {e}\n{traceback.format_exc()}")
