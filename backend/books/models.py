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
