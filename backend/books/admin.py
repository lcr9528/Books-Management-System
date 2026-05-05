from django.contrib import admin

from .models import (
    Book,
    BookChapter,
    BookReview,
    BookReviewComment,
    BookReviewLike,
    BorrowRecord,
    Category,
    Notification,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    list_display = ("id", "name")


class BookChapterInline(admin.TabularInline):
    model = BookChapter
    extra = 0
    ordering = ("order", "id")


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    inlines = (BookChapterInline,)
    list_display = (
        "id",
        "title",
        "isbn",
        "author",
        "category",
        "total_copies",
        "available_copies",
        "cover",
    )
    list_filter = ("category",)
    search_fields = ("title", "isbn", "author", "publisher")
    raw_id_fields = ("category",)


@admin.register(BookReviewLike)
class BookReviewLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "review", "user", "created_at")
    raw_id_fields = ("review", "user")


@admin.register(BookReviewComment)
class BookReviewCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "review", "user", "parent_id", "created_at")
    raw_id_fields = ("review", "user", "parent")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient", "kind", "actor", "is_read", "created_at")
    list_filter = ("kind", "is_read")
    raw_id_fields = ("recipient", "actor", "book", "book_review", "comment")


@admin.register(BookReview)
class BookReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "book", "user", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("content", "book__title", "user__username")
    raw_id_fields = ("book", "user")


@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "book", "borrowed_at", "due_at", "returned_at", "status")
    list_filter = ("status",)
    raw_id_fields = ("user", "book")
    # 不使用 date_hierarchy：MySQL 若未导入系统时区表，与 USE_TZ 组合会在列表页报错。
