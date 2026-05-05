"""站内通知创建（书评点赞 / 评论 / 回复）。"""

import re

from django.contrib.auth import get_user_model

from .models import BookReview, BookReviewComment, Notification

User = get_user_model()

# 入库摘要去掉正文里的「回复某人：」前缀，与前端评论编辑一致
_SNIPPET_STRIP_REPLY = re.compile(r"^回复\s*.+?[﹕∶：:]\s*", re.UNICODE)


def _snippet_for_preview(body: str, max_len: int = 120) -> str:
    raw = (body or "").strip()
    raw = _SNIPPET_STRIP_REPLY.sub("", raw, count=1)
    return raw[:max_len]


def notify_review_liked(review: BookReview, actor: User) -> None:
    if review.user_id == actor.id:
        return
    name = getattr(actor, "username", "") or str(actor.pk)
    Notification.objects.create(
        recipient_id=review.user_id,
        actor=actor,
        kind=Notification.Kind.REVIEW_LIKED,
        book_id=review.book_id,
        book_review=review,
        comment=None,
        preview=f"{name} 赞了你的书评",
    )


def notify_review_commented(
    review: BookReview, actor: User, comment: BookReviewComment
) -> None:
    if review.user_id == actor.id:
        return
    name = getattr(actor, "username", "") or str(actor.pk)
    snippet = _snippet_for_preview(comment.content)
    Notification.objects.create(
        recipient_id=review.user_id,
        actor=actor,
        kind=Notification.Kind.REVIEW_COMMENTED,
        book_id=review.book_id,
        book_review=review,
        comment=comment,
        preview=f"{name} 评论了你的书评：{snippet}",
    )


def notify_comment_replied(
    parent: BookReviewComment, reply: BookReviewComment
) -> None:
    if parent.user_id == reply.user_id:
        return
    actor = reply.user
    name = getattr(actor, "username", "") or str(actor.pk)
    snippet = _snippet_for_preview(reply.content)
    Notification.objects.create(
        recipient_id=parent.user_id,
        actor=actor,
        kind=Notification.Kind.COMMENT_REPLIED,
        book_id=parent.review.book_id,
        book_review=parent.review,
        comment=reply,
        preview=f"{name} 回复了你：{snippet}",
    )
