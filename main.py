import json
import os
import threading
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from downloader_core import DownloaderCore


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
INDEX_HTML = WEB_DIR / "index.html"
HOST = "127.0.0.1"
PORT = 5000


def android_private_download_dir() -> str | None:
    private_root = os.environ.get("ANDROID_PRIVATE", "").strip()
    if not private_root:
        return None
    return str(Path(private_root) / "downloads")


class AppState:
    def __init__(self):
        self._lock = threading.Lock()
        self.output_dir = android_private_download_dir() or DownloaderCore.default_output_dir()
        self.running = False
        self.status = "就绪"
        self.progress = 0.0
        self.logs = []
        self.result = {}
        self.error = ""
        self.mode = "full"
        self._log("服务已启动")

    def _log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{stamp}] {message}")
        self.logs = self.logs[-200:]

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "status": self.status,
                "progress": round(self.progress, 1),
                "logs": list(self.logs),
                "result": dict(self.result),
                "error": self.error,
                "output_dir": self.output_dir,
                "mode": self.mode,
            }

    def start(self, url: str, mode: str) -> tuple[bool, str]:
        with self._lock:
            if self.running:
                return False, "已有任务在运行"
            self.running = True
            self.status = "准备中..."
            self.progress = 0.0
            self.error = ""
            self.result = {}
            self.mode = mode
            self.logs = []
            self._log("开始任务")
        worker = threading.Thread(target=self._worker, args=(url, mode), daemon=True)
        worker.start()
        return True, ""

    def _worker(self, url: str, mode: str) -> None:
        outdir = android_private_download_dir() or self.output_dir
        core = DownloaderCore(outdir=outdir)
        self._set_output_dir(core.outdir)

        try:
            result = core.run(url, mode, self._on_progress)
            with self._lock:
                self.running = False
                self.progress = 100.0
                self.status = "完成"
                self.result = result
                self.output_dir = core.outdir
                self._log("任务完成")
                for key, value in result.items():
                    self._log(f"{key}: {value}")
        except Exception as exc:
            with self._lock:
                self.running = False
                self.status = "失败"
                self.error = str(exc)
                self._log(f"错误: {exc}")

    def _set_output_dir(self, outdir: str) -> None:
        with self._lock:
            self.output_dir = outdir

    def _on_progress(self, evt_type: str, data: dict) -> None:
        with self._lock:
            if evt_type == "thumbnail_progress":
                self.progress = float(data.get("percent", 0.0))
                downloaded = data.get("downloaded", 0) // 1024
                total = max(1, data.get("total", 0) // 1024)
                self.status = f"封面下载 {downloaded}K/{total}K"
                return

            if evt_type == "thumbnail_done":
                self.progress = 100.0
                self.status = "封面下载完成"
                self._log(f"封面已保存: {data.get('path')}")
                return

            if evt_type != "yt":
                return

            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                downloaded = data.get("downloaded_bytes", 0)
                if total:
                    self.progress = downloaded / total * 100
                    self.status = f"下载中 {self.progress:.1f}%"
                else:
                    self.status = f"下载中 {downloaded // 1024**2}MB"
                return

            if status == "finished":
                self.status = "下载完成，正在收尾..."


STATE = AppState()


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = urlparse(self.path).path
        if route == "/":
            self._serve_file(INDEX_HTML, "text/html; charset=utf-8")
            return
        if route == "/api/status":
            self._send_json(STATE.snapshot())
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self):
        route = urlparse(self.path).path
        if route != "/api/start":
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json({"ok": False, "error": "请求格式错误"}, status=HTTPStatus.BAD_REQUEST)
            return

        url = str(payload.get("url", "")).strip()
        mode = str(payload.get("mode", "full")).strip()
        if not url:
            self._send_json({"ok": False, "error": "请输入 YouTube 链接"}, status=HTTPStatus.BAD_REQUEST)
            return
        if mode not in {"full", "thumbnail", "audio"}:
            self._send_json({"ok": False, "error": "未知模式"}, status=HTTPStatus.BAD_REQUEST)
            return

        ok, error = STATE.start(url, mode)
        if not ok:
            self._send_json({"ok": False, "error": error}, status=HTTPStatus.CONFLICT)
            return
        self._send_json({"ok": True})

    def log_message(self, format, *args):
        return

    def _serve_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    if not DownloaderCore.is_android_runtime():
        webbrowser.open(f"http://{HOST}:{PORT}/")
    server = ThreadingHTTPServer((HOST, PORT), RequestHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
