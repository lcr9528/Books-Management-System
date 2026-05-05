# Generated manually for BookReviewCommentLike

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("books", "0005_review_like_comment_notification"),
    ]

    operations = [
        migrations.CreateModel(
            name="BookReviewCommentLike",
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
                    "comment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="likes",
                        to="books.bookreviewcomment",
                        verbose_name="评论",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="book_review_comment_likes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "书评评论点赞",
                "verbose_name_plural": "书评评论点赞",
            },
        ),
        migrations.AddConstraint(
            model_name="bookreviewcommentlike",
            constraint=models.UniqueConstraint(
                fields=("comment", "user"),
                name="uniq_bookreviewcommentlike_comment_user",
            ),
        ),
    ]
