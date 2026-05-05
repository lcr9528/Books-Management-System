import django_filters
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Book, BookChapter, BorrowRecord, Category
from .permissions import (
    BorrowObjectPermission,
    IsLibrarianOrReadOnly,
)
from .serializers import (
    BookChapterDetailSerializer,
    BookChapterListSerializer,
    BookDetailSerializer,
    BookListSerializer,
    BookWriteSerializer,
    BorrowCreateSerializer,
    BorrowRecordSerializer,
    CategorySerializer,
)


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
            b = rec.book
            b.available_copies = min(b.available_copies + 1, b.total_copies)
            b.save(update_fields=["available_copies", "updated_at"])
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
