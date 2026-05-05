# Generated manually

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("books", "0004_book_review"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookReviewLike",
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
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="点赞时间")),
                (
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="likes",
                        to="books.bookreview",
                        verbose_name="书评",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="book_review_likes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "书评点赞",
                "verbose_name_plural": "书评点赞",
            },
        ),
        migrations.CreateModel(
            name="BookReviewComment",
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
                ("content", models.TextField(max_length=2000, verbose_name="内容")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="replies",
                        to="books.bookreviewcomment",
                        verbose_name="回复的评论",
                    ),
                ),
                (
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="review_comments",
                        to="books.bookreview",
                        verbose_name="书评",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="book_review_comments",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "书评评论",
                "verbose_name_plural": "书评评论",
                "ordering": ("created_at",),
            },
        ),
        migrations.CreateModel(
            name="Notification",
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
                    "kind",
                    models.CharField(
                        choices=[
                            ("review_liked", "书评被点赞"),
                            ("review_commented", "书评被评论"),
                            ("comment_replied", "评论被回复"),
                        ],
                        max_length=32,
                        verbose_name="类型",
                    ),
                ),
                ("preview", models.CharField(blank=True, max_length=200, verbose_name="摘要")),
                ("is_read", models.BooleanField(default=False, verbose_name="已读")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notifications_sent",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="操作者",
                    ),
                ),
                (
                    "book",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="books.book",
                        verbose_name="图书",
                    ),
                ),
                (
                    "book_review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="books.bookreview",
                        verbose_name="书评",
                    ),
                ),
                (
                    "comment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="books.bookreviewcomment",
                        verbose_name="相关评论",
                    ),
                ),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="接收者",
                    ),
                ),
            ],
            options={
                "verbose_name": "站内通知",
                "verbose_name_plural": "站内通知",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="bookreviewlike",
            constraint=models.UniqueConstraint(
                fields=("review", "user"),
                name="uniq_bookreviewlike_review_user",
            ),
        ),
        migrations.AddIndex(
            model_name="bookreviewcomment",
            index=models.Index(
                fields=("review", "parent", "created_at"),
                name="books_bookre_review__idx",
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(
                fields=("recipient", "is_read", "created_at"),
                name="books_notifi_recipie_idx",
            ),
        ),
    ]
