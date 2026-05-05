import re

from typing import Optional

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


def _code_digits(s: str) -> str:
    s = s.strip()
    if not re.match(r"^\d{6}$", s):
        raise serializers.ValidationError("验证码须为 6 位数字。")
    return s


class UserSerializer(serializers.ModelSerializer):
    is_librarian = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "student_id",
            "avatar",
            "role",
            "is_librarian",
            "date_joined",
        )
        read_only_fields = ("id", "date_joined", "role")

    def get_is_librarian(self, obj) -> bool:
        return bool(obj.is_librarian)

    def get_avatar(self, obj) -> Optional[str]:
        if not obj.avatar:
            return None
        request = self.context.get("request")
        url = obj.avatar.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class UserUpdateSerializer(serializers.ModelSerializer):
    """当前用户修改资料（含头像上传）。"""

    class Meta:
        model = User
        fields = ("username", "email", "first_name", "last_name", "student_id", "avatar")

    def validate_email(self, value: str) -> str:
        v = value.strip()
        user = self.instance
        if user and User.objects.filter(email__iexact=v).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("该邮箱已被其他账号使用。")
        return v

    def validate_username(self, value: str) -> str:
        v = value.strip()
        if len(v) < 1:
            raise serializers.ValidationError("用户名不能为空。")
        user = self.instance
        if user and User.objects.filter(username=v).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("该用户名已被占用。")
        return v

    def validate_student_id(self, value):
        if value in (None, ""):
            return None
        v = str(value).strip()
        user = self.instance
        if user and User.objects.filter(student_id=v).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("该学号/工号已被占用。")
        return v or None


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6, style={"input_type": "password"})
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "password", "email")
        # 避免 UniqueValidator 先于 validate_* 触发并返回 Django 默认长句
        extra_kwargs = {
            "username": {"validators": []},
            "email": {"validators": []},
        }

    def validate_username(self, value: str) -> str:
        u = (value or "").strip()
        if not u:
            raise serializers.ValidationError("请输入账号。")
        if User.objects.filter(username__iexact=u).exists():
            raise serializers.ValidationError("该账号已被使用。")
        return u

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value.strip()).exists():
            raise serializers.ValidationError("该邮箱已被使用。")
        return value.strip()

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data, role=User.Role.READER)
        user.set_password(password)
        user.save()
        return user


class RegisterAvailabilitySerializer(serializers.Serializer):
    """注册前查重：可单独传 username 或 email。"""

    username = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs: dict) -> dict:
        username = (attrs.get("username") or "").strip()
        email = (attrs.get("email") or "").strip()
        if not username and not email:
            raise serializers.ValidationError("请至少提供账号或邮箱。")
        attrs["username"] = username
        attrs["email"] = email
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField()
    new_password = serializers.CharField(
        min_length=6, write_only=True, style={"input_type": "password"}
    )

    def validate_code(self, value: str) -> str:
        return _code_digits(value)

    def validate(self, attrs):
        attrs["email"] = attrs["email"].strip().lower()
        return attrs
