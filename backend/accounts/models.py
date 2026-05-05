from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        READER = "reader", "读者"
        LIBRARIAN = "librarian", "图书管理员"

    student_id = models.CharField("学号/工号", max_length=32, blank=True, null=True, unique=True, db_index=True)
    avatar = models.ImageField("头像", upload_to="avatars/", blank=True, null=True)
    role = models.CharField(
        "角色",
        max_length=20,
        choices=Role.choices,
        default=Role.READER,
    )

    class Meta:
        verbose_name = "用户"
        verbose_name_plural = "用户"

    @property
    def is_librarian(self) -> bool:
        return self.role == self.Role.LIBRARIAN or self.is_superuser
