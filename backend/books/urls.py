from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BookChapterDetailAPIView,
    BookChapterListAPIView,
    BookViewSet,
    BorrowViewSet,
    CategoryViewSet,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("books", BookViewSet, basename="book")
router.register("borrows", BorrowViewSet, basename="borrow")

urlpatterns = [
    path(
        "books/<int:book_pk>/chapters/<int:pk>/",
        BookChapterDetailAPIView.as_view(),
        name="book-chapter-detail",
    ),
    path(
        "books/<int:book_pk>/chapters/",
        BookChapterListAPIView.as_view(),
        name="book-chapter-list",
    ),
    path("", include(router.urls)),
]
