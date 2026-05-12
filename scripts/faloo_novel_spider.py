#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
飞卢小说网（b.faloo.com）书籍信息抓取示例脚本。

用法示例：
  cd c:\Users\Administrator\Desktop\DRF
  venv\Scripts\activate
  pip install requests beautifulsoup4
  python scripts/faloo_novel_spider.py --book-url https://b.faloo.com/1525878.html
  python scripts/faloo_novel_spider.py --novel-id 1525878 --out ./novel_export
  python scripts/faloo_novel_spider.py --novel-id 1525878 --chapters 50   # 前 50 章
  python scripts/faloo_novel_spider.py --novel-id 1525878 --chapters 0    # 合并目录分页后的全部章节
  # 站点若要求登录后阅读正文：在浏览器登录飞卢后复制 Cookie，见脚本 --help 与 docs 说明
  python scripts/faloo_novel_spider.py --novel-id 1525878 --cookie-file ./faloo_cookies.txt
  python scripts/faloo_novel_spider.py --ranking-url https://b.faloo.com/y_7_0_0_0_0_3_1.html --chapters 10 --max-books 5 --max-ranking-pages 3
  cd backend
  python manage.py import_faloo_export --path c:\Users\Administrator\Desktop\DRF\novel_export
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BASE_HOST = "https://b.faloo.com"
# Windows 文件名不允许的字符（含控制字符）
_WIN_BAD_FILENAME = re.compile(r'[\x00-\x1f<>:"/\\|?*]')


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": DEFAULT_UA, "Accept-Language": "zh-CN,zh;q=0.9"})
    return s


def _strip_cookie_prefix(value: str) -> str:
    """去掉误粘贴的「Cookie:」前缀。"""
    s = value.strip()
    if s.lower().startswith("cookie:"):
        return s[7:].strip()
    return s


def _merge_cookie_header(sess: requests.Session, cookie_fragment: str) -> None:
    """追加 Cookie 请求头（与浏览器「复制为 cURL」中的 Cookie 一致）。"""
    c = _strip_cookie_prefix(cookie_fragment)
    if not c:
        return
    old = (sess.headers.get("Cookie") or "").strip()
    sess.headers["Cookie"] = f"{old}; {c}" if old else c


def apply_saved_cookie_header(sess: requests.Session, cookie_inline: str | None, cookie_file: str | None) -> None:
    """创建 Session 后调用：合并命令行/文件中的 Cookie。"""
    parts: list[str] = []
    if cookie_inline:
        parts.append(_strip_cookie_prefix(cookie_inline))
    if cookie_file:
        p = Path(cookie_file)
        if not p.is_file():
            raise FileNotFoundError(f"Cookie 文件不存在：{p}")
        raw = p.read_text(encoding="utf-8", errors="replace").strip()
        if raw.startswith("\ufeff"):
            raw = raw.lstrip("\ufeff")
        lines = [
            ln.strip()
            for ln in raw.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if len(lines) > 1:
            kv_lines = [_strip_cookie_prefix(ln) for ln in lines if "=" in ln]
            if kv_lines:
                parts.append("; ".join(kv_lines))
        elif len(lines) == 1:
            parts.append(_strip_cookie_prefix(lines[0]))
    if not parts:
        return
    merged = "; ".join(x for x in parts if x)
    _merge_cookie_header(sess, merged)


def fetch_text(sess: requests.Session, url: str) -> str:
    r = sess.get(url, timeout=30)
    r.raise_for_status()
    ct = (r.headers.get("Content-Type") or "").lower()
    # 飞卢章节页常为 gb2312；错误解码会导致中文乱码、选择器匹配失败
    if "gb2312" in ct or "gbk" in ct:
        r.encoding = "gbk"
    else:
        r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def faloo_chapter_html_shows_login_wall(html: str) -> bool:
    """章节 HTML 内 noveContent 仍含未登录提示（div.c_c1），说明服务端未认可登录态。"""
    if "c_c1" not in html or "noveContent" not in html:
        return False
    soup = BeautifulSoup(html, "html.parser")
    tip = soup.select_one("div.noveContent div.c_c1")
    if not tip:
        return False
    t = tip.get_text(strip=True)
    return bool(t) and ("登录" in t or "没有登录" in t or "尚未登录" in t or "注册账号" in t)


def absolute_url(href: str, base: str = BASE_HOST) -> str:
    href = (href or "").strip()
    if not href or href.lower().startswith(("javascript:", "#")):
        return ""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http"):
        return href
    return urljoin(base.rstrip("/") + "/", href.lstrip("/"))


def catalog_url_key(url: str) -> str:
    """目录 URL 去重键（忽略末尾 /）。"""
    u = absolute_url(url) if not str(url).startswith("http") else url.strip()
    p = urlparse(u)
    host = (p.netloc or "").lower()
    path = (p.path or "").rstrip("/") or "/"
    return f"{host}{path}".lower()


def is_likely_chapter_content_url(url: str, novel_id: str) -> bool:
    """章节正文地址 /**/{novel_id}_{n}.html"""
    path = urlparse(absolute_url(url)).path
    return bool(re.match(rf"/{novel_id}_\d+\.html$", path))


def is_probable_toc_list_url(url: str, novel_id: str) -> bool:
    """目录索引页（排除单章链接、书籍详情页）。"""
    if novel_id not in url:
        return False
    if is_likely_chapter_content_url(url, novel_id):
        return False
    path = urlparse(absolute_url(url)).path
    if re.search(r"/html_\d+_\d+", path):
        return True
    if re.search(rf"/booklist/{novel_id}(?:[/._]|\.html|$)", path.replace("//", "/")):
        return True
    return False


def find_next_toc_page_url(soup: BeautifulSoup, novel_id: str, current_url: str) -> str | None:
    """解析「下一页」等与目录分页相关的链接。"""
    cur_key = catalog_url_key(current_url)

    def consider(href: str) -> str | None:
        full = absolute_url(href)
        if not full or not is_probable_toc_list_url(full, novel_id):
            return None
        if catalog_url_key(full) == cur_key:
            return None
        return full

    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        title = (a.get("title") or "").strip()
        if text in ("下一页", "下页"):
            pass
        elif "下一页" in title and "下一章" not in title:
            pass
        else:
            continue
        got = consider(a["href"])
        if got:
            return got

    for ln in soup.find_all("link"):
        rel = ln.get("rel") or []
        if isinstance(rel, str):
            rel = [rel]
        if "next" not in [str(x).lower() for x in rel]:
            continue
        href = ln.get("href")
        if not href:
            continue
        got = consider(href)
        if got:
            return got
    return None


def normalize_book_url(novel_id_or_url: str) -> tuple[str, str]:
    """返回 (书籍详情页 URL, 纯数字 novel_id)。"""
    s = novel_id_or_url.strip()
    if s.isdigit():
        nid = s
        return f"{BASE_HOST}/{nid}.html", nid
    if "faloo.com" in s:
        path = urlparse(s).path.strip("/")
        m = re.match(r"^(\d+)\.html$", path)
        if m:
            return s.split("?")[0], m.group(1)
    raise ValueError(f"无法解析书籍地址或 ID：{novel_id_or_url!r}")


def parse_faloo_genres(soup: BeautifulSoup) -> tuple[str, str]:
    """飞卢书籍详情页「小说分类」主类与「小说子类」；导入时优先用子类作本站分类。"""
    main, sub = "", ""
    og = soup.find("meta", attrs={"name": "og:novel:category"})
    if og and og.get("content"):
        main = (og.get("content") or "").strip()
    for div in soup.select("div.T-R-T-B2-Box1"):
        label_el = div.select_one("span.colorQianHui")
        a = div.select_one("a[href]")
        if not label_el or not a:
            continue
        label = label_el.get_text(strip=True)
        name = (a.get("title") or a.get_text(strip=True) or "").strip()
        if label.startswith("小说分类"):
            if name:
                main = name
        elif "小说子类" in label:
            if name:
                sub = name
    return main, sub


def parse_book_info(html: str, novel_id: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one("h1#novelName")
    title = title_el.get_text(strip=True) if title_el else ""
    if not title:
        og = soup.find("meta", property="og:title")
        title = (og.get("content") or "").strip() if og else ""

    author = ""
    og_auth = soup.find("meta", attrs={"name": "og:novel:author"})
    if og_auth and og_auth.get("content"):
        author = og_auth["content"].strip()

    cover_url = ""
    og_img = soup.find("meta", property="og:image")
    if og_img and og_img.get("content"):
        cover_url = og_img["content"].strip()
    if not cover_url:
        img = soup.select_one("div.T-L-T-Img img.imgcss")
        if img and img.get("src"):
            cover_url = img["src"].strip()

    toc_href = ""
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/html_\d+_\d+/?$", href):
            toc_href = href
            break
    if not toc_href:
        raise RuntimeError("未在书籍页找到目录链接（html_*_* 格式），页面结构可能已变更。")

    if toc_href.startswith("//"):
        toc_url = "https:" + toc_href
    else:
        toc_url = urljoin(BASE_HOST + "/", toc_href.lstrip("/"))

    genre_main, genre_sub = parse_faloo_genres(soup)

    return {
        "novel_id": novel_id,
        "title": title,
        "author": author,
        "cover_url": cover_url,
        "toc_url": toc_url,
        "category_main": genre_main,
        "category_sub": genre_sub,
    }


def parse_book_chapter_total_hint(html: str, novel_id: str) -> int | None:
    """从详情页推断「至少应有」的章节数：优先 og:novel:latest_chapter_url，其次「已写 N 章」。"""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("meta", attrs={"name": "og:novel:latest_chapter_url"})
    if tag and tag.get("content"):
        m = re.search(rf"{novel_id}_(\d+)\.html", tag["content"])
        if m:
            return int(m.group(1))
    m = re.search(r"已写\s*(?:</[^>]+>\s*)*(\d+)\s*(?:</[^>]+>\s*)*章", html)
    if m:
        return int(m.group(1))
    m2 = re.search(r"已写\s*(\d+)\s*章", html)
    if m2:
        return int(m2.group(1))
    return None


def parse_book_intro(html: str) -> str:
    """从书籍详情页取出简介正文（多段 <p>）；失败时尝试 og:description。"""
    soup = BeautifulSoup(html, "html.parser")
    box = soup.select_one("div.T-L-T-C-Box1")
    if box:
        parts: list[str] = []
        for p in box.find_all("p"):
            t = p.get_text("\n", strip=True)
            if not t:
                continue
            # 站点统一免责声明，一般不视作正文简介
            if "飞卢小说网提醒您" in t and "纯属虚构" in t:
                continue
            parts.append(t)
        if parts:
            return "\n\n".join(parts)
    og = soup.find("meta", property="og:description")
    if og and og.get("content"):
        return og["content"].strip()
    return ""


def sanitize_filename_stem(name: str, max_len: int = 120) -> str:
    """生成可作 Windows 文件名的主干（不含扩展名），无效则返回空串。"""
    s = _WIN_BAD_FILENAME.sub("_", name.strip())
    s = re.sub(r"\s+", " ", s).strip(" .")
    if len(s) > max_len:
        s = s[:max_len].rstrip(" .")
    return s


def normalize_chapter_title_for_filename(title: str) -> str:
    """统一「第 N 章」写法（去掉数字两侧多余空格），避免「第 8 章」与「第8章」混排。"""
    s = title.strip()
    s = re.sub(r"第\s*(\d+)\s*章", r"第\1章", s)
    return s


def chapter_ordered_txt_filename(
    order_index: int,
    chapter_num: int,
    toc_title: str,
    pad_width: int,
    used_lower: set[str],
) -> str:
    """生成「序号_标题.txt」，序号零填充，保证按名称排序即章节顺序。"""
    title_part = normalize_chapter_title_for_filename(toc_title)
    stem = sanitize_filename_stem(title_part) or f"第{chapter_num}章"
    prefix = f"{order_index:0{pad_width}d}"
    base = f"{prefix}_{stem}"
    candidate = f"{base}.txt"
    n = 1
    while candidate.lower() in used_lower:
        candidate = f"{base}_{n}.txt"
        n += 1
    used_lower.add(candidate.lower())
    return candidate


def extract_chapter_map_from_toc_html(html: str, novel_id: str) -> dict[int, tuple[str, str]]:
    """单页目录 → {章节号: (章节 URL, 目录标题)}。"""
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[int, tuple[str, str]] = {}
    pat = re.compile(rf"{novel_id}_(\d+)\.html")
    for a in soup.select("div.c_con_list a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        m = pat.search(href)
        if not m:
            continue
        num = int(m.group(1))
        if num in seen:
            continue
        span = a.select_one("span.width1") or a.select_one("span.width2")
        toc_title = span.get_text(strip=True) if span else ""
        if not toc_title:
            toc_title = a.get_text(strip=True)
        toc_title = re.sub(r"\s*new\s*$", "", toc_title, flags=re.I).strip()
        toc_title = normalize_chapter_title_for_filename(toc_title)
        if href.startswith("//"):
            full = "https:" + href
        elif href.startswith("http"):
            full = href
        else:
            full = urljoin(BASE_HOST + "/", href.lstrip("/"))
        seen[num] = (full, toc_title or f"第{num}章")
    return seen


def chapter_rows_from_map(
    merged: dict[int, tuple[str, str]], limit: int
) -> list[tuple[int, str, str]]:
    """limit > 0 时取前 limit 章；limit <= 0 表示全部。"""
    ordered = sorted(merged.items(), key=lambda x: x[0])
    rows = [(n, u, t) for n, (u, t) in ordered]
    if limit and limit > 0:
        return rows[:limit]
    return rows


def collect_chapters_from_all_toc_pages(
    sess: requests.Session,
    start_url: str,
    novel_id: str,
    delay: float,
    max_pages: int,
) -> tuple[dict[int, tuple[str, str]], list[str]]:
    """从起始目录 URL 起，跟随「下一页」合并多页章节；多数书仅一页。"""
    merged: dict[int, tuple[str, str]] = {}
    visited_keys: set[str] = set()
    pages_urls: list[str] = []
    toc_url = start_url
    pages = 0

    while toc_url and pages < max_pages:
        key = catalog_url_key(toc_url)
        if key in visited_keys:
            break
        visited_keys.add(key)
        pages_urls.append(toc_url)
        pages += 1

        html = fetch_text(sess, toc_url)
        time.sleep(delay)
        page_map = extract_chapter_map_from_toc_html(html, novel_id)
        for num, pair in page_map.items():
            if num not in merged:
                merged[num] = pair

        soup = BeautifulSoup(html, "html.parser")
        next_url = find_next_toc_page_url(soup, novel_id, toc_url)
        if not next_url:
            break
        nk = catalog_url_key(next_url)
        if nk in visited_keys:
            break
        toc_url = next_url
        print(f"[*] 目录分页: {toc_url}")

    return merged, pages_urls


def parse_chapter_body(html: str) -> tuple[str, str]:
    """返回 (章节标题, 正文纯文本)。

    阅读页正文通常在 ``div.noveContent`` 的 ``<p>`` 中；未登录时该区域多为登录提示 div（无 ``<p>``）。
    部分章节可能仅有 ``<br>`` 分隔，故在无 ``<p>`` 时对容器做 ``get_text`` 回退（已去掉广告/登录块）。
    """
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.select_one("div.c_l_title h1")
    chapter_title = h1.get_text(strip=True) if h1 else ""
    div = soup.select_one("div.noveContent")
    if not div:
        return chapter_title, ""
    # 去掉登录引导、VIP 推广等，避免 fallback 把提示语当作正文
    for sel in (".c_c1", ".c_c3", ".c_c4"):
        for bad in div.select(sel):
            bad.decompose()
    for sty in div.find_all("style"):
        sty.decompose()
    parts: list[str] = []
    for p in div.find_all("p"):
        t = p.get_text("\n", strip=True)
        if t:
            parts.append(t)
    if parts:
        return chapter_title, "\n\n".join(parts)
    # 无 <p> 时尝试整段文本（飞卢登录后偶见其它容器）
    fallback = div.get_text("\n\n", strip=True)
    junk = ("飞卢小说网", "按左右键翻页", "最新读者", "读者还喜欢", "打赏作者")
    if any(j in fallback for j in junk):
        return chapter_title, ""
    return chapter_title, fallback


def download_cover(sess: requests.Session, url: str, dest: Path) -> None:
    if not url:
        return
    r = sess.get(url, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)


def extract_book_ids_from_ranking_html(html: str) -> list[str]:
    """从排行榜 / 分类列表页提取书籍详情页 ID（路径为 ``/{novel_id}.html``，排除 ``数字_章节.html``）。

    仅扫描主列表容器 ``#BookContent``，避免页眉搜索框旁「热搜」链接先于正文榜单进入 DOM 顺序。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#BookContent")
    if root is None:
        root = soup
    ids: list[str] = []
    seen: set[str] = set()
    for a in root.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        full = absolute_url(href)
        if "faloo.com" not in full:
            continue
        path = urlparse(full).path
        name = path.rstrip("/").split("/")[-1]
        if "_" in name.replace(".html", ""):
            continue
        m = re.match(r"^(\d{4,12})\.html$", name)
        if not m:
            continue
        nid = m.group(1)
        if nid in seen:
            continue
        seen.add(nid)
        ids.append(nid)
    return ids


def find_next_ranking_page_url(soup: BeautifulSoup, current_url: str) -> str | None:
    """排行榜「下一页」或 ``…_N.html`` 页码递增。"""
    cur_key = catalog_url_key(current_url)
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").strip()
        title = (a.get("title") or "").strip()
        if text not in ("下一页", "下页") and "下一页" not in title:
            continue
        full = absolute_url(a["href"])
        if not full or "faloo.com" not in full:
            continue
        if catalog_url_key(full) == cur_key:
            continue
        return full.split("#")[0]

    m = re.search(r"_(\d+)(\.html?)$", current_url)
    if m:
        n = int(m.group(1))
        ext = m.group(2)
        next_u = re.sub(r"_(\d+)(\.html?)$", f"_{n + 1}{ext}", current_url)
        if next_u != current_url:
            return next_u
    return None


def collect_ranking_novel_ids(
    sess: requests.Session,
    start_url: str,
    max_pages: int,
    delay: float,
) -> list[str]:
    """抓取排行榜多页，合并去重后的 novel_id 列表（顺序大致为榜单顺序）。"""
    url = start_url.strip().split("#")[0]
    visited_pages: set[str] = set()
    ordered: list[str] = []
    seen_ids: set[str] = set()

    for page_idx in range(max_pages):
        key = catalog_url_key(url)
        if key in visited_pages:
            break
        visited_pages.add(key)
        print(f"[*] 排行榜第 {page_idx + 1} 页: {url}")
        html = fetch_text(sess, url)
        time.sleep(delay)
        soup = BeautifulSoup(html, "html.parser")
        for nid in extract_book_ids_from_ranking_html(html):
            if nid not in seen_ids:
                seen_ids.add(nid)
                ordered.append(nid)
        nxt = find_next_ranking_page_url(soup, url)
        if not nxt or nxt == url:
            break
        url = nxt

    return ordered


def _remove_novel_export_dir_if_no_saved_chapters(novel_dir: Path, chap_dir: Path) -> None:
    """仅在 chapters 下没有任何 .txt 时删除整本 novel_*；已有章节则保留（中途失败不删已下载正文）。"""
    if not novel_dir.is_dir():
        return
    if chap_dir.is_dir() and any(chap_dir.glob("*.txt")):
        return
    shutil.rmtree(novel_dir, ignore_errors=True)


def _try_write_partial_meta(novel_dir: Path, meta: dict | None) -> None:
    """异常退出时若已有章节列表则写入 meta.json，便于部分导入。"""
    if not meta or not meta.get("chapters_fetched"):
        return
    path = novel_dir / "meta.json"
    try:
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[!] 已保存部分进度（meta.json，共 {len(meta['chapters_fetched'])} 章）: {path}", file=sys.stderr)
    except OSError as e:
        print(f"[!] 无法写入部分 meta.json: {e}", file=sys.stderr)


def crawl_single_novel(
    sess: requests.Session,
    novel_id: str,
    out_root: Path,
    chapters: int,
    delay: float,
    max_toc_pages: int,
) -> int:
    """爬取单本书；返回 0 成功，1 失败（如无章节、解析异常）；异常不向外抛出，便于排行榜批量继续下一本。
    章节爬到一半失败时保留已下载的 .txt，仅当 chapters 下无任何章节文件时才删除整本目录。"""
    book_url, novel_id = normalize_book_url(novel_id)
    novel_dir = out_root / f"novel_{novel_id}"
    chap_dir = novel_dir / "chapters"
    meta: dict | None = None

    try:
        print(f"[*] 书籍页: {book_url}")
        html_book = fetch_text(sess, book_url)
        time.sleep(delay)

        info = parse_book_info(html_book, novel_id)
        # 仅在有有效书籍页解析结果后再建目录，避免「跳过」的书留下空 novel_* 文件夹
        novel_dir.mkdir(parents=True, exist_ok=True)
        chap_dir.mkdir(parents=True, exist_ok=True)

        print(f"[*] 书名: {info['title']}")
        _cm = (info.get("category_main") or "").strip()
        _cs = (info.get("category_sub") or "").strip()
        if _cm or _cs:
            _gl = f"{_cs}（{_cm}）" if (_cs and _cm) else (_cs or _cm)
            print(f"[*] 作品分类: {_gl}")
        print(f"[*] 目录: {info['toc_url']}")

        intro_text = parse_book_intro(html_book)
        intro_path = novel_dir / "简介.txt"
        intro_path.write_text(intro_text + ("\n" if intro_text else ""), encoding="utf-8")
        if intro_text:
            print(f"[*] 简介已保存: {intro_path}")
        else:
            print(f"[!] 未解析到简介正文，已写入空文件: {intro_path}", file=sys.stderr)

        total_hint = parse_book_chapter_total_hint(html_book, novel_id)
        merged_map, toc_page_urls = collect_chapters_from_all_toc_pages(
            sess,
            info["toc_url"],
            novel_id,
            delay,
            max_toc_pages,
        )
        links = chapter_rows_from_map(merged_map, chapters)
        if not links:
            print("[!] 目录未解析到章节链接（可能需登录或页面结构变化）。", file=sys.stderr)
            _remove_novel_export_dir_if_no_saved_chapters(novel_dir, chap_dir)
            return 1

        max_idx = max(merged_map.keys()) if merged_map else 0
        if total_hint is not None and max_idx < total_hint:
            print(
                f"[!] 详情页最新章约为第 {total_hint} 章，目录合并到的最大章节号为 {max_idx}（分页未识别、登录或改版均有可能）。",
                file=sys.stderr,
            )

        meta = {
            **info,
            "chapter_count_requested": (
                "all_merged_toc" if chapters <= 0 else chapters
            ),
            "toc_pages": toc_page_urls,
            "toc_page_count": len(toc_page_urls),
            "total_chapters_on_book_page_hint": total_hint,
            "intro_file": str(intro_path.relative_to(out_root)),
            "chapters_fetched": [],
        }

        if info["cover_url"]:
            ext = Path(urlparse(info["cover_url"]).path).suffix or ".jpg"
            cover_path = novel_dir / f"cover{ext}"
            try:
                download_cover(sess, info["cover_url"], cover_path)
                meta["cover_file"] = str(cover_path.relative_to(out_root))
                print(f"[*] 封面已保存: {cover_path}")
            except requests.RequestException as e:
                print(f"[!] 封面下载失败: {e}", file=sys.stderr)
            time.sleep(delay)

        used_names: set[str] = set()
        pad_width = max(4, len(str(len(links))))
        mtime_base = time.time()

        for order_idx, (num, url, toc_title) in enumerate(links, start=1):
            filename = chapter_ordered_txt_filename(
                order_idx, num, toc_title, pad_width, used_names
            )
            print(f"[*] {toc_title} … {url}")
            try:
                body_html = fetch_text(sess, url)
            except requests.RequestException as e:
                print(f"[!] 请求失败: {e}", file=sys.stderr)
                continue
            time.sleep(delay)
            ch_title, text = parse_chapter_body(body_html)
            if not (text or "").strip():
                if faloo_chapter_html_shows_login_wall(body_html):
                    print(
                        "[!] 本章 HTML 仍显示「未登录」区块（div.noveContent .c_c1），"
                        "服务端未认可你的登录 Cookie。\n"
                        "    常见原因：① Windows PowerShell 下使用 --cookie 时，"
                        "Cookie 里的 **&**（如 KeenFire=...&UserID=...）会把参数截断，"
                        "请改用 **--cookie-file**（UTF-8 文本文件，单行粘贴浏览器 Request Headers 里的整段 Cookie）；"
                        "② Cookie 过期；③ 复制的不是 b.faloo.com 的请求 Cookie。",
                        file=sys.stderr,
                    )
                else:
                    print(
                        "[!] 本章未解析到正文（div.noveContent 无有效段落）；"
                        "若正文由前端异步加载，需扩展脚本请求接口或用浏览器导出。",
                        file=sys.stderr,
                    )
            fn = chap_dir / filename
            fn.write_text(
                (ch_title + "\n\n" + text if ch_title else text),
                encoding="utf-8",
            )
            try:
                ts = mtime_base + float(order_idx)
                os.utime(fn, (ts, ts))
            except OSError:
                pass
            meta["chapters_fetched"].append(
                {
                    "index": num,
                    "sort_order": order_idx,
                    "toc_title": toc_title,
                    "file": str(fn.relative_to(out_root)),
                    "page_title": ch_title,
                }
            )

        meta_path = novel_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[*] 完成。元数据: {meta_path}")
        return 0
    except requests.RequestException as e:
        print(f"[!] novel_{novel_id}: 网络请求失败 — {e}", file=sys.stderr)
        _try_write_partial_meta(novel_dir, meta)
        _remove_novel_export_dir_if_no_saved_chapters(novel_dir, chap_dir)
        return 1
    except RuntimeError as e:
        print(f"[!] novel_{novel_id}: 跳过 — {e}", file=sys.stderr)
        _try_write_partial_meta(novel_dir, meta)
        _remove_novel_export_dir_if_no_saved_chapters(novel_dir, chap_dir)
        return 1
    except Exception as e:
        print(f"[!] novel_{novel_id}: 跳过 — {type(e).__name__}: {e}", file=sys.stderr)
        _try_write_partial_meta(novel_dir, meta)
        _remove_novel_export_dir_if_no_saved_chapters(novel_dir, chap_dir)
        return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="爬取飞卢书籍封面与前 N 章正文（学习示例）")
    ap.add_argument("--book-url", help="书籍详情页 URL，如 https://b.faloo.com/1525878.html")
    ap.add_argument("--novel-id", help="书籍数字 ID（与 --book-url / --ranking-url 互斥）")
    ap.add_argument(
        "--ranking-url",
        help="排行榜/分类列表页 URL（如 y_*_*_…_1.html），将按页解析书籍链接并依次爬取",
    )
    ap.add_argument("--out", default="./faloo_export", help="输出目录")
    ap.add_argument(
        "--chapters",
        type=int,
        default=10,
        metavar="N",
        help="抓取前 N 章；N=0 表示合并全部目录分页后的全部章节（默认 10）",
    )
    ap.add_argument("--delay", type=float, default=0.6, help="请求间隔秒数，默认 0.6")
    ap.add_argument(
        "--max-toc-pages",
        type=int,
        default=100,
        metavar="M",
        help="目录列表最多跟随「下一页」的次数（防止死循环），默认 100",
    )
    ap.add_argument(
        "--max-ranking-pages",
        type=int,
        default=10,
        metavar="P",
        help="排行榜最多翻页次数（与「下一页」或 URL 页码递增配合），默认 10",
    )
    ap.add_argument(
        "--max-books",
        type=int,
        default=0,
        metavar="K",
        help="排行榜模式下最多爬取 K 本书（0 表示不限制，按榜单解析到的全部）",
    )
    ap.add_argument(
        "--cookie",
        metavar="STR",
        help='登录后的 Cookie（与 HTTP 请求头一致），如 name1=val1; name2=val2',
    )
    ap.add_argument(
        "--cookie-file",
        metavar="PATH",
        help="从文件读取 Cookie：可单行整段，或多行每行 name=value（见文档）",
    )
    args = ap.parse_args()

    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    sess = _session()
    try:
        apply_saved_cookie_header(sess, args.cookie, args.cookie_file)
    except FileNotFoundError as e:
        print(f"[!] {e}", file=sys.stderr)
        return 1
    if args.cookie or args.cookie_file:
        print("[*] 已附加 Cookie（用于需登录可见的正文等）；请勿泄露 cookie 文件。")

    if args.ranking_url:
        if args.book_url or args.novel_id:
            ap.error("--ranking-url 不应与 --book-url / --novel-id 同时使用")
        ru = args.ranking_url.strip()
        if "faloo.com" not in ru:
            ru = urljoin(BASE_HOST + "/", ru.lstrip("/"))
        ids = collect_ranking_novel_ids(
            sess, ru, args.max_ranking_pages, args.delay
        )
        if args.max_books and args.max_books > 0:
            ids = ids[: args.max_books]
        if not ids:
            print("[!] 排行榜页未解析到任何书籍链接（页面结构或登录限制）。", file=sys.stderr)
            return 1
        print(f"[*] 共 {len(ids)} 本书待爬取（各书间隔 {args.delay}s）")
        failed = 0
        for i, nid in enumerate(ids, start=1):
            print(f"\n[*] ========== [{i}/{len(ids)}] novel_{nid} ==========")
            rc = crawl_single_novel(
                sess,
                nid,
                out_root,
                args.chapters,
                args.delay,
                args.max_toc_pages,
            )
            if rc != 0:
                failed += 1
            time.sleep(args.delay)
        print(f"\n[*] 批量结束：成功 {len(ids) - failed}，失败 {failed}")
        return 0 if failed == 0 else 1

    if args.book_url:
        _, novel_id = normalize_book_url(args.book_url)
    elif args.novel_id:
        _, novel_id = normalize_book_url(args.novel_id)
    else:
        ap.error("请指定 --book-url、--novel-id 或 --ranking-url")

    return crawl_single_novel(
        sess,
        novel_id,
        out_root,
        args.chapters,
        args.delay,
        args.max_toc_pages,
    )


if __name__ == "__main__":
    raise SystemExit(main())
