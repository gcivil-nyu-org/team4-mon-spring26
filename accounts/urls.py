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
]
