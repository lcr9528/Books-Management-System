# Generated manually for BookChapter model

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("books", "0002_book_cover"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookChapter",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.PositiveIntegerField(default=1, verbose_name="排序")),
                ("title", models.CharField(max_length=300, verbose_name="章节标题")),
                ("content", models.TextField(verbose_name="正文")),
                (
                    "book",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chapters",
                        to="books.book",
                        verbose_name="图书",
                    ),
                ),
            ],
            options={
                "verbose_name": "图书章节",
                "verbose_name_plural": "图书章节",
                "ordering": ("book", "order", "id"),
                "indexes": [
                    models.Index(fields=["book", "order"], name="books_bookchapter_book_ord_idx"),
                ],
            },
        ),
    ]
