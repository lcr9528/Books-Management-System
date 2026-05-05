from rest_framework import permissions


class IsLibrarian(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(u and u.is_authenticated and u.is_librarian)


class IsLibrarianOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.method in permissions.SAFE_METHODS:
            return True
        u = request.user
        return bool(u and u.is_authenticated and u.is_librarian)


class BorrowObjectPermission(permissions.BasePermission):
    """借阅记录仅本人可操作；不因图书管理员身份放行（与 BorrowViewSet 列表范围一致）。"""

    def has_object_permission(self, request, view, obj) -> bool:
        return bool(request.user.is_authenticated) and obj.user_id == request.user.id
