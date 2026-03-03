from django.test import TestCase
from django.urls import reverse

from .models import User


# ============================================================ #
#  User Model
# ============================================================ #


class UserModelTests(TestCase):
    def test_default_role_is_public(self):
        user = User.objects.create_user(username="u1", password="testpass123")
        self.assertEqual(user.role, User.ROLE_PUBLIC)

    def test_is_verified_tenant_property(self):
        user = User.objects.create_user(username="u2", password="testpass123", role=User.ROLE_VERIFIED_TENANT)
        self.assertTrue(user.is_verified_tenant)

    def test_public_user_is_not_verified(self):
        user = User.objects.create_user(username="u3", password="testpass123")
        self.assertFalse(user.is_verified_tenant)

    def test_is_admin_user_for_admin_role(self):
        user = User.objects.create_user(username="u4", password="testpass123", role=User.ROLE_ADMIN)
        self.assertTrue(user.is_admin_user)

    def test_is_admin_user_for_superuser(self):
        user = User.objects.create_superuser(username="su", password="testpass123", email="su@test.com")
        self.assertTrue(user.is_admin_user)

    def test_display_role(self):
        user = User.objects.create_user(username="u5", password="testpass123")
        self.assertEqual(user.display_role, "Public User")

    def test_str(self):
        user = User.objects.create_user(username="alice", password="testpass123")
        self.assertEqual(str(user), "alice")


# ============================================================ #
#  Registration
# ============================================================ #


class RegistrationViewTests(TestCase):
    def test_register_page_loads(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Account")

    def test_register_creates_user_and_redirects(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "first_name": "New",
                "last_name": "User",
                "password1": "StrongPass99!",
                "password2": "StrongPass99!",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_register_logs_user_in(self):
        self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "email": "new@example.com",
                "first_name": "New",
                "last_name": "User",
                "password1": "StrongPass99!",
                "password2": "StrongPass99!",
            },
        )
        # After registration, user should be authenticated
        response = self.client.get(reverse("dashboard"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_register_rejects_duplicate_username(self):
        User.objects.create_user(username="taken", password="testpass123")
        response = self.client.post(
            reverse("register"),
            {
                "username": "taken",
                "email": "new@example.com",
                "first_name": "A",
                "last_name": "B",
                "password1": "StrongPass99!",
                "password2": "StrongPass99!",
            },
        )
        self.assertEqual(response.status_code, 200)  # re-renders with errors
        self.assertEqual(User.objects.filter(username="taken").count(), 1)

    def test_register_rejects_password_mismatch(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "mismatch",
                "email": "mm@example.com",
                "first_name": "A",
                "last_name": "B",
                "password1": "StrongPass99!",
                "password2": "WrongPass99!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="mismatch").exists())

    def test_authenticated_user_redirected_from_register(self):
        User.objects.create_user(username="existing", password="testpass123")
        self.client.login(username="existing", password="testpass123")
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 302)


# ============================================================ #
#  Login
# ============================================================ #


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="loginuser", password="StrongPass99!", email="login@test.com"
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome Back")

    def test_login_success_redirects(self):
        response = self.client.post(
            reverse("login"),
            {"username": "loginuser", "password": "StrongPass99!"},
        )
        self.assertEqual(response.status_code, 302)

    def test_login_invalid_credentials(self):
        response = self.client.post(
            reverse("login"),
            {"username": "loginuser", "password": "WrongPassword"},
        )
        self.assertEqual(response.status_code, 200)  # re-renders form

    def test_authenticated_user_redirected_from_login(self):
        self.client.login(username="loginuser", password="StrongPass99!")
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 302)


# ============================================================ #
#  Logout
# ============================================================ #


class LogoutViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="logoutuser", password="testpass123")

    def test_logout_redirects(self):
        self.client.login(username="logoutuser", password="testpass123")
        response = self.client.post(reverse("logout"))
        self.assertIn(response.status_code, [200, 302])


# ============================================================ #
#  Profile
# ============================================================ #


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="profuser",
            password="StrongPass99!",
            email="prof@test.com",
            first_name="Prof",
            last_name="User",
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_profile_loads_when_authenticated(self):
        self.client.login(username="profuser", password="StrongPass99!")
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Prof")

    def test_profile_update(self):
        self.client.login(username="profuser", password="StrongPass99!")
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "Updated",
                "last_name": "Name",
                "email": "updated@example.com",
                "phone_number": "5551234567",
                "bio": "Hello world",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")
        self.assertEqual(self.user.phone_number, "5551234567")
        self.assertEqual(self.user.bio, "Hello world")

    def test_profile_shows_role_badge(self):
        self.client.login(username="profuser", password="StrongPass99!")
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Public User")
