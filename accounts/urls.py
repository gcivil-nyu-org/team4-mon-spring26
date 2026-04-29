from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path(
        "login/",
        LoginView.as_view(
            template_name="accounts/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("profile/", views.profile_view, name="profile"),
    # Tenant verification
    path("verify/", views.request_verification_view, name="request-verification"),
    path(
        "verify/<int:pk>/edit/",
        views.edit_verification_view,
        name="edit-verification",
    ),
    path(
        "verify/<int:pk>/withdraw/",
        views.withdraw_verification_view,
        name="withdraw-verification",
    ),
    path("verify/status/", views.verification_status_view, name="verification-status"),
    # Admin moderation
    path(
        "admin/verifications/",
        views.admin_verification_queue_view,
        name="admin-verification-queue",
    ),
    path(
        "admin/verifications/<int:pk>/",
        views.admin_verification_review_view,
        name="admin-verification-review",
    ),
]
