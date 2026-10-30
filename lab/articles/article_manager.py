#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hongwu Article Manager V7.0
==================================

V6 core parser inherited from v5
-------------
1) Saves plain text to `content` and text+image order to `content_md`.
2) Downloads inline article images to `images/<date_title_shortid>/001.jpg...`.
3) Saves `images`, `image_dir`, and `media_version` for local reader rendering.
2) Readable local cover names:
   ./covers/YYYY/YYYY-MM-DD_文章标题_shortid.jpg
3) Existing legacy random-token cover names are replaced when an article is revisited.
4) Existing remote cover URLs are revisited by default (unless --no-cover-download)
   so they can be localized into covers/.
5) Faster serial mode:
   - 1 request at a time
   - only main HTML is loaded
   - 2.5-5.5s between articles
   - 30-60s rest every 25 articles
   - stop immediately on verification / 403 / 429
6) Category/collection handling:
   - category prefers the EXACT WeChat collection/directory name from source HTML.
   - class prefers the exact title series before ｜.
   - category_source/class_source record where those values came from.
   - location is extracted independently from category.
7) Supports checkpoints and in-place output safely via temp-file replace.

Fields
------
title, date, category, class, location, summary, content, cover, url,
author, account, source_url, album_url
"""

import argparse
import json
import random
import re
import sys
import time
import os
import threading
import webbrowser
from datetime import datetime
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from collections import deque

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing beautifulsoup4. Run: python -m pip install beautifulsoup4")
    sys.exit(2)

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    sync_playwright = None
    PlaywrightTimeoutError = Exception
    PLAYWRIGHT_AVAILABLE = False

STRING_FIELDS = [
    "title","date","category","class","location","summary","content","content_md","cover","url",
    "author","account","source_url","album_url",
    "category_source","class_source","collection_titles","image_dir","media_version"
]

VERIFY_WORDS = [
    "访问过于频繁","操作频繁","环境异常","请完成验证","安全验证",
    "访问异常","系统繁忙","请在微信客户端打开链接","频率限制",
    "当前环境异常","请先完成验证"
]

GEO_HINTS = [
    "安徽","江苏","浙江","河南","河北","湖南","湖北","广东","广西","福建","江西","山东","山西","陕西",
    "四川","云南","贵州","海南","辽宁","吉林","黑龙江","甘肃","青海","宁夏","新疆","西藏","内蒙古",
    "北京","上海","天津","重庆","香港","澳门","台湾","日本","韩国","菲律宾","新加坡","马来西亚",
    "泰国","越南","印度尼西亚","巴林","埃及","阿联酋","卡塔尔","沙特","土耳其","欧洲","美洲",
    "澳洲","中东","东南亚","国内","海外"
]

PLACE_HINTS = [
    "北京","上海","广州","深圳","杭州","南京","苏州","成都","重庆","武汉","长沙","衡阳","韶山","西安",
    "洛阳","开封","郑州","周口","登封","汕尾","陆丰","厦门","泉州","福州","桂林","南宁","昆明","大理",
    "丽江","三亚","海口","哈尔滨","沈阳","青岛","济南","天津","合肥","蚌埠","黄山","芜湖","安庆","亳州",
    "宿州","淮南","淮北","香港","澳门","台北","巴林","麦纳麦","Manama","开罗","Cairo","马尼拉","Manila",
    "东京","Tokyo","京都","Kyoto","大阪","Osaka","奈良","名古屋","富士吉田","新加坡","Singapore","曼谷",
    "Bangkok","吉隆坡","Kuala Lumpur","迪拜","Dubai","阿布扎比","Abu Dhabi","多哈","Doha"
]

def clean(s):
    s = re.sub(r"[\u200B-\u200D\uFEFF]", "", s or "")
    return re.sub(r"\s+", " ", s).strip()

def norm_record(x):
    x = x or {}
    out = {k: str(x.get(k, "") or "").strip() for k in STRING_FIELDS}
    imgs = x.get("images", [])
    out["images"] = list(imgs) if isinstance(imgs, list) else []
    return out

def load_json(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("articles.json top-level value must be an array")
    return [norm_record(x) for x in data]

def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def save_state(path, state):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def complete(x):
    # media_version=5 means the article has been revisited by the image-aware crawler.
    return bool(
        x.get("title") and x.get("date") and x.get("category") and
        x.get("summary") and x.get("content") and x.get("cover") and
        x.get("media_version") == "5"
    )

def needs_update(x, download_cover=True, download_images=True, refresh=False):
    if refresh:
        return True
    if not x.get("category_source"):
        return True
    if not complete(x):
        return True
    if download_cover and x.get("cover","").startswith(("http://","https://")):
        return True
    if download_images and any(str(v).startswith(("http://","https://")) for v in x.get("images", [])):
        return True
    return False

def decode_js(s):
    if not s:
        return ""
    s = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1),16)), s)
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1),16)), s)
    s = s.replace("\\/","/").replace("\\n","\n").replace("\\r","\r").replace("\\t","\t")
    s = s.replace("\\'","'").replace('\\"','"').replace("\\\\","\\")
    return s

def js_value(raw, key):
    # object-style: key: '...' or key: "..."
    patterns = [
        rf"\b{re.escape(key)}\s*:\s*'((?:\\.|[^'])*)'",
        rf'\b{re.escape(key)}\s*:\s*"((?:\\.|[^"])*)"',
    ]
    for pat in patterns:
        m = re.search(pat, raw, re.S)
        if m:
            return clean(decode_js(m.group(1)))
    return ""

def var_value(raw, key):
    patterns = [
        rf"\b(?:var|let|const)\s+{re.escape(key)}\s*=\s*'((?:\\.|[^'])*)'",
        rf'\b(?:var|let|const)\s+{re.escape(key)}\s*=\s*"((?:\\.|[^"])*)"',
    ]
    for pat in patterns:
        m = re.search(pat, raw, re.S)
        if m:
            return clean(decode_js(m.group(1)))
    return ""


def visibleish(value):
    return bool(re.sub(r"[\s\u200B-\u200D\uFEFF]", "", str(value or "")))


def js_values(raw, key):
    """
    Return every non-empty JS/string value we can find for a field.

    WeChat has several page families. Older graphic articles usually expose
    `content_noencode` near create_time/cdn_url, while video/share pages may
    expose the useful value later inside `video_page_info` or through variables
    such as `videoContentNoEncode`.
    """
    pats = [
        rf"\b{re.escape(key)}\s*:\s*'((?:\\.|[^'])*)'",
        rf'\b{re.escape(key)}\s*:\s*"((?:\\.|[^"])*)"',
        rf"\b(?:var|let|const)\s+{re.escape(key)}\s*=\s*'((?:\\.|[^'])*)'",
        rf'\b(?:var|let|const)\s+{re.escape(key)}\s*=\s*"((?:\\.|[^"])*)"',
        # e.g. var videoContentNoEncode = window.a_value_which_never_exists || '...';
        rf"\b(?:var|let|const)\s+{re.escape(key)}\s*=\s*[^;\n]*?\|\|\s*'((?:\\.|[^'])*)'",
        rf'\b(?:var|let|const)\s+{re.escape(key)}\s*=\s*[^;\n]*?\|\|\s*"((?:\\.|[^"])*)"',
        rf"\bwindow\.{re.escape(key)}\s*=\s*'((?:\\.|[^'])*)'",
        rf'\bwindow\.{re.escape(key)}\s*=\s*"((?:\\.|[^"])*)"',
    ]
    out = []
    seen = set()
    for pat in pats:
        for m in re.finditer(pat, raw, re.S):
            v = clean(decode_js(m.group(1)))
            if v and v not in seen:
                seen.add(v)
                out.append(v)
    return out


def extract_content_candidate(value):
    """
    Parse a possible WeChat content string. It may be raw text or an escaped
    HTML fragment. Return the same tuple format as extract_body_with_images().
    """
    value = decode_js(value or "")
    if not visibleish(value):
        return "", "", []
    frag = BeautifulSoup(value, "html.parser")
    plain, template, imgs = extract_body_with_images(frag)
    if plain or imgs:
        return plain, template, imgs
    v = value.strip()
    return (v, v, []) if visibleish(v) else ("", "", [])


def best_content_from_js(raw):
    """
    Redundant content extraction for WeChat alternate page formats.

    Multiple occurrences are considered because a page can contain an early
    empty content_noencode and a later non-empty video_page_info version.
    """
    keys = (
        "content_noencode",
        "videoContentNoEncode",
        "TextContentNoEncode",
        "ContentNoEncode",
        "content_html",
        "contentHtml",
    )
    candidates = []
    for key in keys:
        for value in js_values(raw, key):
            parsed = extract_content_candidate(value)
            score = len(parsed[0]) + 80 * len(parsed[2])
            if score:
                candidates.append((score, parsed))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]
    return "", "", []

def extract_wechat_collections(raw):
    """
    Extract exact WeChat collection/directory names from source HTML.

    Sources:
    - appmsgalbuminfo: title/link
    - public_tag_info: tag_name/tag_link
    """
    out = []

    def add(title, link, source):
        title = clean(decode_js(title or ""))
        link = clean(decode_js(link or ""))
        if not title:
            return
        if any(x["title"] == title for x in out):
            return
        out.append({"title": title, "link": link, "source": source})

    for m in re.finditer(r"\bappmsgalbuminfo\b", raw):
        frag = raw[m.start():m.start()+8000]
        mt = re.search(r"\btitle\s*:\s*'((?:\\.|[^'])*)'", frag, re.S)
        if not mt:
            mt = re.search(r'\btitle\s*:\s*"((?:\\.|[^"])*)"', frag, re.S)
        ml = re.search(r"\blink\s*:\s*'((?:\\.|[^'])*)'", frag, re.S)
        if not ml:
            ml = re.search(r'\blink\s*:\s*"((?:\\.|[^"])*)"', frag, re.S)
        if mt:
            add(mt.group(1), ml.group(1) if ml else "", "appmsgalbuminfo")

    for m in re.finditer(r"\bpublic_tag_info\b", raw):
        frag = raw[m.start():m.start()+8000]
        mt = re.search(r"\btag_name\s*:\s*'((?:\\.|[^'])*)'", frag, re.S)
        if not mt:
            mt = re.search(r'\btag_name\s*:\s*"((?:\\.|[^"])*)"', frag, re.S)
        ml = re.search(r"\btag_link\s*:\s*'((?:\\.|[^'])*)'", frag, re.S)
        if not ml:
            ml = re.search(r'\btag_link\s*:\s*"((?:\\.|[^"])*)"', frag, re.S)
        if mt:
            add(mt.group(1), ml.group(1) if ml else "", "public_tag_info")

    return out

def title_series(title):
    """Return the exact title prefix before ｜ or |."""
    m = re.match(r"^\s*([^｜|]{2,20})[｜|]", title or "")
    return clean(m.group(1)) if m else ""

def is_geo_class(cls):
    if not cls:
        return False
    if any(g in cls for g in GEO_HINTS):
        return True
    if cls.endswith("篇") and len(cls) <= 8:
        return True
    return False

def infer_title_series(title, official_class=""):
    return title_series(title)

def classify_fallback(title, summary, content):
    """
    Used only when WeChat source contains no collection/directory.
    """
    title_l = (title or "").lower()
    summary_l = (summary or "").lower()
    body_l = (content or "")[:3000].lower()

    groups = [
        ("科研", ["论文","研究","科研","期刊","会议","proposal","phd","博士","文献","模型","算法","实验","学术"]),
        ("工具", ["github","python","ai","人工智能","网站","工具","开源","代码","程序","可视化","软件","app","效率"]),
        ("学习", ["学习","课程","英语","雅思","汉语","教学","课堂","学生","读书","书单","笔记","知识"]),
        ("旅行", ["旅行","游记","旅途","出发","抵达","火车","高铁","机场","自驾","徒步","景区","博物馆","古城","路线"]),
        ("文化", ["诗词","文学","书法","历史","文化","艺术","古籍","庄子","苏轼","展览"]),
        ("生活", ["生活","日常","家乡","朋友","成长","生日","回忆","随笔","心情","碎片"])
    ]
    scores = []
    for category, words in groups:
        score = 0
        for w in words:
            w = w.lower()
            if w in title_l: score += 5
            if w in summary_l: score += 2
            if w in body_l: score += 1
        scores.append((category, score))
    category, score = max(scores, key=lambda x: x[1])
    return category if score >= 2 else "未分类"

def infer_location(title, category=""):
    """
    Extract place from title independently from category.
    """
    m = re.match(r"^\s*[^｜|]{2,20}[｜|]\s*([^：:｜|，,]{1,20})[：:]", title or "")
    if m:
        v = clean(m.group(1))
        if v and not any(k in v for k in ["随笔","杂记","日常","生活","合集","目录","工具","科研","学习"]):
            return v
    for p in PLACE_HINTS:
        if p.lower() in (title or "").lower():
            return p
    return ""

def normalize_image_url(url):
    url = clean(url)
    if url.startswith("//"):
        url = "https:" + url
    return url

def extract_body_with_images(node):
    """
    Return (plain_text, tokenized_text, image_urls).

    tokenized_text preserves the original text/image order with tokens such as
    [[HWIMG_001]]. Later those tokens are replaced by Markdown image lines.
    """
    if not node:
        return "", "", []

    import copy
    from bs4 import NavigableString

    clone = copy.deepcopy(node)
    for bad in clone.select("script,style,noscript"):
        bad.decompose()

    image_urls = []
    for img in list(clone.find_all("img")):
        u = normalize_image_url(
            img.get("data-src") or img.get("data-original") or
            img.get("data-backsrc") or img.get("src") or ""
        )
        if u.startswith(("http://", "https://")):
            image_urls.append(u)
            token = f"[[HWIMG_{len(image_urls):03d}]]"
            img.replace_with(NavigableString("\n" + token + "\n"))
        else:
            img.decompose()

    raw_text = clone.get_text("\n", strip=False)
    lines = []
    prev = None
    for part in raw_text.splitlines():
        part = re.sub(r"[ \t\u00a0]+", " ", part or "").strip()
        if not part:
            continue
        # Keep image tokens even if adjacent text repeats.
        if part == prev and not part.startswith("[[HWIMG_"):
            continue
        lines.append(part)
        prev = part

    tokenized = "\n".join(lines)
    plain = "\n".join(line for line in lines if not re.fullmatch(r"\[\[HWIMG_\d{3}\]\]", line))
    return plain, tokenized, image_urls

def content_md_from_template(template, image_paths):
    md = template or ""
    for i, path in enumerate(image_paths, 1):
        token = f"[[HWIMG_{i:03d}]]"
        line = f"![正文图片 {i}]({path})" if path else ""
        md = md.replace(token, line)
    md = re.sub(r"\[\[HWIMG_\d{3}\]\]", "", md)
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md

def parse_source(raw, url_hint=""):

    soup = BeautifulSoup(raw, "html.parser")

    def meta(attr, value):
        el = soup.find("meta", attrs={attr:value})
        return clean(el.get("content","")) if el else ""

    # OpenGraph/meta: stable and cheap
    title = meta("property","og:title") or meta("property","twitter:title")
    summary = meta("name","description") or meta("property","og:description") or meta("property","twitter:description")
    cover = meta("property","og:image") or meta("property","twitter:image")
    author = meta("name","author") or meta("property","og:article:author")
    url = meta("property","og:url") or url_hint

    # cgiDataNew / page JS fallback
    title = title or js_value(raw, "title")
    summary = summary or js_value(raw, "desc")
    cover = cover or js_value(raw, "cdn_url")
    url = url or js_value(raw, "link")
    author = author or js_value(raw, "author")
    account = js_value(raw, "nick_name")
    source_url = js_value(raw, "source_url")

    # Date
    create_time = js_value(raw, "create_time") or var_value(raw, "createTime")
    date = ""
    m = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})", create_time)
    if m:
        date = f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"

    # Exact WeChat collection/directory names
    collections = extract_wechat_collections(raw)
    official_category = collections[0]["title"] if collections else ""
    album_url = collections[0]["link"] if collections else ""

    # Full body text + inline images in original order.
    # WeChat now has several page families. Standard graphic articles usually
    # use #js_content.rich_media_content, while video/share pages can reuse
    # #js_content as an EMPTY "share_notice_wrp" container. Therefore try
    # several body selectors and keep the richest meaningful candidate.
    body_candidates = []
    selectors = (
        "#js_content.rich_media_content",
        "#js_article .rich_media_content",
        ".rich_media_area_primary .rich_media_content",
        "#js_content",
        "[data-role='outer']",
    )
    for selector in selectors:
        for node in soup.select(selector):
            c, t, imgs = extract_body_with_images(node)
            # Avoid mistaking a title-only wrapper for the body.
            c_clean = clean(c)
            if c_clean and title and c_clean == clean(title):
                continue
            score = len(c) + 80 * len(imgs)
            if score:
                body_candidates.append((score, c, t, imgs))
    if body_candidates:
        body_candidates.sort(key=lambda x: x[0], reverse=True)
        _, content, content_template, image_urls = body_candidates[0]
    else:
        content, content_template, image_urls = "", "", []

    # Legacy/static source fallback: old pages expose content_noencode beside
    # create_time/cdn_url.
    if not visibleish(content) and not image_urls:
        mc = re.search(
            r"\bcontent_noencode\s*:\s*'((?:\\.|[^'])*)'\s*,\s*(?:create_time|cdn_url)",
            raw, re.S
        )
        if mc:
            decoded = decode_js(mc.group(1))
            content, content_template, image_urls = extract_body_with_images(
                BeautifulSoup(decoded, "html.parser")
            )

    # V6.3 redundant fallback: inspect ALL known body-like JS fields, including
    # video_page_info.content_noencode and videoContentNoEncode. This fixes
    # video/share pages where the first content_noencode is empty but a later
    # occurrence contains the visible description.
    if not visibleish(content) and not image_urls:
        c, t, imgs = best_content_from_js(raw)
        if c or imgs:
            content, content_template, image_urls = c, t, imgs

    # Video/share page final fallback. On these pages the only textual body may
    # legitimately be the visible description under the video. Treat that
    # description as content so the archive does not retry forever.
    body_classes = " ".join(soup.body.get("class", [])) if soup.body else ""
    is_video_page = bool(
        soup.find(id="js_video_page_title")
        or soup.find(id="js_mpvedio")
        or "page_share_video" in body_classes
        or "video_channel" in body_classes
    )
    if not visibleish(content) and not image_urls and is_video_page and summary:
        content = summary
        content_template = summary

    if not summary and content:
        one_line = clean(content)
        summary = one_line[:180].rstrip("，。；：、 ") + ("…" if len(one_line) > 180 else "")

    series = title_series(title)

    if official_category:
        category = official_category
        category_source = "wechat_collection"
    else:
        category = classify_fallback(title, summary, content)
        category_source = "fallback"

    if series:
        cls = series
        class_source = "title_series"
    elif len(collections) > 1:
        cls = collections[1]["title"]
        class_source = "wechat_collection_secondary"
    else:
        cls = ""
        class_source = ""

    location = infer_location(title, category)
    collection_titles = " | ".join(x["title"] for x in collections)

    return {
        "title": title,
        "date": date,
        "category": category,
        "class": cls,
        "location": location,
        "summary": summary,
        "content": content,
        "cover": cover,
        "url": url or url_hint,
        "author": author,
        "account": account,
        "source_url": source_url,
        "album_url": album_url,
        "category_source": category_source,
        "class_source": class_source,
        "collection_titles": collection_titles,
        "_content_template": content_template,
        "_image_urls": image_urls
    }

def safe_filename_part(text, max_chars=52):
    s = (text or "article").strip()
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", s)
    s = re.sub(r"[｜：，。！？、；（）【】《》“”‘’\s]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("._ ")
    return s[:max_chars] or "article"

def short_id(url):
    s = (url or "").rstrip("/").split("/")[-1]
    s = re.sub(r"[^A-Za-z0-9_-]+", "", s)
    return s[:7] or "article"

def local_cover_name(date, title, article_url, ext):
    year = date[:4] if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or "") else "unknown"
    prefix = date if year != "unknown" else "undated"
    filename = f"{prefix}_{safe_filename_part(title)}_{short_id(article_url)}{ext}"
    return year, filename

def save_cover(browser_context, cover_url, article_url, covers_dir, title="", date=""):
    if not cover_url:
        return ""
    try:
        r = browser_context.request.get(
            cover_url,
            headers={"Referer": article_url},
            timeout=30000
        )
        if not r.ok:
            return cover_url
        ct = (r.headers.get("content-type") or "").lower()
        ext = ".webp" if "webp" in ct else ".png" if "png" in ct else ".jpg"
        year, filename = local_cover_name(date, title, article_url, ext)
        out = Path(covers_dir) / year / filename
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(r.body())
        return "./covers/" + year + "/" + filename
    except Exception:
        return cover_url

def article_image_folder(date, title, article_url):
    prefix = date if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or "") else "undated"
    return f"{prefix}_{safe_filename_part(title, max_chars=46)}_{short_id(article_url)}"

def response_extension(content_type, url=""):
    ct = (content_type or "").lower()
    if "webp" in ct: return ".webp"
    if "png" in ct: return ".png"
    if "gif" in ct: return ".gif"
    if "svg" in ct: return ".svg"
    if "jpeg" in ct or "jpg" in ct: return ".jpg"
    m = re.search(r"\.(webp|png|gif|jpe?g|svg)(?:[?#]|$)", url or "", re.I)
    if m:
        ext = m.group(1).lower()
        return ".jpg" if ext in ("jpg","jpeg") else "." + ext
    return ".jpg"

def save_article_images(browser_context, image_urls, article_url, images_dir, title="", date="", refresh=False):
    """Download body images in source order and return (relative_paths, relative_dir)."""
    if not image_urls:
        return [], ""

    folder_name = article_image_folder(date, title, article_url)
    folder = Path(images_dir) / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    rel_dir = "./" + Path(images_dir).name.strip("/\\") + "/" + folder_name
    saved = []

    for order, image_url in enumerate(image_urls, 1):
        prefix = f"{order:03d}"
        existing = sorted(folder.glob(prefix + ".*"))
        if existing and not refresh:
            saved.append(rel_dir + "/" + existing[0].name)
            continue

        try:
            r = browser_context.request.get(
                image_url,
                headers={"Referer": article_url},
                timeout=30000
            )
            if not r.ok:
                saved.append(image_url)
                continue
            ext = response_extension(r.headers.get("content-type") or "", image_url)
            raw = r.body()
            from datetime import datetime
            backup = Path(__file__).resolve().parents[3] / "000 备份" / "lab" / "articles" / datetime.now().strftime("%Y-%m-%d") / "新下载原图" / folder_name
            backup.mkdir(parents=True, exist_ok=True)
            (backup / (prefix + "-" + datetime.now().strftime("%H%M%S%f") + ext)).write_bytes(raw)
            if ext.lower() == ".svg":
                out = folder / (prefix + ext)
                out.write_bytes(raw)
            else:
                import io
                from PIL import Image, ImageOps, ImageSequence
                with Image.open(io.BytesIO(raw)) as image:
                    out = folder / (prefix + ext + ".webp")
                    if getattr(image, "n_frames", 1) > 1:
                        frames, durations = [], []
                        for frame in ImageSequence.Iterator(image):
                            durations.append(frame.info.get("duration", 100))
                            frame = frame.convert("RGBA")
                            frame.thumbnail((400, 400))
                            frames.append(frame.copy())
                        frames[0].save(out, "WEBP", save_all=True, append_images=frames[1:], duration=durations, loop=image.info.get("loop", 0), quality=18, method=3)
                    else:
                        frame = ImageOps.exif_transpose(image)
                        frame.thumbnail((720, 720))
                        frame.convert("RGBA" if "A" in frame.getbands() else "RGB").save(out, "WEBP", quality=22, method=4)
            saved.append(rel_dir + "/" + out.name)
        except Exception:
            saved.append(image_url)

    return saved, rel_dir

def is_legacy_local_cover(path):
    if not path.startswith("./covers/"):
        return False
    # Legacy v2: ./covers/<wechat-short-id>.jpg (no year subfolder)
    rel = path[len("./covers/"):]
    return "/" not in rel

def merge(old, got, refresh=False):
    old = norm_record(old)
    got = norm_record(got)

    factual = ["title","date","summary","content","content_md","url","author","account","source_url","album_url","image_dir","media_version"]
    for k in factual:
        if got[k] and (refresh or not old[k]):
            old[k] = got[k]

    # Replace cover when missing, refresh requested, old one is remote, or old one uses legacy naming.
    if got["cover"] and (
        refresh or not old["cover"] or
        old["cover"].startswith(("http://","https://")) or
        is_legacy_local_cover(old["cover"])
    ):
        old["cover"] = got["cover"]

    if got.get("category") and (
        refresh or not old.get("category") or got.get("category_source") == "wechat_collection"
    ):
        old["category"] = got["category"]
        old["category_source"] = got.get("category_source","")

    if got.get("class") and (
        refresh or not old.get("class") or got.get("class_source") in ("title_series","wechat_collection_secondary")
    ):
        old["class"] = got["class"]
        old["class_source"] = got.get("class_source","")

    if got.get("location") and (refresh or not old.get("location")):
        old["location"] = got["location"]

    if got.get("collection_titles"):
        old["collection_titles"] = got["collection_titles"]

    if isinstance(got.get("images"), list) and (refresh or got.get("media_version") == "5"):
        old["images"] = list(got.get("images") or [])

    return old

def unwrap_saved_view_source(path):
    wrapper = BeautifulSoup(Path(path).read_text(encoding="utf-8", errors="ignore"), "html.parser")
    tds = wrapper.select("td.line-content")
    if not tds:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    return "\n".join(td.get_text("", strip=False) for td in tds)


# ============================== V6 manager/server ==============================
ROOT = Path(__file__).resolve().parent
LAB_SHELVES_PATH = ROOT.parent / "asset" / "local-data" / "lab_shelves.json"
HOST = "127.0.0.1"
DEFAULT_PORT = 18765
STATE_PATH = ROOT / "crawl_state.json"
JSON_PATH = ROOT / "articles.json"
INDEX_PATH = ROOT / "index.html"
TASK_LOCK = threading.Lock()
TASK_RUNNING = False
TASK_RETURN_CODE = None
TASK_MESSAGE = "待命"
LOG_BUFFER = deque(maxlen=200)

# These fields are expected to exist for a normal text article. Fields such as
# class/location/author/source_url can legitimately be empty, so they are not
# treated as hard errors and therefore will not trigger endless re-crawling.
HARD_FIELDS = ("title", "date", "category", "cover", "account")
OPTIONAL_FIELDS = ("class", "location", "author", "source_url", "album_url", "collection_titles", "image_dir")


def log(*parts):
    msg = " ".join(str(x) for x in parts)
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG_BUFFER.append(line)


def atomic_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def visible_text(value):
    return re.sub(r"[\s\u200B-\u200D\uFEFF]", "", str(value or ""))


def is_blank(value):
    return not bool(visible_text(value))


def valid_wechat_url(u):
    return isinstance(u, str) and re.match(r"^https?://mp\.weixin\.qq\.com/", u.strip(), re.I) is not None


def load_archive():
    if not JSON_PATH.exists():
        return []
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("articles.json 顶层必须是数组")
    return [norm_record(x) for x in data]


def record_missing_fields(x):
    """Return only fields worth automatically repairing from the source URL."""
    miss = []
    for k in HARD_FIELDS:
        if is_blank(x.get(k)):
            miss.append(k)

    has_images = isinstance(x.get("images"), list) and len(x.get("images")) > 0
    has_content = not is_blank(x.get("content"))
    has_summary = not is_blank(x.get("summary"))
    has_md = not is_blank(x.get("content_md"))

    # Image-only WeChat posts are valid: do not loop forever trying to invent OCR text.
    if not has_content and not has_images:
        miss.append("content")
    if not has_summary and (has_content or not has_images):
        miss.append("summary")
    if has_content and not has_md:
        miss.append("content_md")

    cover = str(x.get("cover") or "")
    if cover.startswith(("http://", "https://")) and "cover" not in miss:
        miss.append("cover")

    imgs = x.get("images") if isinstance(x.get("images"), list) else []
    if any(str(v).startswith(("http://", "https://")) for v in imgs):
        miss.append("images")
    return list(dict.fromkeys(miss))


def audit_archive(data=None):
    data = data if data is not None else load_archive()
    field_blank = {}
    repairable = []
    for i, x in enumerate(data):
        for k in STRING_FIELDS:
            if is_blank(x.get(k)):
                field_blank[k] = field_blank.get(k, 0) + 1
        if not isinstance(x.get("images"), list) or not x.get("images"):
            field_blank["images"] = field_blank.get("images", 0) + 1
        miss = record_missing_fields(x)
        if miss and valid_wechat_url(x.get("url", "")):
            repairable.append((i, x.get("url", ""), miss))
    return {
        "total": len(data),
        "field_blank": field_blank,
        "repairable": repairable,
        "repairable_count": len(repairable),
    }


def merge_missing_only(old, got, force=False):
    """Fill blanks from source; never overwrite curated nonblank values unless force=True."""
    old = norm_record(old)
    # got may include images list.
    out = dict(old)
    for k in STRING_FIELDS:
        gv = str(got.get(k, "") or "").strip()
        if gv and (force or is_blank(out.get(k))):
            out[k] = gv

    gimgs = got.get("images") if isinstance(got.get("images"), list) else []
    oimgs = out.get("images") if isinstance(out.get("images"), list) else []
    if gimgs and (force or not oimgs or any(str(v).startswith(("http://", "https://")) for v in oimgs)):
        out["images"] = list(gimgs)

    # Localized media may replace a remote nonblank path safely.
    if str(got.get("cover", "")).startswith("./covers/") and str(out.get("cover", "")).startswith(("http://", "https://")):
        out["cover"] = got["cover"]
    if got.get("media_version") and (force or str(out.get("media_version") or "") < str(got.get("media_version"))):
        out["media_version"] = str(got.get("media_version"))
    return out


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}


def local_images_from_disk(x):
    """Recover images[] / image_dir from an already-downloaded local article folder."""
    candidates = []
    raw_dir = str(x.get("image_dir") or "").strip()
    if raw_dir.startswith("./images/"):
        candidates.append(ROOT / raw_dir[2:])
    if x.get("url") and x.get("title"):
        candidates.append(ROOT / "images" / article_image_folder(x.get("date", ""), x.get("title", ""), x.get("url", "")))

    seen = set()
    for folder in candidates:
        try:
            folder = folder.resolve()
        except Exception:
            continue
        key = str(folder).lower()
        if key in seen:
            continue
        seen.add(key)
        if not folder.is_dir():
            continue
        files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]
        if not files:
            continue
        def sort_key(f):
            m = re.match(r"^(\d+)", f.stem)
            return (int(m.group(1)) if m else 10**9, f.name.lower())
        files.sort(key=sort_key)
        rel_dir = "./images/" + folder.name
        return [rel_dir + "/" + f.name for f in files], rel_dir
    return [], ""


def reconcile_local_media(data):
    """Use existing images/ folders first; never redownload files that are already on disk."""
    changed = 0
    for x in data:
        imgs = x.get("images") if isinstance(x.get("images"), list) else []
        local_imgs, local_dir = local_images_from_disk(x)
        if local_imgs and not imgs:
            x["images"] = local_imgs
            x["image_dir"] = local_dir
            x["media_version"] = "6"
            changed += 1
        elif imgs and is_blank(x.get("image_dir")):
            first = str(imgs[0])
            if first.startswith("./images/") and "/" in first[len("./images/"):]:
                x["image_dir"] = first.rsplit("/", 1)[0]
                x["media_version"] = "6"
                changed += 1
    return changed


def snapshot_light(x):
    """Legacy helper retained for compatibility."""
    keep = [
        "title","date","category","class","location","summary","content","cover","url",
        "author","account","source_url","album_url","category_source","class_source",
        "collection_titles","image_dir","media_version"
    ]
    return {k: x.get(k, "") for k in keep}


def sync_index_snapshot(data):
    """无快照版：保留兼容调用，但不写入 index.html。"""
    return None


def _load_state():
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state):
    atomic_json(STATE_PATH, state)


HTTP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
)


class _HttpResponse:
    def __init__(self, status, headers, body):
        self.status = int(status or 0)
        try:
            self.headers = {str(k).lower(): str(v) for k, v in headers.items()}
        except Exception:
            self.headers = {}
        self._body = body or b""
        self.ok = 200 <= self.status < 400

    def body(self):
        return self._body


class _HttpRequestAPI:
    def get(self, url, headers=None, timeout=30000):
        req_headers = {
            "User-Agent": HTTP_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if headers:
            req_headers.update({k: v for k, v in headers.items() if v})
        req = Request(url, headers=req_headers, method="GET")
        try:
            with urlopen(req, timeout=max(float(timeout) / 1000.0, 1.0)) as r:
                return _HttpResponse(getattr(r, "status", 200), r.headers, r.read())
        except HTTPError as e:
            try:
                body = e.read()
            except Exception:
                body = b""
            return _HttpResponse(getattr(e, "code", 0), getattr(e, "headers", {}), body)


class _HttpContext:
    """Minimal adapter matching the context.request.get API used by media download helpers."""
    def __init__(self):
        self.request = _HttpRequestAPI()


def _decode_response_text(resp):
    body = resp.body() if hasattr(resp, "body") else b""
    ctype = str((getattr(resp, "headers", {}) or {}).get("content-type", ""))
    m = re.search(r"charset=([\w.-]+)", ctype, re.I)
    encodings = [m.group(1)] if m else []
    encodings += ["utf-8", "gb18030"]
    for enc in encodings:
        try:
            return body.decode(enc)
        except Exception:
            pass
    return body.decode("utf-8", errors="ignore")


def _http_article_source(http_context, url):
    resp = http_context.request.get(
        url,
        headers={"Referer": "https://mp.weixin.qq.com/"},
        timeout=60000,
    )
    if resp.status in (403, 429):
        raise RuntimeError(f"HTTP_{resp.status}")
    if not resp.ok:
        raise RuntimeError(f"HTTP_{resp.status or 'ERROR'}")
    return _decode_response_text(resp)


def _playwright_article_source(url, headless=True):
    """Lazy browser fallback; Playwright failure must not crash the whole repair task."""
    if not PLAYWRIGHT_AVAILABLE or sync_playwright is None:
        raise RuntimeError("PLAYWRIGHT_UNAVAILABLE")
    manager = None
    p = None
    browser = context = None
    try:
        manager = sync_playwright()
        p = manager.start()
        browser, context, page = _browser_context(p, headless=headless)
        response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
        if response is None:
            raise RuntimeError("NO_RESPONSE")
        if response.status in (403, 429):
            raise RuntimeError(f"HTTP_{response.status}")
        return response.text()
    finally:
        for obj in (context, browser):
            try:
                if obj:
                    obj.close()
            except Exception:
                pass
        try:
            if p:
                p.stop()
        except Exception:
            pass


def fetch_article_source(url, http_context, headless=True):
    """HTTP first, Playwright only as a lazy fallback."""
    http_error = None
    try:
        raw = _http_article_source(http_context, url)
        text = clean(BeautifulSoup(raw, "html.parser").get_text(" ", strip=True))
        got = parse_source(raw, url)
        suspicious = (not got.get("title") and not got.get("content") and len(text) < 2500)
        if not suspicious:
            return raw, "HTTP"
        http_error = RuntimeError("SUSPECT_HTTP_PAGE")
    except Exception as e:
        http_error = e

    log("  HTTP 获取未成功，尝试浏览器兜底：", str(http_error)[:160])
    try:
        return _playwright_article_source(url, headless=headless), "PLAYWRIGHT"
    except Exception as e:
        log("  浏览器兜底不可用：", str(e)[:180])
        raise RuntimeError(f"FETCH_FAILED: HTTP={http_error}; PLAYWRIGHT={e}")


def _browser_context(playwright, headless=False):
    try:
        browser = playwright.chromium.launch(channel="msedge", headless=headless)
        log("浏览器：Microsoft Edge")
    except Exception:
        browser = playwright.chromium.launch(headless=headless)
        log("浏览器：Playwright Chromium")
    context = browser.new_context(locale="zh-CN", viewport={"width": 1280, "height": 800})
    page = context.new_page()

    def route_handler(route):
        if route.request.resource_type == "document":
            route.continue_()
        else:
            route.abort()
    page.route("**/*", route_handler)
    return browser, context, page


def repair_archive(force=False, only_urls=None, headless=True, min_delay=1.5, max_delay=3.0,
                   batch_size=25, batch_rest_min=8.0, batch_rest_max=15.0):
    """Audit and repair only records with missing/remote repairable fields."""
    global TASK_RETURN_CODE, TASK_MESSAGE
    data = load_archive()

    # V6.1: first recover image references from folders that already exist locally.
    # This is zero-network and fixes archives where images/ is complete but JSON lost images[].
    media_fixed = reconcile_local_media(data)
    if media_fixed:
        atomic_json(JSON_PATH, data)
        log(f"本地恢复图片索引：{media_fixed} 篇（无需联网）。")

    # Derived field: if v5 already confirmed there are no inline images, content_md can
    # be rebuilt locally from content. No reason to hit WeChat for this one field.
    local_fixed = 0
    for x in data:
        imgs = x.get("images") if isinstance(x.get("images"), list) else []
        if not is_blank(x.get("content")) and is_blank(x.get("content_md")) and not imgs and str(x.get("media_version") or "") in ("5", "6"):
            x["content_md"] = x.get("content", "")
            x["media_version"] = "6"
            local_fixed += 1
    if local_fixed:
        atomic_json(JSON_PATH, data)
        sync_index_snapshot(data)
        log(f"本地直接修复 content_md：{local_fixed} 篇（无需联网）。")

    state = _load_state()
    wanted = set(only_urls or [])
    targets = []
    for i, x in enumerate(data):
        if wanted and x.get("url") not in wanted:
            continue
        miss = list(STRING_FIELDS) if force else record_missing_fields(x)
        if valid_wechat_url(x.get("url", "")) and (force or miss):
            targets.append((i, miss))

    audit = audit_archive(data)
    log(f"JSON 检查：{len(data)} 篇；需要自动补全 {len(targets)} 篇。")
    if audit["field_blank"]:
        summary = ", ".join(f"{k}:{v}" for k, v in sorted(audit["field_blank"].items()))
        log("空字段统计（含允许为空字段，仅供检查）：", summary)
    if not targets:
        sync_index_snapshot(data)
        TASK_RETURN_CODE = 0
        TASK_MESSAGE = "检查完成，无需补抓"
        return 0

    processed = 0
    stopped = False
    http_context = _HttpContext()
    for pos, (idx, before_missing) in enumerate(targets, 1):
        old = data[idx]
        url = old["url"]
        log(f"[{pos}/{len(targets)}] 补抓 {url}")
        log("  缺少：", ", ".join(before_missing) if before_missing else "force refresh")
        try:
            raw, fetch_mode = fetch_article_source(url, http_context, headless=headless)
            log("  获取方式：", fetch_mode)
            raw_text = clean(BeautifulSoup(raw, "html.parser").get_text(" ", strip=True))
            if any(w in raw_text for w in VERIFY_WORDS):
                raise RuntimeError("WECHAT_VERIFY")

            got = parse_source(raw, url)
            if not got.get("title") and "微信公众平台" in raw_text and len(raw_text) < 2000:
                raise RuntimeError("SUSPECT_PAGE")

            need_cover = force or "cover" in before_missing or str(old.get("cover", "")).startswith(("http://", "https://"))
            if got.get("cover") and need_cover:
                got["cover"] = save_cover(http_context, got["cover"], url, ROOT / "covers", got.get("title", ""), got.get("date", ""))

            image_urls = got.pop("_image_urls", [])
            template = got.pop("_content_template", "")
            need_media = force or any(k in before_missing for k in ("content", "content_md", "images"))
            if need_media:
                local_images, image_dir = save_article_images(
                    http_context, image_urls, url, ROOT / "images",
                    title=got.get("title", ""), date=got.get("date", ""), refresh=force
                )
                got["images"] = local_images
                got["image_dir"] = image_dir
                got["content_md"] = content_md_from_template(template, local_images) or got.get("content", "")
            else:
                got["images"] = old.get("images", []) if isinstance(old.get("images"), list) else []
                got["image_dir"] = old.get("image_dir", "")
                got["content_md"] = old.get("content_md", "")
            got["media_version"] = "6"

            data[idx] = merge_missing_only(old, got, force=force)
            after_missing = record_missing_fields(data[idx])
            atomic_json(JSON_PATH, data)
            sync_index_snapshot(data)
            state[url] = {
                "status": "ok" if not after_missing else "partial",
                "last_checked": datetime.now().isoformat(timespec="seconds"),
                "missing_before": before_missing,
                "missing_after": after_missing,
                "title": data[idx].get("title", ""),
                "fetch_mode": fetch_mode,
            }
            _save_state(state)
            processed += 1
            log("  完成：", data[idx].get("title") or "(仍无标题)")
            if after_missing:
                log("  原文仍未提供/未解析：", ", ".join(after_missing))
        except Exception as e:
            code = str(e)
            state[url] = {
                "status": "stopped" if any(t in code for t in ("WECHAT_VERIFY","HTTP_403","HTTP_429","SUSPECT_PAGE")) else "error",
                "last_checked": datetime.now().isoformat(timespec="seconds"),
                "error": code[:300],
                "missing_before": before_missing,
            }
            _save_state(state)
            atomic_json(JSON_PATH, data)
            log("  失败：", code[:220])
            if any(t in code for t in ("WECHAT_VERIFY","HTTP_403","HTTP_429","SUSPECT_PAGE")):
                log("检测到微信验证/限流，已保存进度，本轮停止。")
                stopped = True
                break

        if pos < len(targets):
            delay = random.uniform(min_delay, max_delay)
            time.sleep(delay)
        if batch_size > 0 and pos % batch_size == 0 and pos < len(targets):
            rest = random.uniform(batch_rest_min, batch_rest_max)
            log(f"批次休息 {rest:.0f}s")
            time.sleep(rest)

    sync_index_snapshot(data)
    TASK_RETURN_CODE = 2 if stopped else 0
    TASK_MESSAGE = f"补全结束：处理 {processed}/{len(targets)} 篇" + ("；因微信验证/限流提前停止" if stopped else "")
    log(TASK_MESSAGE)
    return TASK_RETURN_CODE


def _task_wrapper(force=False, urls=None):
    global TASK_RUNNING, TASK_RETURN_CODE, TASK_MESSAGE
    try:
        TASK_MESSAGE = "正在检查并补全"
        TASK_RETURN_CODE = repair_archive(force=force, only_urls=urls, headless=True)
    except Exception as e:
        TASK_RETURN_CODE = 1
        TASK_MESSAGE = f"任务异常：{e}"
        log(TASK_MESSAGE)
    finally:
        with TASK_LOCK:
            TASK_RUNNING = False


def start_repair_task(force=False, urls=None):
    global TASK_RUNNING, TASK_RETURN_CODE, TASK_MESSAGE
    with TASK_LOCK:
        if TASK_RUNNING:
            return False
        TASK_RUNNING = True
        TASK_RETURN_CODE = None
        TASK_MESSAGE = "准备启动"
        t = threading.Thread(target=_task_wrapper, kwargs={"force": force, "urls": urls}, daemon=True)
        t.start()
        return True


def status_payload():
    tail = "\n".join(list(LOG_BUFFER)[-30:])
    return {"ok": True, "app":"hongwu-articles", "running": TASK_RUNNING, "returncode": TASK_RETURN_CODE, "message": TASK_MESSAGE, "log": tail}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        pass

    def end_headers(self):
        if self.path.endswith((".html", ".json", ".js", ".css")):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()

    def send_json(self, obj, status=200):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/lab_shelves":
            return self.send_json(json.loads(LAB_SHELVES_PATH.read_text(encoding="utf-8")))
        if path == "/api/status":
            return self.send_json(status_payload())
        if path == "/api/audit":
            a = audit_archive()
            a["repairable"] = [{"index": i, "url": u, "missing": m} for i, u, m in a["repairable"]]
            return self.send_json({"ok": True, **a})
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = self.read_json()
        except Exception:
            return self.send_json({"ok": False, "error": "JSON 格式错误"}, 400)

        if path == "/api/shelf/article":
            try:
                item = body.get("article") or {}
                active = bool(body.get("active"))
                shelf = json.loads(LAB_SHELVES_PATH.read_text(encoding="utf-8")) if LAB_SHELVES_PATH.exists() else {}
                if not isinstance(shelf, dict): shelf = {}
                fav = shelf.setdefault("article_favorites", [])
                key = str(item.get("url") or item.get("title") or "").strip()
                fav[:] = [x for x in fav if str(x.get("url") or x.get("title") or "").strip() != key]
                if active and key:
                    fav.insert(0, {"title": item.get("title", ""), "meta": item.get("meta", ""), "url": item.get("url", "")})
                shelf["updated"] = time.strftime("%Y-%m-%d")
                atomic_json(LAB_SHELVES_PATH, shelf)
                return self.send_json({"ok": True, "active": active})
            except Exception as exc:
                return self.send_json({"ok": False, "error": f"收藏同步失败：{exc}"}, 400)

        if path == "/api/add_urls":
            if TASK_RUNNING:
                return self.send_json({"ok": False, "error": "后台补全正在运行，请等它结束后再添加 URL"}, 409)
            urls = [str(u).strip() for u in body.get("urls", []) if valid_wechat_url(str(u).strip())]
            data = load_archive()
            seen = {x.get("url", "") for x in data}
            added = 0
            for u in urls:
                if u in seen:
                    continue
                data.append(norm_record({"url": u}))
                seen.add(u)
                added += 1
            atomic_json(JSON_PATH, data)
            sync_index_snapshot(data)
            return self.send_json({"ok": True, "added": added, "total": len(data)})

        if path == "/api/save_articles":
            if TASK_RUNNING:
                return self.send_json({"ok": False, "error": "后台补全正在运行，请等它结束后再保存编辑"}, 409)
            rows = body.get("articles")
            if not isinstance(rows, list):
                return self.send_json({"ok": False, "error": "articles 必须是数组"}, 400)
            data = [norm_record(x) for x in rows]
            atomic_json(JSON_PATH, data)
            sync_index_snapshot(data)
            return self.send_json({"ok": True, "total": len(data)})

        if path == "/api/enrich":
            force = bool(body.get("force", False))
            urls = body.get("urls") if isinstance(body.get("urls"), list) else None
            if urls:
                urls = [u for u in urls if valid_wechat_url(u)]
            if not start_repair_task(force=force, urls=urls):
                return self.send_json({"ok": False, "error": "抓取任务正在运行"}, 409)
            return self.send_json({"ok": True, "started": True})

        return self.send_json({"ok": False, "error": "unknown endpoint"}, 404)


def serve(port=DEFAULT_PORT, repair_on_start=False, open_browser=True):
    server = None
    chosen = port
    for candidate in range(port, port + 10):
        try:
            server = ThreadingHTTPServer((HOST, candidate), Handler)
            chosen = candidate
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError(f"{port}-{port+9} 端口都被占用")

    url = f"http://{HOST}:{chosen}/index.html"
    log("Hongwu Article Manager V7.0")
    log("本地地址：", url)
    log("浏览器只能通过本地助手写 JSON / 启动抓取；GitHub Pages 仍为只读。")
    log("日志仅显示在当前命令行，不再生成 crawl.log。")
    try:
        a = audit_archive()
        log(f"articles.json：{a['total']} 篇；可按需补全 {a['repairable_count']} 篇。")
    except Exception as e:
        log("articles.json 读取失败：", e)
    if repair_on_start:
        start_repair_task(force=False)
    if open_browser and os.environ.get("HONGWU_LAUNCHED_BY_HUB") != "1":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def cli():
    ap = argparse.ArgumentParser(description="Hongwu Article Manager V7.0")
    ap.add_argument("--audit", action="store_true", help="只检查 articles.json，不联网")
    ap.add_argument("--repair", action="store_true", help="补全缺失字段后退出")
    ap.add_argument("--force", action="store_true", help="强制刷新目标文章（谨慎）")
    ap.add_argument("--url", action="append", default=[], help="只处理指定微信文章 URL，可重复")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--serve-only", action="store_true", help="启动网页但不做启动自动补全")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if args.audit:
        a = audit_archive()
        print(json.dumps({
            "total": a["total"],
            "repairable_count": a["repairable_count"],
            "field_blank": a["field_blank"],
            "repairable": [{"index": i, "url": u, "missing": m} for i, u, m in a["repairable"]],
        }, ensure_ascii=False, indent=2))
        return

    if args.repair:
        raise SystemExit(repair_archive(force=args.force, only_urls=args.url or None, headless=True))

    serve(port=args.port, repair_on_start=False, open_browser=not args.no_browser)


if __name__ == "__main__":
    cli()
