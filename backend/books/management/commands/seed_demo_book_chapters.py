"""
为指定 ISBN 的图书写入几条示例章节（公版书 Moby Dick 试读片段），便于验收详情页「目录」功能。
若该书已有章节则跳过。用法：
  python manage.py seed_demo_book_chapters
  python manage.py seed_demo_book_chapters --isbn PG0002701
"""
from django.core.management.base import BaseCommand

from books.models import Book, BookChapter

MOBY_ISBN = "PG0002701"
SAMPLES = [
    (
        1,
        "序曲：人以海洋为邻（节选）",
        """Call me Ishmael. Some years ago—never mind how long precisely—having little or no money in my purse, and nothing particular to interest me on shore, I thought I would sail about a little and see the watery part of the world.

（以上为《白鲸》开篇名句的英文原文节选，置于正文样式预览；完整作品见 Project Gutenberg。）""",
    ),
    (
        2,
        "第二章（节选）",
        """As I sat there at my ease, cross-legged on the deck; after the bitter exertion at the windlass; under a blue tranquil sky; the ship under indolent sail, and gliding so quietly along…

（节选示意：章节正文支持长文本滚动阅读。）""",
    ),
    (
        3,
        "第三章（节选）",
        """Upon waking next morning, I found Queepeg sitting close beside me…

（如需替换为完整译本或自有版权正文，请在后台「图书」内编辑章节条目。）""",
    ),
]


class Command(BaseCommand):
    help = "写入示例章节（默认 Moby Dick / PG0002701），便于详情页目录验收"

    def add_arguments(self, parser) -> None:
        parser.add_argument("--isbn", type=str, default=MOBY_ISBN, help="目标图书 ISBN")

    def handle(self, *args, **options) -> None:
        isbn = (options.get("isbn") or MOBY_ISBN)[:20].strip()
        book = Book.objects.filter(isbn=isbn).first()
        if not book:
            self.stderr.write(self.style.ERROR(f"未找到 ISBN={isbn} 的图书，请先导入该书。"))
            return
        if book.chapters.exists():
            self.stdout.write(self.style.NOTICE("该书已有章节，跳过。"))
            return
        for order, title, content in SAMPLES:
            BookChapter.objects.create(
                book=book, order=order, title=title[:300], content=content
            )
        self.stdout.write(self.style.SUCCESS(f"已为「{book.title}」写入 {len(SAMPLES)} 条示例章节。"))
