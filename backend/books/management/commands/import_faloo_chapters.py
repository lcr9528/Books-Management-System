"""
将飞卢爬虫导出目录中的章节 .txt 批量写入 BookChapter（须已存在对应 Book，ISBN=FL+书号）。

优先使用 meta.json 的 chapters_fetched（顺序与标题与爬虫一致）；若无该字段则按
chapters/ 下「数字前缀_标题.txt」文件名排序导入。

用法（在 backend 目录）:
  python manage.py import_faloo_chapters --path ..\\faloo_export
  python manage.py import_faloo_chapters --path ..\\faloo_export\\novel_1120020
  python manage.py import_faloo_chapters --path ..\\faloo_export --dry-run
  python manage.py import_faloo_chapters --path ..\\faloo_export\\novel_1120020 --replace
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from django.db import transaction
from django.core.management.base import BaseCommand

from books.models import Book, BookChapter

_CHAPTER_TXT = re.compile(r"^(\d+)_(.+)\.txt$", re.IGNORECASE)


def _export_root_for(base: Path, novel_dir: Path) -> Path:
    base = base.resolve()
    if base.name.startswith("novel_") and base.is_dir():
        return base.parent
    return base


def _novel_dirs(path: Path) -> list[Path]:
    """含 meta.json 的 novel_*，或单目录 novel_* 且仅有 chapters/*.txt。"""
    path = path.resolve()
    if path.is_dir() and path.name.startswith("novel_"):
        if (path / "meta.json").is_file():
            return [path]
        chap = path / "chapters"
        if chap.is_dir() and any(chap.glob("*.txt")):
            return [path]
        return []
    return sorted(
        p
        for p in path.iterdir()
        if p.is_dir()
        and p.name.startswith("novel_")
        and (
            (p / "meta.json").is_file()
            or (
                (p / "chapters").is_dir()
                and any((p / "chapters").glob("*.txt"))
            )
        )
    )


def _isbn_for(novel_id: str) -> str:
    return f"FL{novel_id}"[:20]


def _strip_novel_dir_name(name: str) -> str:
    """目录名去掉 novel_ 前缀（兼容 Python 3.8，勿用 str.removeprefix）。"""
    return name[6:] if name.startswith("novel_") else name


def _novel_id_from_dir(novel_dir: Path, meta: dict[str, Any] | None) -> str:
    if meta and meta.get("novel_id"):
        return str(meta["novel_id"]).strip()
    return _strip_novel_dir_name(novel_dir.name)


def _rows_from_meta(
    export_root: Path, meta: dict[str, Any]
) -> list[tuple[int, str, Path]]:
    items = meta.get("chapters_fetched") or []
    rows: list[tuple[int, str, Path]] = []
    for row in sorted(
        items,
        key=lambda x: (
            int(x.get("sort_order") or 0),
            int(x.get("index") or 0),
        ),
    ):
        rel = row.get("file")
        if not rel:
            continue
        path = export_root / str(rel).replace("\\", "/")
        order = int(row.get("sort_order") or row.get("index") or len(rows) + 1)
        title = (row.get("toc_title") or row.get("page_title") or "").strip()
        if not title:
            title = f"第{row.get('index', order)}章"
        title = title[:300]
        rows.append((order, title, path))
    return rows


def _rows_from_chapter_dir(chap_dir: Path) -> list[tuple[int, str, Path]]:
    rows: list[tuple[int, str, Path]] = []
    for p in sorted(chap_dir.glob("*.txt"), key=lambda x: x.name.lower()):
        m = _CHAPTER_TXT.match(p.name)
        if not m:
            continue
        order = int(m.group(1))
        title = m.group(2).replace("_", " ").strip() or f"第{order}节"
        title = title[:300]
        rows.append((order, title, p))
    rows.sort(key=lambda x: (x[0], x[2].name))
    return rows


def _build_plan(
    novel_dir: Path, export_root: Path, meta: dict[str, Any] | None
) -> list[tuple[int, str, Path]]:
    if meta and meta.get("chapters_fetched"):
        return _rows_from_meta(export_root, meta)
    chap_dir = novel_dir / "chapters"
    if chap_dir.is_dir():
        return _rows_from_chapter_dir(chap_dir)
    return []


class Command(BaseCommand):
    help = "从飞卢导出目录批量导入章节到 BookChapter（图书须已存在）。"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--path",
            type=str,
            required=True,
            help="faloo_export 根目录，或单个 novel_{书号} 目录",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只统计将要写入的章节数，不写库",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="导入前删除该书已有全部章节（慎用）",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        root = Path(options["path"]).expanduser()
        dry = bool(options["dry_run"])
        replace = bool(options["replace"])

        if not root.is_dir():
            self.stderr.write(self.style.ERROR(f"路径不存在或不是目录：{root}"))
            return

        dirs = _novel_dirs(root)
        if not dirs:
            self.stderr.write(
                self.style.WARNING(
                    f"未找到可导入的 novel_*（需 meta.json 或 chapters/*.txt）：{root}"
                )
            )
            return

        total_created = 0
        skipped_books = 0
        skipped_rows = 0
        missing_book = 0

        for novel_dir in dirs:
            export_root = _export_root_for(root, novel_dir)
            meta: dict[str, Any] | None = None
            meta_path = novel_dir / "meta.json"
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as e:
                    self.stderr.write(
                        self.style.ERROR(f"{novel_dir.name}: 读取 meta.json 失败: {e}")
                    )
                    continue

            novel_id = _novel_id_from_dir(novel_dir, meta)
            isbn = _isbn_for(novel_id)
            plan = _build_plan(novel_dir, export_root, meta)
            if not plan:
                self.stdout.write(
                    self.style.WARNING(f"{novel_dir.name}: 无章节文件，跳过。")
                )
                continue

            book = Book.objects.filter(isbn=isbn).first()
            if not book:
                self.stdout.write(
                    self.style.WARNING(
                        f"{novel_dir.name}: 未找到 ISBN={isbn} 的图书，请先 import_faloo_export。"
                    )
                )
                missing_book += 1
                continue

            if book.chapters.exists() and not replace:
                self.stdout.write(
                    self.style.NOTICE(
                        f"「{book.title}」({isbn}) 已有 {book.chapters.count()} 章，跳过（加 --replace 可覆盖）。"
                    )
                )
                skipped_books += 1
                continue

            # 去重 order：同一 order 保留先出现的一条
            seen_order: set[int] = set()
            unique_plan: list[tuple[int, str, Path]] = []
            for order, title, path in plan:
                if order in seen_order:
                    skipped_rows += 1
                    continue
                seen_order.add(order)
                unique_plan.append((order, title, path))

            to_write: list[tuple[int, str, str]] = []
            for order, title, path in unique_plan:
                if not path.is_file():
                    self.stdout.write(
                        self.style.WARNING(f"  缺失文件，跳过: {path.name}")
                    )
                    skipped_rows += 1
                    continue
                try:
                    body = path.read_text(encoding="utf-8").strip()
                except OSError as e:
                    self.stdout.write(
                        self.style.WARNING(f"  读取失败 {path.name}: {e}")
                    )
                    skipped_rows += 1
                    continue
                if not body:
                    skipped_rows += 1
                    continue
                to_write.append((order, title, body))

            self.stdout.write(
                f"  → {isbn} 「{book.title[:40]}」: 准备写入 {len(to_write)} 章"
            )

            if dry or not to_write:
                total_created += len(to_write)
                continue

            with transaction.atomic():
                if replace:
                    BookChapter.objects.filter(book=book).delete()
                objs = [
                    BookChapter(
                        book=book,
                        order=o,
                        title=t,
                        content=c,
                    )
                    for o, t, c in to_write
                ]
                BookChapter.objects.bulk_create(objs, batch_size=300)

            total_created += len(to_write)
            self.stdout.write(
                self.style.SUCCESS(f"     已写入 {len(to_write)} 章。")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"完成。写入章节条数累计 {total_created}（dry-run 时为计划数）；"
                f"跳过已有章节的书 {skipped_books} 本；缺书目 {missing_book} 本；"
                f"跳过缺文件/空文件/重复 order {skipped_rows} 条。"
            )
        )
        if dry:
            self.stdout.write(self.style.WARNING("以上为 DRY-RUN，未写入数据库。"))
