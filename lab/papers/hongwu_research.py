from __future__ import annotations

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote_plus
from urllib.request import Request, urlopen
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser

PAPERS = Path(__file__).resolve().parent
ROOT = PAPERS.parent
DATA = PAPERS / "data"
PUBLICATIONS = ROOT.parent / "docs" / "Publications"

def paper_files():
    primary = sorted(PUBLICATIONS.glob("*.pdf"))
    import hashlib
    hashes = {hashlib.sha256(x.read_bytes()).digest() for x in primary}
    return primary + [x for x in sorted(DATA.glob("*.pdf")) if hashlib.sha256(x.read_bytes()).digest() not in hashes]

def paper_rel(path):
    return "../../docs/Publications/" + path.name if path.parent == PUBLICATIONS else "data/" + path.name
LIBRARY = PAPERS / "library.json"
TRASH = PAPERS / ".trash"
ALLOWED = {".pdf"}
DOC_TYPES = {"journal_article", "conference_paper", "survey_report", "project_proposal", "competition_entry", "other"}
EDITABLE = {
    "title", "authors", "year", "month", "venue", "venue_short", "volume_issue_pages",
    "doi", "publication_status", "research_area", "research_question", "methods",
    "data_sample", "findings", "conclusion", "keywords", "outline", "notes",
    "research_group", "venue_type", "document_type", "abstract"
}


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json_atomic(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def read_lib() -> dict:
    doc = read_json(LIBRARY, {})
    if not isinstance(doc, dict):
        doc = {"items": doc if isinstance(doc, list) else []}
    doc.setdefault("schema_version", 3)
    doc.setdefault("mode", "manual-first")
    doc.setdefault("supported_formats", ["pdf"])
    doc.setdefault("document_types", ["journal_article", "conference_paper", "survey_report", "project_proposal", "competition_entry", "other"])
    doc.setdefault("venues", {})
    doc.setdefault("items", [])
    doc["total"] = len(doc["items"])
    return doc


def stable_id(rel: str) -> str:
    return "pdf-" + hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]


def safe_name(name: str) -> str:
    name = Path(str(name or "")).name.strip()
    name = re.sub(r"[\x00-\x1f]", "", name)
    if not name:
        raise ValueError("文件名为空")
    if Path(name).suffix.lower() != ".pdf":
        raise ValueError("当前版本仅支持 PDF")
    return name


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def file_state(path: Path) -> dict:
    st = path.stat()
    return {
        "size": st.st_size,
        "modified": dt.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
    }


def infer_year(name: str):
    m = re.search(r"(?:^|\D)((?:19|20)\d{2})(?:\D|$)", name)
    return int(m.group(1)) if m else ""


def skeleton_for(path: Path) -> dict:
    rel = paper_rel(path)
    state = file_state(path)
    title = re.sub(r"^(?:19|20)\d{2}(?:[-_. ]\d{1,2})?[-_. ]*", "", path.stem).strip()
    return {
        "id": stable_id(rel), "file": rel, "name": path.name, "ext": "pdf",
        **state, "title": title, "authors": [], "authors_text": "", "year": infer_year(path.name), "month": "",
        "document_type": "other", "publication_status": "unpublished", "venue": "", "venue_short": "", "venue_type": "none",
        "research_group": "待人工核对", "research_area": "待人工核对", "keywords": [], "methods": [],
        "abstract": "", "research_question": "", "data_sample": "", "findings": "", "outline": [],
        "review": {"status": "待人工核对"}
    }


def scan_changes() -> dict:
    """只比较：是否为新 PDF + 文件修改时间。绝不自动解析正文或覆盖科研元数据。"""
    DATA.mkdir(exist_ok=True)
    doc = read_lib()
    by_file = {str(x.get("file", "")): x for x in doc.get("items", [])}
    changes = []
    for path in paper_files():
        rel = paper_rel(path)
        state = file_state(path)
        old = by_file.get(rel)
        if old is None:
            changes.append({"kind": "new", "label": "新增 PDF", "file": rel, "name": path.name, "modified": state["modified"], "item": skeleton_for(path)})
        elif str(old.get("modified", "")) != state["modified"]:
            candidate = dict(old)
            candidate.update(state)
            changes.append({"kind": "modified", "label": "修改时间已变化", "file": rel, "name": path.name,
                            "old_modified": old.get("modified", ""), "modified": state["modified"], "item": candidate})
    return {"ok": True, "changes": changes, "count": len(changes), "checked": len(paper_files())}


def clean_patch(patch: dict) -> dict:
    out = {k: v for k, v in (patch or {}).items() if k in EDITABLE}
    if "document_type" in out and out["document_type"] not in DOC_TYPES:
        out["document_type"] = "other"
    if "authors" in out:
        if isinstance(out["authors"], str):
            out["authors"] = [x.strip() for x in re.split(r"[;；]", out["authors"]) if x.strip()]
        elif not isinstance(out["authors"], list):
            out["authors"] = []
    for k in ("keywords", "methods", "outline"):
        if k in out and isinstance(out[k], str):
            out[k] = [x.strip() for x in re.split(r"[;；\n]", out[k]) if x.strip()]
    return out


def save_review(file_rel: str, patch: dict) -> dict:
    if not file_rel.startswith(("data/", "../../docs/Publications/")):
        raise ValueError("文件路径不安全")
    path = (PAPERS / file_rel).resolve()
    if not any(folder.resolve() == path.parent for folder in (DATA, PUBLICATIONS)) or not path.exists() or path.suffix.lower() != ".pdf":
        raise ValueError("PDF 文件不存在")
    doc = read_lib()
    target = next((x for x in doc["items"] if str(x.get("file")) == file_rel), None)
    if target is None:
        target = skeleton_for(path)
        doc["items"].append(target)
    target.update(clean_patch(patch))
    target.update(file_state(path))
    target["sha256"] = sha256(path)
    target["id"] = target.get("id") or stable_id(file_rel)
    target["file"] = file_rel
    target["name"] = path.name
    target["ext"] = "pdf"
    target["authors_text"] = "; ".join(target.get("authors") or [])
    target["review"] = {"status": "人工核对", "reviewed_at": now_iso(), "basis": "人工确认后写入"}
    doc["generated_at"] = now_iso()
    doc["total"] = len(doc["items"])
    write_json_atomic(LIBRARY, doc)
    return target


def save_metadata(item_id: str, patch: dict) -> dict:
    doc = read_lib()
    target = next((x for x in doc["items"] if str(x.get("id")) == item_id), None)
    if target is None:
        raise KeyError("未找到成果")
    target.update(clean_patch(patch))
    target["authors_text"] = "; ".join(target.get("authors") or [])
    target["review"] = {"status": "人工核对", "reviewed_at": now_iso(), "basis": "页面编辑"}
    doc["generated_at"] = now_iso()
    write_json_atomic(LIBRARY, doc)
    return target


def venue_key(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def get_venue_meta(name: str, refresh=False) -> dict:
    doc = read_lib()
    venues = doc.setdefault("venues", {})
    meta = venues.get(name)
    if meta is None:
        nk = venue_key(name)
        for k, v in venues.items():
            kk = venue_key(k)
            if nk == kk or nk in kk or kk in nk:
                meta = v
                name = k
                break
    meta = dict(meta or {"name": name, "type": "journal", "indexing": [], "quartile": "待人工核验"})
    if refresh:
        # 只补充 OpenAlex 可安全获得的基础字段，不自动改写 SCI/JCR 分区等人工核验字段。
        try:
            q = quote_plus(name)
            req = Request(f"https://api.openalex.org/sources?search={q}&per-page=5", headers={"User-Agent": "HongwuResearch/2.5"})
            with urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode("utf-8"))
            results = data.get("results") or []
            if results:
                best = results[0]
                meta.setdefault("issn", best.get("issn") or [])
                if best.get("homepage_url"):
                    meta.setdefault("homepage", best.get("homepage_url"))
                meta["openalex_id"] = best.get("id", "")
                meta["openalex_works_count"] = best.get("works_count")
                meta["openalex_cited_by_count"] = best.get("cited_by_count")
                meta["refreshed_at"] = now_iso()
        except Exception as e:
            meta["refresh_note"] = f"OpenAlex 基础信息刷新失败：{e}"
        venues[name] = meta
        doc["generated_at"] = now_iso()
        write_json_atomic(LIBRARY, doc)
    return meta


class Handler(SimpleHTTPRequestHandler):
    server_version = "HongwuResearch/2.5"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT.parent), **kwargs)

    def translate_path(self, path):
        if path.startswith("/papers/"): path = "/lab" + path
        return super().translate_path(path)

    def log_message(self, fmt, *args):
        print("[HTTP]", fmt % args)

    def json_out(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def body(self):
        n = int(self.headers.get("Content-Length", "0") or 0)
        return self.rfile.read(n)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/api/research/status":
            return self.json_out({"ok": True, "app": "hongwu-research", "version": "2.5", "mode": "manual-first",
                                  "papers": str(PAPERS), "data": str(DATA), "library": str(LIBRARY), "supported_formats": ["pdf"]})
        if u.path == "/api/research/library":
            return self.json_out(read_lib())
        if u.path == "/api/research/scan-changes":
            return self.json_out(scan_changes())
        if u.path == "/api/research/venue-meta":
            q = parse_qs(u.query)
            name = str((q.get("name") or [""])[0]).strip()
            refresh = str((q.get("refresh") or ["0"])[0]).lower() in {"1", "true", "yes"}
            if not name:
                return self.json_out({"ok": False, "error": "缺少期刊/会议名称"}, 400)
            return self.json_out({"ok": True, "venue": get_venue_meta(name, refresh=refresh)})
        if u.path == "/api/research/open-data":
            try:
                DATA.mkdir(exist_ok=True)
                if os.name == "nt":
                    os.startfile(DATA)  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(DATA)])
                else:
                    subprocess.Popen(["xdg-open", str(DATA)])
                return self.json_out({"ok": True})
            except Exception as e:
                return self.json_out({"ok": False, "error": str(e)}, 500)
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        try:
            if u.path == "/api/research/upload":
                name = safe_name((q.get("name") or [""])[0])
                DATA.mkdir(exist_ok=True)
                dest = DATA / name
                if dest.exists():
                    stem, suffix, i = dest.stem, dest.suffix, 2
                    while dest.exists():
                        dest = DATA / f"{stem} ({i}){suffix}"
                        i += 1
                dest.write_bytes(self.body())
                return self.json_out({"ok": True, "file": "data/" + dest.name, "name": dest.name, "change": skeleton_for(dest)})

            if u.path == "/api/research/review-save":
                payload = json.loads(self.body() or b"{}")
                target = save_review(str(payload.get("file", "")), payload.get("patch") or {})
                return self.json_out({"ok": True, "item": target})

            if u.path == "/api/research/favorite":
                payload = json.loads(self.body() or b"{}")
                doc = read_lib()
                target = next((x for x in doc["items"] if str(x.get("id")) == str(payload.get("id"))), None)
                if target is None:
                    return self.json_out({"ok": False, "error": "未找到成果"}, 404)
                target["favorite"] = bool(payload.get("active"))
                target["favorite_at"] = now_iso() if target["favorite"] else ""
                write_json_atomic(LIBRARY, doc)
                return self.json_out({"ok": True, "item": target})

            if u.path == "/api/research/save-metadata":
                payload = json.loads(self.body() or b"{}")
                target = save_metadata(str(payload.get("id", "")), payload.get("patch") or {})
                return self.json_out({"ok": True, "item": target})

            if u.path == "/api/research/analyze":
                # 兼容旧按钮：不再自动分析，只返回变化清单。
                return self.json_out(scan_changes())

            if u.path == "/api/research/delete":
                payload = json.loads(self.body() or b"{}")
                item_id = str(payload.get("id", ""))
                doc = read_lib()
                target = next((x for x in doc["items"] if str(x.get("id")) == item_id), None)
                if target is None:
                    return self.json_out({"ok": False, "error": "未找到成果"}, 404)
                rel = str(target.get("file", ""))
                path = (PAPERS / rel).resolve()
                if DATA.resolve() not in path.parents:
                    return self.json_out({"ok": False, "error": "文件路径不安全"}, 400)
                moved = ""
                if path.exists():
                    TRASH.mkdir(exist_ok=True)
                    dest = TRASH / path.name
                    if dest.exists():
                        dest = TRASH / f"{int(time.time())}_{path.name}"
                    shutil.move(str(path), str(dest))
                    moved = str(dest)
                doc["items"] = [x for x in doc["items"] if str(x.get("id")) != item_id]
                doc["total"] = len(doc["items"])
                doc["generated_at"] = now_iso()
                write_json_atomic(LIBRARY, doc)
                return self.json_out({"ok": True, "moved_to": moved})

            return self.json_out({"ok": False, "error": "unknown endpoint"}, 404)
        except KeyError as e:
            return self.json_out({"ok": False, "error": str(e)}, 404)
        except Exception as e:
            return self.json_out({"ok": False, "error": str(e)}, 500)


def serve(port=8766, no_browser=False):
    DATA.mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    research_url = f"http://127.0.0.1:{port}/lab/papers/index.html?maintain=1"
    print("=" * 58)
    print(" 鸿武研究 · 本地维护 V2.5（PDF / 人工核对优先）")
    print(" 页面:", research_url)
    print(" data:", DATA)
    print(" 启动时不会自动改写 library.json")
    print(" Ctrl+C 退出")
    print("=" * 58)
    if not no_browser:
        
        if os.environ.get('HONGWU_LAUNCHED_BY_HUB') != '1':
            threading.Timer(.7, lambda: webbrowser.open(research_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="鸿武研究：PDF 目录检测 + 人工核对维护")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--scan-only", action="store_true", help="只检测新增/修改时间变化，不写 library.json")
    args = parser.parse_args()
    if args.scan_only:
        print(json.dumps(scan_changes(), ensure_ascii=False, indent=2))
        return
    serve(args.port, args.no_browser)


if __name__ == "__main__":
    main()
