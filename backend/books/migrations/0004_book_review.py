# Generated manually for BookReview model

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("books", "0003_bookchapter"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookReview",
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
                (
                    "rating",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        help_text="1～5 星，可与文字择一或并存",
                        null=True,
                        verbose_name="评分",
                    ),
                ),
                (
                    "content",
                    models.TextField(blank=True, default="", verbose_name="书评正文"),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="创建时间"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="更新时间"),
                ),
                (
                    "book",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reviews",
                        to="books.book",
                        verbose_name="图书",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="book_reviews",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "图书书评",
                "verbose_name_plural": "图书书评",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="bookreview",
            index=models.Index(
                fields=["book", "created_at"],
                name="books_br_book_created_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="bookreview",
            constraint=models.UniqueConstraint(
                fields=("book", "user"),
                name="uniq_bookreview_book_user",
            ),
        ),
    ]
