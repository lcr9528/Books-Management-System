from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField("分类名", max_length=100, unique=True)

    class Meta:
        verbose_name = "分类"
        verbose_name_plural = "分类"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    title = models.CharField("书名", max_length=200)
    isbn = models.CharField("ISBN", max_length=20, unique=True, db_index=True)
    author = models.CharField("作者", max_length=200)
    category = models.ForeignKey(
        Category,
        verbose_name="分类",
        on_delete=models.PROTECT,
        related_name="books",
    )
    publisher = models.CharField("出版社", max_length=200, blank=True, default="")
    description = models.TextField("简介", blank=True, default="")
    cover = models.ImageField("封面", upload_to="book_covers", blank=True, null=True)
    total_copies = models.PositiveIntegerField("总册数", default=1)
    available_copies = models.PositiveIntegerField("在架册数", default=1)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "图书"
        verbose_name_plural = "图书"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.title} ({self.isbn})"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.total_copies < 1:
            raise ValidationError({"total_copies": "总册数至少为 1。"})
        if self.available_copies > self.total_copies:
            raise ValidationError({"available_copies": "在架册数不能大于总册数。"})


class BookChapter(models.Model):
    """图书正文章节（用于详情页在线阅读；无章节时前端显示为空列表）。"""

    book = models.ForeignKey(
        Book,
        verbose_name="图书",
        on_delete=models.CASCADE,
        related_name="chapters",
    )
    order = models.PositiveIntegerField("排序", default=1)
    title = models.CharField("章节标题", max_length=300)
    content = models.TextField("正文")

    class Meta:
        verbose_name = "图书章节"
        verbose_name_plural = "图书章节"
        ordering = ("book", "order", "id")
        indexes = [
            models.Index(fields=("book", "order")),
        ]

    def __str__(self) -> str:
        return f"{self.book_id} #{self.order} {self.title[:40]}"


class BorrowRecord(models.Model):
    class Status(models.TextChoices):
        BORROWED = "borrowed", "在借"
        RETURNED = "returned", "已归还"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="borrows",
        verbose_name="读者",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="borrow_records",
        verbose_name="图书",
    )
    borrowed_at = models.DateTimeField("借出时间", auto_now_add=True)
    due_at = models.DateTimeField("应还时间")
    returned_at = models.DateTimeField("实际归还", null=True, blank=True)
    status = models.CharField(
        "状态",
        max_length=20,
        choices=Status.choices,
        default=Status.BORROWED,
    )

    class Meta:
        verbose_name = "借阅记录"
        verbose_name_plural = "借阅记录"
        ordering = ("-borrowed_at",)
        # 同一用户同一本「在借」不重复在 API 中校验，避免不同数据库对条件唯一约束支持差异

    def __str__(self) -> str:
        return f"{self.user_id} {self.book_id} {self.status}"

    @property
    def is_overdue(self) -> bool:
        if self.status != self.Status.BORROWED or self.returned_at:
            return False
        return timezone.now() > self.due_at


class BookReview(models.Model):
    """图书书评：每用户每书至多一条；仅允许曾有过借阅记录的用户发表（见校验逻辑）。"""

    book = models.ForeignKey(
        Book,
        verbose_name="图书",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="book_reviews",
    )
    rating = models.PositiveSmallIntegerField(
        "评分",
        null=True,
        blank=True,
        help_text="1～5 星，可与文字择一或并存",
    )
    content = models.TextField("书评正文", blank=True, default="")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "图书书评"
        verbose_name_plural = "图书书评"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("book", "user"),
                name="uniq_bookreview_book_user",
            ),
        ]
        indexes = [
            models.Index(fields=("book", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.book_id} ← {self.user_id}"


class BookReviewLike(models.Model):
    """书评点赞：每用户对每条书评至多点赞一次（重复请求视为取消）。"""

    review = models.ForeignKey(
        BookReview,
        verbose_name="书评",
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="book_review_likes",
    )
    created_at = models.DateTimeField("点赞时间", auto_now_add=True)

    class Meta:
        verbose_name = "书评点赞"
        verbose_name_plural = "书评点赞"
        constraints = [
            models.UniqueConstraint(
                fields=("review", "user"),
                name="uniq_bookreviewlike_review_user",
            ),
        ]


class BookReviewComment(models.Model):
    """书评下的评论；parent 为空表示直接评论书评，否则为回复某条评论。"""

    review = models.ForeignKey(
        BookReview,
        verbose_name="书评",
        on_delete=models.CASCADE,
        related_name="review_comments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="book_review_comments",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="回复的评论",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
    )
    content = models.TextField("内容", max_length=2000)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "书评评论"
        verbose_name_plural = "书评评论"
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=("review", "parent", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.review_id} ← {self.user_id}"


class BookReviewCommentLike(models.Model):
    """评论点赞：每用户对每条评论至多点赞一次。"""

    comment = models.ForeignKey(
        BookReviewComment,
        verbose_name="评论",
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.CASCADE,
        related_name="book_review_comment_likes",
    )
    created_at = models.DateTimeField("点赞时间", auto_now_add=True)

    class Meta:
        verbose_name = "书评评论点赞"
        verbose_name_plural = "书评评论点赞"
        constraints = [
            models.UniqueConstraint(
                fields=("comment", "user"),
                name="uniq_bookreviewcommentlike_comment_user",
            ),
        ]


class Notification(models.Model):
    """站内通知（书评点赞、书评评论、回复评论）。"""

    class Kind(models.TextChoices):
        REVIEW_LIKED = "review_liked", "书评被点赞"
        REVIEW_COMMENTED = "review_commented", "书评被评论"
        COMMENT_REPLIED = "comment_replied", "评论被回复"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="接收者",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="操作者",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_sent",
    )
    kind = models.CharField("类型", max_length=32, choices=Kind.choices)
    book = models.ForeignKey(
        Book,
        verbose_name="图书",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    book_review = models.ForeignKey(
        BookReview,
        verbose_name="书评",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    comment = models.ForeignKey(
        BookReviewComment,
        verbose_name="相关评论",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    preview = models.CharField("摘要", max_length=200, blank=True)
    is_read = models.BooleanField("已读", default=False)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "站内通知"
        verbose_name_plural = "站内通知"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("recipient", "is_read", "-created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.recipient_id} ← {self.kind}"
