import django_filters
from django.conf import settings
from django.db import transaction
from django.db.models import BooleanField, Count, Exists, F, OuterRef, Value
from django.db.models.functions import Least
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, status, viewsets
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated, NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import (
    Book,
    BookChapter,
    BookReview,
    BookReviewComment,
    BookReviewCommentLike,
    BookReviewLike,
    BorrowRecord,
    Category,
    Notification,
    SiteSettings,
)
from .permissions import (
    BorrowObjectPermission,
    CommentOwnerOrLibrarian,
    IsLibrarian,
    IsLibrarianOrReadOnly,
)
from .serializers import (
    annotate_book_review_comment_queryset,
    BookChapterDetailSerializer,
    BookChapterListSerializer,
    BookDetailSerializer,
    BookListSerializer,
    BookReviewCommentSerializer,
    BookReviewCommentWriteSerializer,
    BookReviewSerializer,
    BookReviewWriteSerializer,
    BookWriteSerializer,
    BorrowCreateSerializer,
    BorrowRecordSerializer,
    CategorySerializer,
    NotificationSerializer,
    SiteSettingsSerializer,
)


class SiteSettingsAPIView(APIView):
    """GET/PATCH /api/v1/site-settings/ — 全局站点开关（PATCH 仅图书管理员）。"""

    def get_permissions(self):
        if self.request.method == "PATCH":
            return [IsAuthenticated(), IsLibrarian()]
        return [AllowAny()]

    def get(self, request):
        s = SiteSettings.get_solo()
        return Response(SiteSettingsSerializer(s).data)

    def patch(self, request):
        s = SiteSettings.get_solo()
        ser = SiteSettingsSerializer(s, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = (IsLibrarianOrReadOnly,)
    pagination_class = None  # 分类总量小，列表页侧边栏需一次取全


class BookFilter(django_filters.FilterSet):
    class Meta:
        model = Book
        fields = ("category", "isbn")


class BookPagePagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 100


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.select_related("category").all()
    permission_classes = (IsLibrarianOrReadOnly,)
    filterset_class = BookFilter
    pagination_class = BookPagePagination
    search_fields = ("title", "author", "isbn", "publisher")
    ordering_fields = ("created_at", "title", "isbn")
    ordering = ("-created_at",)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return BookWriteSerializer
        if self.action == "retrieve":
            return BookDetailSerializer
        return BookListSerializer


class BookChapterListAPIView(generics.ListAPIView):
    """GET /api/v1/books/{book_pk}/chapters/"""

    serializer_class = BookChapterListSerializer
    permission_classes = (IsLibrarianOrReadOnly,)
    pagination_class = None

    def get_queryset(self):
        return BookChapter.objects.filter(book_id=self.kwargs["book_pk"]).order_by(
            "order", "id"
        )


class BookChapterDetailAPIView(generics.RetrieveAPIView):
    """GET /api/v1/books/{book_pk}/chapters/{pk}/"""

    serializer_class = BookChapterDetailSerializer
    permission_classes = (IsLibrarianOrReadOnly,)
    lookup_url_kwarg = "pk"

    def get_queryset(self):
        return BookChapter.objects.filter(book_id=self.kwargs["book_pk"])

    def retrieve(self, request, *args, **kwargs):
        if SiteSettings.get_solo().require_borrow_to_read_chapters:
            user = request.user
            book_pk = self.kwargs["book_pk"]
            if not user.is_authenticated:
                raise NotAuthenticated(detail="请先登录后再阅读章节正文。")
            if not BorrowRecord.objects.filter(
                user_id=user.id,
                book_id=book_pk,
                status=BorrowRecord.Status.BORROWED,
            ).exists():
                raise PermissionDenied(
                    detail="请先借阅本书，并在「在借」期间阅读章节正文。"
                )
        return super().retrieve(request, *args, **kwargs)


def _annotate_book_review_qs(qs, request):
    qs = qs.annotate(
        like_count=Count("likes", distinct=True),
        comment_count=Count("review_comments", distinct=True),
    )
    user = request.user
    if user.is_authenticated:
        qs = qs.annotate(
            liked_by_me=Exists(
                BookReviewLike.objects.filter(
                    review_id=OuterRef("pk"), user_id=user.id
                )
            )
        )
    else:
        qs = qs.annotate(liked_by_me=Value(False, output_field=BooleanField()))
    return qs


class BookReviewListCreateAPIView(generics.ListCreateAPIView):
    """GET/POST /api/v1/books/{book_pk}/reviews/ — 列表公开；发表需登录且曾借阅该书。"""

    pagination_class = BookPagePagination

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BookReviewWriteSerializer
        return BookReviewSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.method == "POST":
            ctx["book"] = get_object_or_404(Book.objects.all(), pk=self.kwargs["book_pk"])
        return ctx

    def get_queryset(self):
        qs = BookReview.objects.select_related("user").filter(
            book_id=self.kwargs["book_pk"]
        )
        qs = _annotate_book_review_qs(qs, self.request)
        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        book_pk = self.kwargs["book_pk"]
        if BookReview.objects.filter(
            book_id=book_pk, user_id=self.request.user.id
        ).exists():
            raise ValidationError(
                {"detail": "您已对该书发表过书评；发布后不可修改，请先删除后再发表。"}
            )
        serializer.save()


class BookReviewMineAPIView(generics.RetrieveDestroyAPIView):
    """GET/DELETE /api/v1/books/{book_pk}/reviews/mine/ — 当前用户对该书的一条书评（发布后不可修改）。"""

    permission_classes = (IsAuthenticated,)
    serializer_class = BookReviewSerializer
    http_method_names = ("get", "delete", "head", "options")

    def get_queryset(self):
        qs = BookReview.objects.select_related("user").filter(
            book_id=self.kwargs["book_pk"],
            user_id=self.request.user.id,
        )
        return _annotate_book_review_qs(qs, self.request)

    def get_object(self):
        obj = self.get_queryset().first()
        if obj is None:
            raise NotFound()
        self.check_object_permissions(self.request, obj)
        return obj


class BookReviewAdminDestroyAPIView(generics.DestroyAPIView):
    """DELETE /api/v1/books/{book_pk}/reviews/{pk}/ — 仅图书管理员可删任意书评。"""

    permission_classes = (IsAuthenticated, IsLibrarian)

    def get_queryset(self):
        return BookReview.objects.filter(book_id=self.kwargs["book_pk"])


class BookReviewLikeToggleAPIView(APIView):
    """POST /api/v1/books/{book_pk}/reviews/{review_pk}/like/ — 切换点赞。"""

    permission_classes = (IsAuthenticated,)

    def post(self, request, book_pk, review_pk):
        review = get_object_or_404(BookReview, pk=review_pk, book_id=book_pk)
        like = BookReviewLike.objects.filter(review=review, user=request.user).first()
        if like:
            like.delete()
            liked = False
        else:
            BookReviewLike.objects.create(review=review, user=request.user)
            liked = True
            from .notify import notify_review_liked

            notify_review_liked(review, request.user)
        cnt = BookReviewLike.objects.filter(review=review).count()
        return Response({"liked": liked, "like_count": cnt})


class BookReviewCommentListCreateAPIView(generics.ListCreateAPIView):
    """GET/POST /api/v1/books/{book_pk}/reviews/{review_pk}/comments/ — 一级评论列表与发表。"""

    pagination_class = None

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BookReviewCommentWriteSerializer
        return BookReviewCommentSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["review"] = get_object_or_404(
            BookReview.objects.all(),
            pk=self.kwargs["review_pk"],
            book_id=self.kwargs["book_pk"],
        )
        return ctx

    def get_queryset(self):
        review = get_object_or_404(
            BookReview.objects.all(),
            pk=self.kwargs["review_pk"],
            book_id=self.kwargs["book_pk"],
        )
        qs = BookReviewComment.objects.filter(
            review=review, parent__isnull=True
        ).select_related("user", "review", "review__user")
        qs = annotate_book_review_comment_queryset(qs, self.request)
        return qs.order_by("created_at", "id")

    def perform_create(self, serializer):
        comment = serializer.save()
        from .notify import notify_comment_replied, notify_review_commented

        if comment.parent_id:
            notify_comment_replied(comment.parent, comment)
        else:
            notify_review_commented(comment.review, self.request.user, comment)


class BookReviewCommentLikeToggleAPIView(APIView):
    """POST .../comments/{comment_pk}/like/ — 切换评论点赞。"""

    permission_classes = (IsAuthenticated,)

    def post(self, request, book_pk, review_pk, comment_pk):
        review = get_object_or_404(BookReview, pk=review_pk, book_id=book_pk)
        comment = get_object_or_404(
            BookReviewComment.objects.all(), pk=comment_pk, review=review
        )
        like = BookReviewCommentLike.objects.filter(
            comment=comment, user=request.user
        ).first()
        if like:
            like.delete()
            liked = False
        else:
            BookReviewCommentLike.objects.create(comment=comment, user=request.user)
            liked = True
        cnt = BookReviewCommentLike.objects.filter(comment=comment).count()
        return Response({"liked": liked, "like_count": cnt})


class BookReviewCommentDestroyAPIView(generics.DestroyAPIView):
    """DELETE .../comments/{comment_pk}/ — 删除评论（本人或馆员）。"""

    permission_classes = (IsAuthenticated, CommentOwnerOrLibrarian)
    lookup_url_kwarg = "comment_pk"

    def get_queryset(self):
        return BookReviewComment.objects.filter(
            review_id=self.kwargs["review_pk"],
            review__book_id=self.kwargs["book_pk"],
        )


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/v1/notifications/ — 当前用户通知列表；标记已读。"""

    permission_classes = (IsAuthenticated,)
    serializer_class = NotificationSerializer
    pagination_class = BookPagePagination
    # 需允许 post：read、mark-all-read 等 @action
    http_method_names = ("get", "head", "options", "post")

    def get_queryset(self):
        return (
            Notification.objects.select_related(
                "actor", "book", "book_review", "comment"
            )
            .filter(recipient=self.request.user)
            .order_by("-created_at")
        )

    @action(detail=True, methods=("post",), url_path="read")
    def mark_read(self, request, pk=None):
        updated = Notification.objects.filter(
            pk=pk, recipient=request.user, is_read=False
        ).update(is_read=True)
        if not updated and not Notification.objects.filter(
            pk=pk, recipient=request.user
        ).exists():
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response({"ok": True})

    @action(detail=False, methods=("post",), url_path="mark-all-read")
    def mark_all_read(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True
        )
        return Response({"ok": True})

    @action(detail=False, methods=("get",), url_path="unread-count")
    def unread_count(self, request):
        n = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        return Response({"count": n})


class BorrowViewSet(viewsets.ModelViewSet):
    """REST 借阅接口仅供前台「我的借阅」：所有人（含超级管理员、图书管理员）只能读写自己的记录。
    查看全部借阅请在 Django Admin（/admin/…）操作。"""
    permission_classes = (IsAuthenticated, BorrowObjectPermission)
    pagination_class = BookPagePagination
    http_method_names = ("get", "post", "head", "options")

    def get_queryset(self):
        u = self.request.user
        return (
            BorrowRecord.objects.select_related("user", "book").filter(user=u)
        )

    def get_serializer_class(self):
        if self.action == "create":
            return BorrowCreateSerializer
        return BorrowRecordSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record: BorrowRecord = serializer.save()
        return Response(
            BorrowRecordSerializer(record, context={"request": request}).data,
            status=201,
        )

    @action(
        detail=True,
        methods=("post",),
        url_path="return",
    )
    def return_book(self, request, pk=None):
        preview = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(request, preview)
        with transaction.atomic():
            qs = self.get_queryset().select_for_update().select_related("book")
            rec = get_object_or_404(qs, pk=pk)
            if rec.status != BorrowRecord.Status.BORROWED:
                raise ValidationError({"detail": "该记录已归还，无需再次归还。"})
            # 单行原子加回在架册数，避免多副本同时归还时的丢失更新；上限钳制 total_copies
            Book.objects.filter(pk=rec.book_id).update(
                available_copies=Least(F("available_copies") + 1, F("total_copies")),
                updated_at=timezone.now(),
            )
            rec.returned_at = timezone.now()
            rec.status = BorrowRecord.Status.RETURNED
            rec.save(update_fields=["returned_at", "status"])
        return Response(
            BorrowRecordSerializer(rec, context={"request": request}).data
        )

    @action(
        detail=True,
        methods=("post",),
        url_path="renew",
    )
    def renew_book(self, request, pk=None):
        preview = get_object_or_404(self.get_queryset(), pk=pk)
        self.check_object_permissions(request, preview)
        with transaction.atomic():
            qs = self.get_queryset().select_for_update()
            rec = get_object_or_404(qs, pk=pk)
            if rec.status != BorrowRecord.Status.BORROWED:
                raise ValidationError({"detail": "该记录已归还，无法续借。"})
            if rec.returned_at:
                raise ValidationError({"detail": "该记录已归还，无法续借。"})

            req_due_at = request.data.get("due_at")
            if req_due_at not in (None, ""):
                try:
                    new_due = serializers.DateTimeField().to_internal_value(req_due_at)
                except serializers.ValidationError:
                    raise ValidationError({"detail": "续借时间格式不正确。"})
                if new_due <= timezone.now():
                    raise ValidationError({"detail": "续借时间需晚于当前时间。"})
                if new_due <= rec.due_at:
                    raise ValidationError({"detail": "续借时间需晚于当前归还时间。"})
                if new_due > rec.due_at + timezone.timedelta(days=90):
                    raise ValidationError({"detail": "续借时间不能超过当前归还时间后 90 天。"})
                rec.due_at = new_due
                rec.save(update_fields=["due_at"])
                return Response(
                    BorrowRecordSerializer(rec, context={"request": request}).data
                )

            renew_days = max(int(getattr(settings, "BORROW_RENEW_DAYS", 15)), 1)
            req_days = request.data.get("days")
            if req_days is not None:
                try:
                    renew_days = int(req_days)
                except (TypeError, ValueError):
                    raise ValidationError({"detail": "续借天数格式不正确。"})
                if renew_days < 1 or renew_days > 90:
                    raise ValidationError({"detail": "续借天数需在 1~90 天之间。"})
            max_renewals = max(int(getattr(settings, "BORROW_MAX_RENEWALS", 1)), 0)
            borrow_days = max(int(getattr(settings, "BORROW_DAYS", 30)), 1)
            base_delta = timezone.timedelta(days=borrow_days)
            renew_delta = timezone.timedelta(days=renew_days)

            total_delta = rec.due_at - rec.borrowed_at
            renew_count = 0
            if total_delta > base_delta and renew_delta.total_seconds() > 0:
                extra_seconds = (total_delta - base_delta).total_seconds()
                renew_count = int(extra_seconds // renew_delta.total_seconds())
            if renew_count >= max_renewals:
                raise ValidationError({"detail": "该借阅记录已达到续借上限。"})

            rec.due_at = rec.due_at + renew_delta
            rec.save(update_fields=["due_at"])
        return Response(
            BorrowRecordSerializer(rec, context={"request": request}).data
        )
