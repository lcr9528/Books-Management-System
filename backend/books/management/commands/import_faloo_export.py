"""
将 faloo_novel_spider.py 导出目录（novel_{书号}/）中的图书元数据、简介与封面写入本系统。

说明：
- 每条书目一条 Book；ISBN 使用内部前缀 FL + 飞卢书号（与真实纸质 ISBN 区分）。
- 章节 .txt 不会随本命令入库；书目入库后请用 import_faloo_chapters 批量写入 BookChapter。
- 若 ISBN 已存在则跳过（可加 --force-update 仅更新简介/封面，见下文）。
- meta.json 中含爬虫写入的 category_main / category_sub（作品子类优先）时，自动 get_or_create 分类并归类；缺省时使用 --category。

用法示例（在项目 backend 目录且已激活虚拟环境）:
  python manage.py import_faloo_export --path C:\\Users\\xxx\\Desktop\\DRF\\faloo_export
  python manage.py import_faloo_export --path ..\\faloo_export\\novel_1525878 --category 同人小说
  python manage.py import_faloo_export --path ..\\faloo_export --dry-run
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.files import File
from django.core.management.base import BaseCommand

from books.models import Book, Category


def _export_root_for(base: Path, novel_dir: Path) -> Path:
    """meta.json 内相对路径相对于爬虫 --out 根目录。"""
    base = base.resolve()
    if base.name.startswith("novel_") and (base / "meta.json").is_file():
        return base.parent
    return base


def _novel_dirs(path: Path) -> list[Path]:
    path = path.resolve()
    if path.is_dir() and path.name.startswith("novel_") and (path / "meta.json").is_file():
        return [path]
    return sorted(
        p
        for p in path.iterdir()
        if p.is_dir() and p.name.startswith("novel_") and (p / "meta.json").is_file()
    )


def _isbn_for(novel_id: str) -> str:
    s = f"FL{novel_id}"
    return s[:20]


def _strip_novel_dir_name(name: str) -> str:
    """目录名去掉 novel_ 前缀（兼容 Python 3.8，勿用 str.removeprefix）。"""
    return name[6:] if name.startswith("novel_") else name


def _import_category_name(meta: dict[str, Any], fallback: str) -> str:
    """优先用书详情子类（列表标签），其次主类；再无则用命令行 --category。"""
    sub = (meta.get("faloo_category_sub") or meta.get("category_sub") or "").strip()
    main = (meta.get("faloo_category_main") or meta.get("category_main") or "").strip()
    if sub:
        return sub[:100]
    if main:
        return main[:100]
    fb = (fallback or "").strip() or "网络连载（飞卢导入）"
    return fb[:100]


class Command(BaseCommand):
    help = "从飞卢爬虫导出目录批量导入图书（元数据、简介.txt、封面文件）。"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--path",
            type=str,
            required=True,
            help="faloo_export 根目录，或单个 novel_{书号} 目录",
        )
        parser.add_argument(
            "--category",
            type=str,
            default="网络连载（飞卢导入）",
            help="meta 未含飞卢分类时的默认分类名；不存在则自动创建",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只打印将要导入的书目，不写数据库与媒体文件",
        )
        parser.add_argument(
            "--force-update",
            action="store_true",
            help="ISBN 已存在时更新书名、作者、简介、封面（慎用）",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        root = Path(options["path"]).expanduser()
        if not root.is_dir():
            self.stderr.write(self.style.ERROR(f"路径不存在或不是目录：{root}"))
            return

        cat_name = (options["category"] or "")[:100].strip() or "网络连载（飞卢导入）"
        dry = bool(options["dry_run"])
        force_update = bool(options["force_update"])

        dirs = _novel_dirs(root)
        if not dirs:
            self.stderr.write(
                self.style.WARNING(f"未找到含 meta.json 的 novel_* 目录：{root}")
            )
            return

        # 批量根目录下若存在 novel_* 却无 meta.json，不会进入 dirs，这里单独提示以免误以为「漏导」
        if root.is_dir() and not (
            root.name.startswith("novel_") and (root / "meta.json").is_file()
        ):
            picked = {p.resolve() for p in dirs}
            for p in sorted(root.iterdir()):
                if (
                    p.is_dir()
                    and p.name.startswith("novel_")
                    and p.resolve() not in picked
                ):
                    self.stdout.write(
                        self.style.WARNING(
                            f"跳过 {p.name}：缺少 meta.json（仅章节或其它文件时不会被导入；请对该书重新爬虫导出或补全 meta.json）。"
                        )
                    )

        created = updated = skipped = failed = 0

        for novel_dir in dirs:
            export_root = _export_root_for(root, novel_dir)
            meta_path = novel_dir / "meta.json"
            try:
                meta: dict[str, Any] = json.loads(
                    meta_path.read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as e:
                self.stderr.write(self.style.ERROR(f"{novel_dir}: 读取 meta.json 失败: {e}"))
                failed += 1
                continue

            novel_id = str(meta.get("novel_id") or _strip_novel_dir_name(novel_dir.name))
            title = (meta.get("title") or "").strip() or novel_dir.name
            title = title[:200]
            author = (meta.get("author") or "").strip() or "佚名"
            author = author[:200]
            isbn = _isbn_for(novel_id)
            book_category_name = _import_category_name(meta, cat_name)

            intro = ""
            intro_rel = meta.get("intro_file")
            if intro_rel:
                ip = export_root / str(intro_rel).replace("\\", "/")
                if ip.is_file():
                    intro = ip.read_text(encoding="utf-8").strip()
            if not intro:
                ip2 = novel_dir / "简介.txt"
                if ip2.is_file():
                    intro = ip2.read_text(encoding="utf-8").strip()

            publisher = "飞卢小说网（导入）"

            self.stdout.write(
                f"  → {isbn} {title[:40]!r} / {author[:20]!r}  「{book_category_name}」"
            )

            existing = Book.objects.filter(isbn=isbn).first()
            if existing and not force_update:
                self.stdout.write(self.style.NOTICE(f"     已存在，跳过（--force-update 可覆盖）"))
                skipped += 1
                continue

            cover_path: Path | None = None
            cf = meta.get("cover_file")
            if cf:
                cp = export_root / str(cf).replace("\\", "/")
                if cp.is_file():
                    cover_path = cp
            if cover_path is None:
                for ext in (".jpg", ".jpeg", ".png", ".webp"):
                    cand = novel_dir / f"cover{ext}"
                    if cand.is_file():
                        cover_path = cand
                        break

            if dry:
                if existing and force_update:
                    updated += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            "     [dry-run] 将更新书目（--force-update）"
                            + (f"，并绑定封面 {cover_path.name}" if cover_path else "")
                        )
                    )
                else:
                    created += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            "     [dry-run] 将新建书目"
                            + (f"，并绑定封面 {cover_path.name}" if cover_path else "")
                        )
                    )
                continue

            cat_row, _ = Category.objects.get_or_create(name=book_category_name)

            try:
                if existing and force_update:
                    existing.title = title
                    existing.author = author
                    existing.category = cat_row
                    existing.publisher = publisher[:200]
                    existing.description = intro[:10000] if intro else ""
                    existing.save()
                    b = existing
                    updated += 1
                else:
                    b = Book.objects.create(
                        title=title,
                        isbn=isbn,
                        author=author,
                        category=cat_row,
                        publisher=publisher[:200],
                        description=(intro[:10000] if intro else ""),
                        total_copies=1,
                        available_copies=1,
                    )
                    created += 1

                if cover_path is not None:
                    with cover_path.open("rb") as fh:
                        b.cover.save(cover_path.name, File(fh), save=True)
                    self.stdout.write(self.style.SUCCESS(f"     已绑定封面 {cover_path.name}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"     写入失败: {e}"))
                failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"完成。新建 {created}，更新 {updated}，跳过 {skipped}，失败 {failed}。"
            )
        )
        if dry:
            self.stdout.write(self.style.WARNING("以上为 DRY-RUN，未写入数据库。"))
