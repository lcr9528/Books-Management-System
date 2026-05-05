from django.urls import path

from .password_reset_views import PasswordResetConfirmView, PasswordResetRequestView
from .views import MeView, RegisterAvailabilityView, RegisterView

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/register/check/", RegisterAvailabilityView.as_view(), name="auth-register-check"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
]
