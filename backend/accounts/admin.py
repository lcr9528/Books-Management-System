from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "student_id", "is_active", "is_staff")
    list_filter = ("role", "is_staff", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (("图书系统", {"fields": ("role", "student_id", "avatar")}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("图书系统", {"fields": ("role", "student_id")}),)
