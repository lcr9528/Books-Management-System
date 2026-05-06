import re
from typing import Optional

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import BooleanField, Count, Exists, F, OuterRef, Value
from django.utils import timezone
from rest_framework import serializers

from accounts.models import User

from .models import (
    Book,
    BookChapter,
    BookReview,
    BookReviewComment,
    BookReviewCommentLike,
    BorrowRecord,
    Category,
    Notification,
    SiteSettings,
)


def annotate_book_review_comment_queryset(qs, request):
    """为评论查询集附加 like_count、liked_by_me（列表与子回复共用）。"""
    qs = qs.annotate(like_count=Count("likes", distinct=True))
    user = request.user
    if user.is_authenticated:
        qs = qs.annotate(
            liked_by_me=Exists(
                BookReviewCommentLike.objects.filter(
                    comment_id=OuterRef("pk"), user_id=user.id
                )
            )
        )
    else:
        qs = qs.annotate(liked_by_me=Value(False, output_field=BooleanField()))
    return qs


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name")


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = ("require_borrow_to_read_chapters", "updated_at")
        read_only_fields = ("updated_at",)


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
    review_eligible = serializers.SerializerMethodField()
    has_my_review = serializers.SerializerMethodField()
    reading_requires_borrow = serializers.SerializerMethodField()
    can_read_chapters = serializers.SerializerMethodField()
    has_my_active_borrow = serializers.SerializerMethodField()

    class Meta(BookListSerializer.Meta):
        fields = BookListSerializer.Meta.fields + (
            "description",
            "updated_at",
            "review_eligible",
            "has_my_review",
            "reading_requires_borrow",
            "can_read_chapters",
            "has_my_active_borrow",
        )
        read_only_fields = (
            "created_at",
            "available_copies",
            "review_eligible",
            "has_my_review",
            "reading_requires_borrow",
            "can_read_chapters",
            "has_my_active_borrow",
        )

    def get_review_eligible(self, obj: Book) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return BorrowRecord.objects.filter(
            user_id=request.user.id, book_id=obj.id
        ).exists()

    def get_has_my_review(self, obj: Book) -> bool:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return BookReview.objects.filter(
            user_id=request.user.id, book_id=obj.id
        ).exists()

    def get_reading_requires_borrow(self, obj: Book) -> bool:
        return SiteSettings.get_solo().require_borrow_to_read_chapters

    def get_can_read_chapters(self, obj: Book) -> bool:
        if not SiteSettings.get_solo().require_borrow_to_read_chapters:
            return True
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return BorrowRecord.objects.filter(
            user_id=request.user.id,
            book_id=obj.id,
            status=BorrowRecord.Status.BORROWED,
        ).exists()

    def get_has_my_active_borrow(self, obj: Book) -> bool:
        """当前用户是否已有本书「在借」记录（未归还前不可再借第二册）。"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return BorrowRecord.objects.filter(
            user_id=request.user.id,
            book_id=obj.id,
            status=BorrowRecord.Status.BORROWED,
        ).exists()


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
        try:
            with transaction.atomic():
                locked = Book.objects.select_for_update().get(pk=book.pk)
                if BorrowRecord.objects.filter(
                    user=user,
                    book=locked,
                    status=BorrowRecord.Status.BORROWED,
                ).exists():
                    raise serializers.ValidationError("您已借阅该书且尚未归还。")
                # 条件 UPDATE：单行原子扣减；SQLite 等忽略 select_for_update 时仍靠此行避免超借
                n = Book.objects.filter(
                    pk=locked.pk, available_copies__gte=1
                ).update(available_copies=F("available_copies") - 1)
                if n != 1:
                    raise serializers.ValidationError("该书暂无在架副本。")
                return BorrowRecord.objects.create(
                    user=user,
                    book_id=locked.pk,
                    due_at=due,
                    status=BorrowRecord.Status.BORROWED,
                )
        except IntegrityError:
            # 条件唯一约束下并发 create 失败；在 atomic 外捕获以便整段事务回滚、库存自动还原
            raise serializers.ValidationError("您已借阅该书且尚未归还。")


class BookReviewSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_avatar = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(read_only=True, required=False)
    liked_by_me = serializers.BooleanField(read_only=True, required=False)
    comment_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = BookReview
        fields = (
            "id",
            "user",
            "user_username",
            "user_avatar",
            "rating",
            "content",
            "created_at",
            "updated_at",
            "like_count",
            "liked_by_me",
            "comment_count",
        )
        read_only_fields = fields

    def get_user_avatar(self, obj: BookReview) -> Optional[str]:
        u = obj.user
        if not getattr(u, "avatar", None):
            return None
        request = self.context.get("request")
        url = u.avatar.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class BookReviewCommentSerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source="user.username", read_only=True)
    user_avatar = serializers.SerializerMethodField()
    parent_user_username = serializers.SerializerMethodField()
    is_follow_up_review = serializers.SerializerMethodField()
    like_count = serializers.IntegerField(read_only=True, required=False)
    liked_by_me = serializers.BooleanField(read_only=True, required=False)
    replies = serializers.SerializerMethodField()

    class Meta:
        model = BookReviewComment
        fields = (
            "id",
            "user",
            "user_username",
            "user_avatar",
            "content",
            "parent",
            "parent_user_username",
            "is_follow_up_review",
            "created_at",
            "like_count",
            "liked_by_me",
            "replies",
        )
        read_only_fields = (
            "id",
            "user",
            "user_username",
            "user_avatar",
            "parent_user_username",
            "is_follow_up_review",
            "created_at",
            "like_count",
            "liked_by_me",
            "replies",
        )

    def get_user_avatar(self, obj: BookReviewComment) -> Optional[str]:
        u = obj.user
        if not getattr(u, "avatar", None):
            return None
        request = self.context.get("request")
        url = u.avatar.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def get_parent_user_username(self, obj: BookReviewComment) -> Optional[str]:
        if obj.parent_id is None:
            return None
        p = obj.parent
        if p is None:
            return None
        return p.user.username

    def get_is_follow_up_review(self, obj: BookReviewComment) -> bool:
        """本人回复自己的书评（顶层评论）或回复自己的上一条评论。"""
        if obj.parent_id is None:
            return obj.user_id == obj.review.user_id
        p = obj.parent
        if p is None:
            return False
        return obj.user_id == p.user_id

    def get_replies(self, obj: BookReviewComment):
        request = self.context.get("request")
        if request is None:
            return []
        qs = (
            BookReviewComment.objects.filter(parent=obj)
            .select_related(
                "user",
                "parent",
                "parent__user",
                "review",
                "review__user",
            )
            .order_by("created_at", "id")
        )
        qs = annotate_book_review_comment_queryset(qs, request)
        return BookReviewCommentSerializer(qs, many=True, context=self.context).data


class BookReviewCommentWriteSerializer(serializers.ModelSerializer):
    parent = serializers.PrimaryKeyRelatedField(
        queryset=BookReviewComment.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = BookReviewComment
        fields = ("content", "parent")

    def validate_content(self, value):
        text = (value or "").strip()
        if not text:
            raise serializers.ValidationError("评论内容不能为空。")
        if len(text) > 2000:
            raise serializers.ValidationError("评论不能超过 2000 字。")
        return text

    def validate(self, attrs):
        parent = attrs.get("parent")
        review: BookReview = self.context["review"]
        if parent is not None and parent.review_id != review.id:
            raise serializers.ValidationError({"parent": "回复不属于该书评。"})
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        review: BookReview = self.context["review"]
        parent = validated_data.get("parent")
        return BookReviewComment.objects.create(
            review=review,
            user=request.user,
            parent=parent,
            content=validated_data["content"],
        )


# 通知摘要里正文常带「回复某用户：」，列表展示时去掉，只保留实际内容
_PREVIEW_EMBEDDED_REPLY = re.compile(r"^回复\s*.+?[﹕∶：:]\s*", re.UNICODE)


def clean_notification_preview_display(preview: str) -> str:
    if not preview:
        return preview
    for marker in ("评论了你的书评：", "回复了你："):
        if marker in preview:
            i = preview.index(marker) + len(marker)
            head, tail = preview[:i], preview[i:]
            tail = _PREVIEW_EMBEDDED_REPLY.sub("", tail.lstrip(), count=1)
            return head + tail
    return preview


class NotificationSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(
        source="actor.username", read_only=True, default=""
    )
    book_title = serializers.CharField(source="book.title", read_only=True)
    preview = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = (
            "id",
            "kind",
            "actor_username",
            "preview",
            "book",
            "book_review",
            "comment",
            "is_read",
            "created_at",
            "book_title",
        )
        read_only_fields = fields

    def get_preview(self, obj: Notification) -> str:
        return clean_notification_preview_display(obj.preview or "")


class BookReviewWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookReview
        fields = ("rating", "content")

    def validate_rating(self, value):
        if value is None:
            return None
        if value < 1 or value > 5:
            raise serializers.ValidationError("评分需在 1～5 星之间。")
        return value

    def validate_content(self, value):
        if value is None:
            return ""
        return value

    def validate(self, attrs):
        inst = self.instance
        rating = attrs.get("rating", inst.rating if inst else None)
        if "rating" in attrs and attrs["rating"] is None:
            rating = None
        raw_content = attrs.get("content", inst.content if inst else "")
        if raw_content is None:
            raw_content = ""
        content = str(raw_content).strip()
        if rating is None and not content:
            raise serializers.ValidationError(
                {"non_field_errors": ["请填写评分或书评正文（至少其一）。"]}
            )
        if len(content) > 5000:
            raise serializers.ValidationError(
                {"content": "书评正文不能超过 5000 字。"}
            )
        attrs["content"] = content
        attrs["rating"] = rating
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        book: Book = self.context["book"]
        user: User = request.user
        if not BorrowRecord.objects.filter(user=user, book=book).exists():
            raise serializers.ValidationError(
                {"detail": "仅借阅过该书的用户可发表书评。"}
            )
        return BookReview.objects.create(
            user=user,
            book=book,
            rating=validated_data.get("rating"),
            content=validated_data.get("content", ""),
        )
