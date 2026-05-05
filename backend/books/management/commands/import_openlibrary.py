"""
从 Open Library（openlibrary.org）的公开 JSON API 拉取书目、简介与封面，
写入本系统的 Category / Book 表。

说明：这是受官网允许的 API 用法，不是对任意网站做 HTML 抓取；
对豆瓣等站点有反爬/版权限制，本命令未实现。
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from books.models import Book, Category

OPEN_LIBRARY_SEARCH = "https://openlibrary.org/search.json"
OPEN_LIBRARY_BASE = "https://openlibrary.org"
COVER_BY_ID = "https://covers.openlibrary.org/b/id/{}-L.jpg"
USER_AGENT = "LibraryDRFDemo/1.0 (Django management command; +local)"


def _clean_isbn(raw: str) -> str:
    s = re.sub(r"[^0-9Xx]", "", str(raw))
    if len(s) > 20:
        s = s[:20]
    return s


def _work_to_description(work: Dict[str, Any]) -> str:
    d = work.get("description")
    if d is None:
        return ""
    if isinstance(d, str):
        return d.strip()[:10000]
    if isinstance(d, dict) and "value" in d:
        return str(d["value"]).strip()[:10000]
    return (str(d) or "").strip()[:10000]


def _pick_isbn(doc: Dict[str, Any], work_key: str) -> str:
    isbns: List[str] = doc.get("isbn") or []
    for i in isbns:
        c = _clean_isbn(i)
        if 10 <= len(c) <= 20:
            return c
    for i in isbns:
        c = _clean_isbn(i)
        if c:
            return c[:20]
    part = (work_key or "OLunknown").rstrip("/").split("/")[-1]
    part = re.sub(r"[^A-Za-z0-9]", "", part) or "X"
    if not part.upper().startswith("OL"):
        part = "OL" + part
    return part[:20]


def _title_author_publisher(doc: Dict[str, Any]):
    title = (doc.get("title") or "无标题")[:200]
    authors: List[str] = doc.get("author_name") or []
    if not authors and "author_name" in doc and isinstance(doc["author_name"], str):
        authors = [doc["author_name"]]
    author = ", ".join(authors[:4])[:200] if authors else "未知"
    pub_list = doc.get("publisher")
    if isinstance(pub_list, list) and pub_list:
        publisher = (pub_list[0] or "")[:200]
    else:
        publisher = (doc.get("publishers") or [""])
        if isinstance(publisher, list) and publisher:
            publisher = (str(publisher[0]) or "")[:200]
        else:
            publisher = ""
    return title, author, publisher


def _build_search_q(query: str, lang: str) -> str:
    q = query.strip() or "fiction"
    if lang and lang.strip():
        return f"{q} language:{lang.strip()}"
    return q


class Command(BaseCommand):
    help = "从 Open Library API 导入图书（简介 + 封面到本地 media）"

    def add_arguments(self, parser) -> None:
        parser.add_argument("query", nargs="?", type=str, default="fiction", help="搜索词，可写 subject:science 等")
        parser.add_argument("--limit", type=int, default=10, help="最多导入条数")
        parser.add_argument("--lang", type=str, default="", help="语言码，如 eng、chi；不填不限制")
        parser.add_argument("--category", type=str, default="网络导入", help="分类名，不存在会创建")
        parser.add_argument("--delay", type=float, default=0.35, help="请求间隔（秒）")
        parser.add_argument("--dry-run", action="store_true", help="只打印，不写入")
        parser.add_argument("--no-cover", action="store_true", help="不下载封面")

    def handle(self, *args, **options) -> None:
        query = _build_search_q(options["query"] or "fiction", options.get("lang") or "")
        limit = max(1, int(options["limit"] or 10))
        category_name = (options.get("category") or "网络导入")[:100]
        delay = float(options.get("delay") or 0.35)
        dry = bool(options.get("dry_run"))
        no_cover = bool(options.get("no_cover"))

        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        params: Dict[str, Any] = {"q": query, "limit": limit}
        try:
            r = session.get(OPEN_LIBRARY_SEARCH, params=params, timeout=40)
            r.raise_for_status()
        except OSError as e:
            self.stderr.write(
                f"无法连接 Open Library（{e}）。请检查网络、代理与防火墙，稍后再试。"
            )
            return
        payload = r.json()
        docs: List[Dict[str, Any]] = payload.get("docs") or []

        if not docs:
            self.stdout.write(self.style.WARNING("未找到结果，可换个关键词或取消 --lang 再试。"))
            return

        self.stdout.write(
            f"Open Library 返回 {len(docs)} 条候选（关键词: {query!r}，最多取 {limit} 条）"
        )

        created, skipped, failed = 0, 0, 0
        for doc in docs[:limit]:
            work_key = (doc.get("key") or "").strip()
            if not work_key.startswith("/works/"):
                skipped += 1
                continue
            isbn = _pick_isbn(doc, work_key)
            if Book.objects.filter(isbn=isbn).exists():
                self.stdout.write(self.style.NOTICE(f"  已存在，跳过: {isbn} {doc.get('title', '')!r}"))
                skipped += 1
                continue
            title, author, publisher = _title_author_publisher(doc)
            if dry:
                self.stdout.write(
                    f"  [DRY] {isbn!r} | {title!r} | {author!r} | cover_i={doc.get('cover_i')!r}"
                )
                time.sleep(0.05)
                continue

            time.sleep(delay)
            work_url = f"{OPEN_LIBRARY_BASE}{work_key}.json"
            try:
                wr = session.get(work_url, timeout=40)
                wr.raise_for_status()
                work = wr.json()
            except OSError as e:
                self.stdout.write(self.style.ERROR(f"  拉取作品失败 {work_key}: {e}"))
                failed += 1
                continue

            description = _work_to_description(work) or ""
            if not description:
                fs = doc.get("first_sentence")
                if isinstance(fs, str):
                    description = fs[:2000]
                elif isinstance(fs, list) and fs:
                    description = (fs[0] or "")[:2000]

            cat, _ = Category.objects.get_or_create(name=category_name)
            book = Book(
                title=title,
                isbn=isbn,
                author=author,
                category=cat,
                publisher=publisher,
                description=description,
                total_copies=1,
                available_copies=1,
            )
            book.save()

            cover_id = doc.get("cover_i")
            if (not no_cover) and cover_id and isinstance(cover_id, int):
                time.sleep(max(0.1, delay * 0.4))
                cu = COVER_BY_ID.format(cover_id)
                try:
                    cr = session.get(cu, timeout=40)
                    if cr.status_code == 200 and cr.content and len(cr.content) > 800:
                        name = f"{re.sub(r'[^0-9A-Za-z]', '_', isbn)[:32]}.jpg"
                        book.cover.save(name, ContentFile(cr.content), save=True)
                except OSError as e:
                    self.stdout.write(self.style.WARNING(f"  封面临时失败（已保存书目）: {e}"))

            self.stdout.write(self.style.SUCCESS(f"  已导入: {isbn} — {book.title[:60]}"))
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"完成：新增 {created} 本，跳过 {skipped}，失败 {failed}。"
                f" 本地封面目录见 MEDIA_ROOT / book_covers/。"
            )
        )
