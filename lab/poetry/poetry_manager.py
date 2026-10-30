from __future__ import annotations

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
import json
import os
import socket
import tempfile
import threading
import webbrowser

BASE = Path(__file__).resolve().parent
POETRY = BASE / "poetry.json"
INDEX = BASE / "index.html"
HOST = "127.0.0.1"
START_PORT = 8767


def validate_works(value):
    if not isinstance(value, list):
        raise ValueError("poetry.json 顶层必须是数组")
    for i, work in enumerate(value, 1):
        if not isinstance(work, dict):
            raise ValueError(f"第 {i} 条作品不是对象")
        if not str(work.get("title", "")).strip():
            raise ValueError(f"第 {i} 条作品缺少 title")
    return value


def read_poetry():
    if not POETRY.exists():
        raise FileNotFoundError("缺少 poetry.json")
    return validate_works(json.loads(POETRY.read_text(encoding="utf-8")))


def atomic_write_text(path: Path, text: str):
    """先写临时文件，再原子替换，减少保存中断导致 JSON 损坏的概率。"""
    fd, temp_name = tempfile.mkstemp(
        prefix=path.stem + "_", suffix=path.suffix, dir=str(path.parent)
    )
    os.close(fd)
    temp = Path(temp_name)
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink(missing_ok=True)


def write_poetry(works):
    """只保存 poetry.json；不生成 backup，也不修改 index.html。"""
    validate_works(works)
    text = json.dumps(works, ensure_ascii=False, indent=2)
    atomic_write_text(POETRY, text)


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[HTTP]", fmt % args)

    def end_headers(self):
        # 本地维护时总是读取当前文件，避免看到旧版 JSON/HTML。
        if self.path.endswith((".html", ".json", ".js", ".css", ".tsv")):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()

    def _json(self, obj, status=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if urlparse(self.path).path == "/api/status":
            try:
                works = read_poetry()
                return self._json(
                    {
                        "ok": True,
                        "app": "hongwu-poetry",
                        "file": "poetry.json",
                        "count": len(works),
                        "write_enabled": True,
                    }
                )
            except Exception as exc:
                return self._json({"ok": False, "error": str(exc)}, 500)
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/save_poetry":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = (
                    json.loads(self.rfile.read(length).decode("utf-8"))
                    if length
                    else {}
                )
                works = validate_works(
                    body.get("works") if isinstance(body, dict) else None
                )
                write_poetry(works)
                return self._json(
                    {
                        "ok": True,
                        "saved": len(works),
                        "file": "poetry.json",
                    }
                )
            except Exception as exc:
                return self._json({"error": str(exc)}, 400)

        return self._json({"error": "not found"}, 404)


def choose_port():
    with socket.socket() as sock:
        try:sock.bind((HOST,START_PORT))
        except OSError:raise RuntimeError("诗集维护端口 8767 已被占用，请关闭旧维护服务后重试")
    return START_PORT


def main():
    os.chdir(BASE)

    if not INDEX.exists():
        raise SystemExit("缺少 index.html")
    if not POETRY.exists():
        raise SystemExit("缺少 poetry.json")

    works = read_poetry()
    port = choose_port()
    url = f"http://{HOST}:{port}/index.html"
    server = ThreadingHTTPServer((HOST, port), Handler)

    print("=" * 62)
    print("鸿武集 · poetry.json 本地维护")
    print("目录：", BASE)
    print("地址：", url)
    print(f"作品：{len(works)} 篇")
    print("数据源：poetry.json（唯一正式作品数据）")
    print("保存逻辑：只写 poetry.json；不生成 backup，不修改 index.html")
    print("提示：直接双击 index.html 无法自动读取同目录 JSON，请使用本启动方式。")
    print("按 Ctrl+C 停止服务。")
    print("=" * 62)

    
    if os.environ.get('HONGWU_LAUNCHED_BY_HUB') != '1':
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
