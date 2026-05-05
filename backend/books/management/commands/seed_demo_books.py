"""
向数据库写入若干条固定示例图书记录（不访问外网，可离线使用）。
若已存在相同 ISBN 会跳过，可重复执行。
"""
from django.core.management.base import BaseCommand

from books.models import Book, Category

DEMO = [
    {
        "isbn": "9787111544937",
        "title": "Django 企业开发实战",
        "author": "胡阳",
        "publisher": "机械工业出版社",
        "description": "基于 Django 与 DRF 搭建 Web 项目的常见模式与实践要点（示例数据）。",
    },
    {
        "isbn": "9787111558422",
        "title": "JavaScript 高级程序设计",
        "author": "Nicholas C. Zakas",
        "publisher": "人民邮电出版社",
        "description": "经典前端参考书，系统讲解语言核心与 DOM/BOM（示例数据）。",
    },
    {
        "isbn": "9787115538998",
        "title": "深入理解计算机系统",
        "author": "Randal E. Bryant",
        "publisher": "机械工业出版社",
        "description": "从程序视角理解硬件、体系结构与系统软件（示例数据）。",
    },
    {
        "isbn": "9787302510926",
        "title": "Redis 深度历险：核心原理与应用实践",
        "author": "钱文品",
        "publisher": "清华大学出版社",
        "description": "缓存、持久化、集群等主题的入门与实践（示例数据）。",
    },
    {
        "isbn": "9787115490925",
        "title": "流畅的 Python",
        "author": "Luciano Ramalho",
        "publisher": "人民邮电出版社",
        "description": "Python 语言特性、数据模型与元编程（示例数据）。",
    },
    {
        "isbn": "9787111213826",
        "title": "设计模式：可复用面向对象软件的基础",
        "author": "Erich Gamma 等",
        "publisher": "机械工业出版社",
        "description": "GoF 设计模式，面向对象设计经典（示例数据）。",
    },
]


class Command(BaseCommand):
    help = "写入离线图书记录（示例），不依赖外网与 Open Library"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--category",
            type=str,
            default="示例书目",
            help="分类名，没有则自动创建",
        )
        parser.add_argument(
            "--copies",
            type=int,
            default=2,
            help="每本总册与在架册数（均设为该值）",
        )

    def handle(self, *args, **options) -> None:
        name = (options.get("category") or "示例书目")[:100]
        copies = max(1, int(options.get("copies") or 2))
        cat, _ = Category.objects.get_or_create(name=name)

        created, skipped = 0, 0
        for row in DEMO:
            isbn = row["isbn"][:20]
            if Book.objects.filter(isbn=isbn).exists():
                self.stdout.write(self.style.NOTICE(f"已存在，跳过: {isbn} {row['title']!r}"))
                skipped += 1
                continue
            Book.objects.create(
                title=row["title"][:200],
                isbn=isbn,
                author=row["author"][:200],
                category=cat,
                publisher=(row.get("publisher") or "")[:200],
                description=(row.get("description") or "")[:10000],
                total_copies=copies,
                available_copies=copies,
            )
            self.stdout.write(self.style.SUCCESS(f"已创建: {isbn} — {row['title'][:40]}"))
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"完成：新建 {created} 本，跳过 {skipped} 本。请刷新前端「图书列表」。"
            )
        )
