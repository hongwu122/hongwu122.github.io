# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import time
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SHELF = ROOT.parent / "asset" / "local-data" / "lab_shelves.json"
HOST, PORT = "127.0.0.1", 8768
HUB_ORIGINS = {
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    f"http://127.0.0.1:{PORT}",
    f"http://localhost:{PORT}",
}


def load_json(path: Path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


class H(SimpleHTTPRequestHandler):
    def _cors(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin in HUB_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def end_headers(self):
        self._cors()
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def reply(self, obj, status=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/__travel/status":
            return self.reply({"ok": True, "service": "travel", "port": PORT})
        if parsed.path == "/api/shelf/travel":
            from urllib.parse import parse_qs
            title = ((parse_qs(parsed.query).get("title") or [""])[0]).strip()
            shelf = load_json(SHELF, {})
            active = any(str(x.get("title") or "").strip()==title for x in shelf.get("go_again", [])) if isinstance(shelf, dict) else False
            return self.reply({"ok": True, "active": active})
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/api/shelf/travel":
                title = str(body.get("title") or "").strip()
                if not title: raise ValueError("地点为空")
                shelf = load_json(SHELF, {})
                if not isinstance(shelf, dict): shelf = {}
                rows = shelf.setdefault("go_again", [])
                old = next((x for x in rows if str(x.get("title") or "").strip()==title), None)
                if old:
                    rows[:] = [x for x in rows if str(x.get("title") or "").strip()!=title]; active=False
                else:
                    rows.insert(0,{"title":title,"meta":body.get("meta","再访清单"),"url":body.get("url","")}); active=True
                shelf["updated"] = time.strftime("%Y-%m-%d")
                write_json_atomic(SHELF, shelf)
                return self.reply({"ok":True,"active":active})
            if path != "/__travel/save":
                return self.reply({"ok": False, "message": "Unknown endpoint"}, 404)
            routes = body.get("routes")
            style = body.get("style")
            if not isinstance(routes, dict) or not isinstance(routes.get("routes"), list):
                raise ValueError("routes 数据格式不正确")
            if not isinstance(style, dict):
                raise ValueError("style 数据格式不正确")

            write_json_atomic(DATA / "travel_routes_config_hongwu.json", routes)
            write_json_atomic(DATA / "user_style_config_hongwu.json", style)
            print(f"[SAVE] {len(routes.get('routes', []))} routes", flush=True)
            return self.reply({"ok": True, "routes": len(routes.get("routes", []))})
        except Exception as exc:
            print("[ERROR]", exc, flush=True)
            return self.reply({"ok": False, "message": str(exc)}, 400)

    def log_message(self, fmt, *args):
        path = getattr(self, "path", "")
        if path.startswith("/__travel/"):
            print("[TRAVEL] " + (fmt % args), flush=True)


if __name__ == "__main__":
    os.chdir(ROOT)
    url = f"http://{HOST}:{PORT}/"
    print("=" * 58)
    print(" 山海行藏 · LOCAL 自动维护")
    print("=" * 58)
    print("URL :", url)
    print("DATA:", DATA)
    print("说明：通过根目录 local_hub.py 启动时不会额外弹浏览器页面。")
    print("=" * 58, flush=True)

    # 手工双击本目录 BAT 时仍自动打开；由总控后台拉起时不额外开标签页。
    if os.environ.get("HONGWU_LAUNCHED_BY_HUB") != "1":
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        ThreadingHTTPServer((HOST, PORT), H).serve_forever()
    except KeyboardInterrupt:
        pass
