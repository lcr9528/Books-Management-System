from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from accounts.models import User

from .models import Book, BookChapter, BorrowRecord, Category


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")


class BookListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    cover = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = (
            "id",
            "title",
            "isbn",
            "author",
            "category",
            "category_name",
            "publisher",
            "cover",
            "total_copies",
            "available_copies",
            "created_at",
        )
        read_only_fields = ("created_at", "available_copies", "total_copies")

    def get_cover(self, obj) -> Optional[str]:
        if not obj.cover:
            return None
        request = self.context.get("request")
        url = obj.cover.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class BookChapterListSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookChapter
        fields = ("id", "order", "title")


class BookChapterDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookChapter
        fields = ("id", "order", "title", "content")


class BookDetailSerializer(BookListSerializer):
    class Meta(BookListSerializer.Meta):
        fields = BookListSerializer.Meta.fields + ("description", "updated_at")
        read_only_fields = (
            "created_at",
            "available_copies",
        )


class BookWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = (
            "id",
            "title",
            "isbn",
            "author",
            "category",
            "publisher",
            "description",
            "total_copies",
        )
        read_only_fields = ("id",)

    def create(self, validated_data):
        total = validated_data.get("total_copies", 1)
        if total < 1:
            total = 1
        validated_data["total_copies"] = total
        validated_data["available_copies"] = total
        return super().create(validated_data)

    def update(self, instance, validated_data):
        old_total = instance.total_copies
        on_loan = old_total - instance.available_copies
        if "total_copies" in validated_data:
            new_total = validated_data["total_copies"]
            if new_total < 1:
                raise serializers.ValidationError({"total_copies": "总册数至少为 1。"})
            if new_total < on_loan:
                raise serializers.ValidationError(
                    {"total_copies": f"总册数不能小于已借出册数（当前已借 {on_loan} ）。"}
                )
            instance.available_copies = new_total - on_loan
        return super().update(instance, validated_data)


class BorrowRecordSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title", read_only=True)
    book_isbn = serializers.CharField(source="book.isbn", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = BorrowRecord
        fields = (
            "id",
            "user",
            "user_username",
            "book",
            "book_title",
            "book_isbn",
            "borrowed_at",
            "due_at",
            "returned_at",
            "status",
            "is_overdue",
        )
        read_only_fields = (
            "id",
            "user",
            "borrowed_at",
            "due_at",
            "returned_at",
            "status",
        )

    def get_is_overdue(self, obj: BorrowRecord) -> bool:
        return bool(obj.is_overdue)


class BorrowCreateSerializer(serializers.Serializer):
    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())
    days = serializers.IntegerField(required=False, min_value=1, max_value=90)
    due_at = serializers.DateTimeField(required=False)

    def create(self, validated_data):
        request = self.context["request"]
        user: User = request.user
        book: Book = validated_data["book"]

        if not user.is_librarian and not user.is_active:
            raise serializers.ValidationError("当前账号无法借书。")

        if book.available_copies < 1:
            raise serializers.ValidationError("该书暂无在架副本。")
        if BorrowRecord.objects.filter(
            user=user,
            book=book,
            status=BorrowRecord.Status.BORROWED,
        ).exists():
            raise serializers.ValidationError("您已借阅该书且尚未归还。")

        now = timezone.now()
        due = validated_data.get("due_at")
        if due is not None:
            if due <= now:
                raise serializers.ValidationError({"detail": "借阅时间需晚于当前时间。"})
            if due > now + timezone.timedelta(days=180):
                raise serializers.ValidationError({"detail": "借阅时间不能超过当前时间后 180 天。"})
        else:
            days = validated_data.get("days", getattr(settings, "BORROW_DAYS", 30))
            due = now + timezone.timedelta(days=days)
        with transaction.atomic():
            locked = Book.objects.select_for_update().get(pk=book.pk)
            if locked.available_copies < 1:
                raise serializers.ValidationError("该书暂无在架副本。")
            if BorrowRecord.objects.filter(
                user=user,
                book=locked,
                status=BorrowRecord.Status.BORROWED,
            ).exists():
                raise serializers.ValidationError("您已借阅该书且尚未归还。")
            locked.available_copies -= 1
            locked.save(update_fields=["available_copies", "updated_at"])
            return BorrowRecord.objects.create(
                user=user,
                book=locked,
                due_at=due,
                status=BorrowRecord.Status.BORROWED,
            )
