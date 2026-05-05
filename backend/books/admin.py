from django.contrib import admin

from .models import Book, BookChapter, BorrowRecord, Category


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


@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "book", "borrowed_at", "due_at", "returned_at", "status")
    list_filter = ("status",)
    raw_id_fields = ("user", "book")
    # 不使用 date_hierarchy：MySQL 若未导入系统时区表，与 USE_TZ 组合会在列表页报错。
