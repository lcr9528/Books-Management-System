from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BookChapterDetailAPIView,
    BookChapterListAPIView,
    BookReviewAdminDestroyAPIView,
    BookReviewCommentDestroyAPIView,
    BookReviewCommentLikeToggleAPIView,
    BookReviewCommentListCreateAPIView,
    BookReviewLikeToggleAPIView,
    BookReviewListCreateAPIView,
    BookReviewMineAPIView,
    BookViewSet,
    BorrowViewSet,
    CategoryViewSet,
    NotificationViewSet,
    SiteSettingsAPIView,
)

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("books", BookViewSet, basename="book")
router.register("borrows", BorrowViewSet, basename="borrow")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("site-settings/", SiteSettingsAPIView.as_view(), name="site-settings"),
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
    path(
        "books/<int:book_pk>/reviews/<int:review_pk>/comments/<int:comment_pk>/like/",
        BookReviewCommentLikeToggleAPIView.as_view(),
        name="book-review-comment-like-toggle",
    ),
    path(
        "books/<int:book_pk>/reviews/<int:review_pk>/comments/<int:comment_pk>/",
        BookReviewCommentDestroyAPIView.as_view(),
        name="book-review-comment-destroy",
    ),
    path(
        "books/<int:book_pk>/reviews/<int:review_pk>/comments/",
        BookReviewCommentListCreateAPIView.as_view(),
        name="book-review-comments",
    ),
    path(
        "books/<int:book_pk>/reviews/<int:review_pk>/like/",
        BookReviewLikeToggleAPIView.as_view(),
        name="book-review-like-toggle",
    ),
    path(
        "books/<int:book_pk>/reviews/mine/",
        BookReviewMineAPIView.as_view(),
        name="book-review-mine",
    ),
    path(
        "books/<int:book_pk>/reviews/<int:pk>/",
        BookReviewAdminDestroyAPIView.as_view(),
        name="book-review-admin-destroy",
    ),
    path(
        "books/<int:book_pk>/reviews/",
        BookReviewListCreateAPIView.as_view(),
        name="book-review-list-create",
    ),
    path("", include(router.urls)),
]
