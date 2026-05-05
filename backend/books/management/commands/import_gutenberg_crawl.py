"""
从 Project Gutenberg 官网的图书详情页（HTML）抓取公版书的书名、作者、简介，并尽量下载站方提供的封面图。

- 公版、学术与教学常用来源；请合理设置 --delay，勿高频请求（尊重对方服务器）。
- 与 Open Library 无关，仅解析 gutenberg.org 页面。
- 唯一键使用内部编号 PG-{id}，不填写真实商业 ISBN（避免与实书冲突）。

用法示例:
  python manage.py import_gutenberg_crawl
  python manage.py import_gutenberg_crawl --ids 11,1342,84 --delay 1.5
  python manage.py import_gutenberg_crawl --dry-run
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from books.models import Book, Category

E_BOOK_URL = "https://www.gutenberg.org/ebooks/{eid}"
USER_AGENT = "LibraryEDU-DRF-Import/1.0 (+local educational; respects robots: delay) Mozilla/5.0"

# 几本站方常见 EPUB 封面图路径；若 404 则再从页面中找 img
COVER_URL_PATTERNS = [
    "https://www.gutenberg.org/cache/epub/{eid}/pg{eid}.cover.medium.jpg",
    "https://www.gutenberg.org/cache/epub/{eid}/pg{eid}.cover.small.jpg",
    "https://www.gutenberg.org/files/{eid}/{eid}-h/cover.jpg",
]
# 公版常读：爱丽丝、科学怪人、傲慢与偏见、白鲸、时间机器 等
DEFAULT_EBOOK_IDS = (11, 84, 1342, 2701, 35)


def _gut_isbn(eid: int) -> str:
    s = f"PG{str(eid).zfill(7)}"
    return s[:20]


def _fetch_text(session: requests.Session, url: str, timeout: int = 45) -> str:
    r = session.get(url, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def _abs_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin("https://www.gutenberg.org/", href)


def _parse_ebook_page(html: str, eid: int) -> Dict[str, Any]:
    """尽量兼容古登堡近年改版，多路选择器兜底。"""
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    author = ""
    description = ""
    cover_from_page: Optional[str] = None

    h1 = soup.find("h1", itemprop="name")
    if not h1:
        h1 = soup.find("h1", attrs={"property": "name"})
    if not h1:
        h1 = soup.find("h1")
    if h1:
        # 只取首行，避免部分页面 h1 内粘进大段说明；再拆 "Title by Author"
        raw = h1.get_text("\n", strip=True) or ""
        first = raw.split("\n")[0].strip() if raw else ""
        m = re.match(r"^(.+?)\s+by\s+(.+)$", first, re.IGNORECASE)
        if m:
            title = re.sub(r"\s+", " ", m.group(1).strip())[:200]
            author = re.sub(r"\s+", " ", m.group(2).strip())[:200]
        else:
            t2 = re.sub(r" by .+$", "", first, flags=re.I)
            t2 = re.sub(r" — .+$", "", t2)
            t2 = re.sub(r"Project Gutenberg.*$", "", t2, flags=re.I)
            title = re.sub(r"\s+", " ", t2).strip()[:200]

    a_auth = soup.select_one('a[href*="/ebooks/author/"]')
    if a_auth:
        author = a_auth.get_text(" ", strip=True)[:200]
    if not author and h1:
        byp = re.search(
            r"\bby\s+([^\n<]{2,120})",
            h1.get_text() if h1 else "",
            re.IGNORECASE,
        )
        if byp:
            author = re.sub(r"\s+", " ", byp.group(1)).strip()[:200]
    if not author:
        author = "公版/佚名 (Gutenberg)"

    eid_s = str(eid)
    for img in soup.find_all("img", src=True):
        raw = (img.get("src") or "").strip()
        if not raw:
            continue
        low = raw.lower()
        if f"/{eid_s}/" in low or f"epub/{eid_s}" in low or f"files/{eid_s}" in low:
            if "cover" in low or "epub" in low or "cache" in low:
                cover_from_page = _abs_url(raw)
                break

    # 简介：多选择器
    for css in (
        "div#about",
        "#about",
        "#pg-content",
        "div#about-1",
        "table.bib",
        "table.bibrec",
    ):
        el = soup.select_one(css)
        if el:
            description = el.get_text("\n", strip=True)[:10000]
            if len(description) > 80:
                break
    if not description or len(description) < 20:
        meta = soup.find("meta", attrs={"name": re.compile("description", re.I)})
        if meta and meta.get("content"):
            description = (meta.get("content") or "").strip()[:10000]
    if not description:
        description = (
            f"来自 Project Gutenberg 公版书目录 (ebook #{eid})。\n"
            f"原站：{E_BOOK_URL.format(eid=eid)}"
        )[:10000]

    if not title:
        title = f"Gutenberg Ebook {eid}"

    return {
        "title": title,
        "author": author,
        "description": description,
        "cover_url_from_page": cover_from_page,
    }


def _download_cover(
    session: requests.Session, eid: int, page_url: Optional[str]
) -> Optional[Tuple[bytes, str]]:
    for ptn in COVER_URL_PATTERNS:
        url = ptn.format(eid=eid)
        try:
            r = session.get(url, timeout=30, allow_redirects=True, stream=True)
            ct = (r.headers.get("Content-Type") or "").lower()
            if r.status_code == 200 and r.content and 500 < len(r.content) < 8_000_000:
                if "image" in ct or "jpeg" in ct or "png" in ct or url.lower().endswith((".jpg", ".jpeg", ".png")):
                    return r.content, f"pg{eid}.jpg"
        except OSError:
            continue
    if page_url and page_url.startswith("http"):
        try:
            r = session.get(page_url, timeout=30, stream=True)
            ct = (r.headers.get("Content-Type") or "").lower()
            if r.status_code == 200 and r.content and 500 < len(r.content) < 8_000_000:
                if "image" in ct:
                    return r.content, f"pg{eid}_from_page.jpg"
        except OSError:
            pass
    return None


def _ids_arg(arg: str) -> List[int]:
    out: List[int] = []
    for part in re.split(r"[,\s]+", arg.strip()):
        if not part:
            continue
        try:
            out.append(int(part))
        except ValueError:
            continue
    return out or list(DEFAULT_EBOOK_IDS)


class Command(BaseCommand):
    help = "从 gutenberg.org 公版书详情页抓取元数据与封面，写入本系统（非 Open Library）。"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--ids",
            type=str,
            default=",".join(str(x) for x in DEFAULT_EBOOK_IDS),
            help="逗号分隔的 Gutenberg 电子书 id，如 11,1342",
        )
        parser.add_argument(
            "--category", type=str, default="公版书 (Gutenberg)", help="分类，不存在会创建"
        )
        parser.add_argument("--delay", type=float, default=1.2, help="每本书之间的停顿（秒）")
        parser.add_argument("--dry-run", action="store_true", help="只拉取、不写入数据库与文件")
        parser.add_argument("--no-cover", action="store_true", help="不下载图片")

    def handle(self, *args, **options) -> None:
        ids = _ids_arg(options.get("ids") or "")
        delay = max(0.3, float(options.get("delay") or 1.2))
        cat_name = (options.get("category") or "公版书 (Gutenberg)")[:100]
        dry = bool(options.get("dry_run"))
        no_cover = bool(options.get("no_cover"))

        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT
        session.headers["Accept"] = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8"
        session.headers["Accept-Language"] = "en-US,en;q=0.9,zh;q=0.8"

        cat, _ = Category.objects.get_or_create(name=cat_name) if not dry else (None, None)
        if dry:
            self.stdout.write(self.style.WARNING("DRY-RUN：不写入数据库。"))
        else:
            assert cat is not None

        created, skipped, failed = 0, 0, 0
        for eid in ids:
            isbn = _gut_isbn(eid)
            if not dry and Book.objects.filter(isbn=isbn).exists():
                self.stdout.write(
                    self.style.NOTICE(f"  已存在，跳过 {isbn} (ebook id {eid})")
                )
                skipped += 1
                time.sleep(0.05)
                continue

            url = E_BOOK_URL.format(eid=eid)
            try:
                time.sleep(delay)
                html = _fetch_text(session, url)
            except OSError as e:
                self.stdout.write(
                    self.style.ERROR(f"  无法打开 {url}: {e}（可检查网络与 HTTPS）")
                )
                failed += 1
                continue

            meta = _parse_ebook_page(html, eid)
            title = (meta.get("title") or "")[:200]
            author = (meta.get("author") or "未知")[:200]
            description = meta.get("description") or ""
            self.stdout.write(
                f"  → ebook {eid}: {title[:50]!r} / 作者: {author[:30]!r}…"
            )

            if dry:
                created += 0
                continue

            b = Book(
                title=title,
                isbn=isbn,
                author=author,
                category=cat,
                publisher="Project Gutenberg (web)",
                description=description,
                total_copies=1,
                available_copies=1,
            )
            b.save()
            if not no_cover:
                c_from = meta.get("cover_url_from_page")
                blob = _download_cover(session, eid, c_from)
                if blob:
                    data, fname = blob[0], blob[1]
                    b.cover.save(fname, ContentFile(data), save=True)
                    self.stdout.write(self.style.SUCCESS("     已保存封面"))
            self.stdout.write(self.style.SUCCESS(f"  已入库: {isbn} — {title[:40]}"))
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"完成。新建 {created} 本，跳过 {skipped}，失败 {failed} 。"
            )
        )
