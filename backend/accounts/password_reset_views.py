import random

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import PasswordResetConfirmSerializer, PasswordResetRequestSerializer
from .models import User


def _cache_key(email: str) -> str:
    return f"pwdreset:{email}"


class PasswordResetRequestView(APIView):
    """申请发送邮箱验证码（10 分钟内有效）。"""

    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        ser = PasswordResetRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]
        user = User.objects.filter(email__iexact=email).first()
        if user:
            code = f"{random.randint(100000, 999999)}"
            cache.set(_cache_key(email), code, 600)
            body = (
                f"【图书管理系统】您正在重置密码。验证码为 {code}，10 分钟内有效。"
                f"如非本人操作请忽略本邮件。"
            )
            try:
                send_mail(
                    subject="图书管理系统 — 密码重置验证码",
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email or email],
                    fail_silently=False,
                )
            except Exception:  # noqa: BLE001 — 发信失败不暴露给前端细节
                return Response(
                    {"detail": "邮件暂时无法发出，请稍后重试或联系管理员。"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        return Response(
            {
                "detail": "如该邮箱已注册，将收到含验证码的邮件。请查收后返回本页填写验证码并设置新密码。",
            }
        )


class PasswordResetConfirmView(APIView):
    """用邮箱验证码重设密码。"""

    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"]
        code = ser.validated_data["code"]
        new_password = ser.validated_data["new_password"]
        key = _cache_key(email)
        real = cache.get(key)
        if not real or real != code:
            return Response(
                {"code": ["验证码无效或已过期，请重新申请。"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            return Response(
                {"email": ["未找到该邮箱对应账号。"]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(new_password)
        user.save()
        cache.delete(key)
        return Response({"detail": "密码已重置，请使用新密码登录。"})
