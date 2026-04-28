from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import User, VerificationRequest

# ============================================================ #
#  User Model
# ============================================================ #


class UserModelTests(TestCase):
    def test_default_role_is_public(self):
        user = User.objects.create_user(username="u1", password="testpass123")
        self.assertEqual(user.role, User.ROLE_PUBLIC)

    def test_is_verified_tenant_property(self):
        user = User.objects.create_user(
            username="u2", password="testpass123", role=User.ROLE_VERIFIED_TENANT
        )
        self.assertTrue(user.is_verified_tenant)

    def test_public_user_is_not_verified(self):
        user = User.objects.create_user(username="u3", password="testpass123")
        self.assertFalse(user.is_verified_tenant)

    def test_is_admin_user_for_admin_role(self):
        user = User.objects.create_user(
            username="u4", password="testpass123", role=User.ROLE_ADMIN
        )
        self.assertTrue(user.is_admin_user)

    def test_is_admin_user_for_superuser(self):
        user = User.objects.create_superuser(
            username="su", password="testpass123", email="su@test.com"
        )
        self.assertTrue(user.is_admin_user)

    def test_display_role(self):
        user = User.objects.create_user(username="u5", password="testpass123")
        self.assertEqual(user.display_role, "Public User")

    def test_str(self):
        user = User.objects.create_user(username="alice", password="testpass123")
        self.assertEqual(str(user), "alice")

    def test_has_pending_verification_false_initially(self):
        user = User.objects.create_user(username="u6", password="testpass123")
        self.assertFalse(user.has_pending_verification)

    def test_has_pending_verification_true_when_pending(self):
        user = User.objects.create_user(username="u7", password="testpass123")
        VerificationRequest.objects.create(
            user=user,
            address="100 Broadway, New York, NY",
            document_type="lease",
            status=VerificationRequest.STATUS_PENDING,
        )
        self.assertTrue(user.has_pending_verification)

    def test_verified_address_returns_approved_address(self):
        user = User.objects.create_user(username="u8", password="testpass123")
        VerificationRequest.objects.create(
            user=user,
            address="200 Park Ave",
            document_type="utility_bill",
            status=VerificationRequest.STATUS_APPROVED,
            reviewed_at="2026-01-01T00:00:00Z",
        )
        self.assertEqual(user.verified_address, "200 Park Ave")

    def test_verified_address_none_if_no_approved(self):
        user = User.objects.create_user(username="u9", password="testpass123")
        self.assertIsNone(user.verified_address)


# ============================================================ #
#  VerificationRequest Model
# ============================================================ #


class VerificationRequestModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="vruser", password="testpass123")

    def test_create_request(self):
        vr = VerificationRequest.objects.create(
            user=self.user,
            address="123 Main St, Apt 4B",
            borough="MANHATTAN",
            zip_code="10001",
            document_type="lease",
            document_description="Lease dated Jan 2026",
        )
        self.assertEqual(vr.status, VerificationRequest.STATUS_PENDING)
        self.assertTrue(vr.is_pending)
        self.assertFalse(vr.is_approved)
        self.assertFalse(vr.is_rejected)

    def test_str(self):
        vr = VerificationRequest.objects.create(
            user=self.user,
            address="456 Elm St",
            document_type="utility_bill",
        )
        self.assertIn("vruser", str(vr))
        self.assertIn("456 Elm St", str(vr))

    def test_ordering(self):
        VerificationRequest.objects.create(
            user=self.user, address="A", document_type="lease"
        )
        vr2 = VerificationRequest.objects.create(
            user=self.user, address="B", document_type="lease"
        )
        first = VerificationRequest.objects.first()
        self.assertEqual(first.pk, vr2.pk)


# ============================================================ #
#  Registration (#44 — ease of signup)
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
        self.assertEqual(response.status_code, 200)
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

    def test_register_rejects_weak_password_without_complexity(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "weakpass",
                "email": "weak@example.com",
                "first_name": "Weak",
                "last_name": "Pass",
                "password1": "pqrstuvw",
                "password2": "pqrstuvw",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Password must include uppercase, lowercase, number, and symbol characters.",
        )
        self.assertFalse(User.objects.filter(username="weakpass").exists())

    def test_register_page_shows_password_requirements(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "uppercase, lowercase, number, and symbol characters",
        )

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
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_redirected_from_login(self):
        self.client.login(username="loginuser", password="StrongPass99!")
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 302)


# ============================================================ #
#  Logout
# ============================================================ #


class LogoutViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="logoutuser", password="testpass123"
        )

    def test_logout_redirects(self):
        self.client.login(username="logoutuser", password="testpass123")
        response = self.client.post(reverse("logout"))
        self.assertIn(response.status_code, [200, 302])


# ============================================================ #
#  Profile (#43 — saved user profile)
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

    def test_profile_update_rejects_blank_required_fields(self):
        self.client.login(username="profuser", password="StrongPass99!")
        response = self.client.post(
            reverse("profile"),
            {
                "first_name": "",
                "last_name": "",
                "email": "",
                "phone_number": "5551234567",
                "bio": "Hello world",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.", count=3)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Prof")
        self.assertEqual(self.user.last_name, "User")
        self.assertEqual(self.user.email, "prof@test.com")

    def test_profile_shows_role_badge(self):
        self.client.login(username="profuser", password="StrongPass99!")
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Public User")

    def test_profile_shows_verified_badge(self):
        self.user.role = User.ROLE_VERIFIED_TENANT
        self.user.save()
        self.client.login(username="profuser", password="StrongPass99!")
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Verified Tenant")
        self.assertContains(response, "verified-badge")

    def test_profile_shows_verification_history(self):
        self.client.login(username="profuser", password="StrongPass99!")
        VerificationRequest.objects.create(
            user=self.user, address="99 Test St", document_type="lease"
        )
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "99 Test St")

    def test_profile_shows_request_verification_link_for_unverified(self):
        self.client.login(username="profuser", password="StrongPass99!")
        response = self.client.get(reverse("profile"))
        self.assertContains(response, "Request Verification")

    def test_profile_no_request_link_for_verified_user(self):
        self.user.role = User.ROLE_VERIFIED_TENANT
        self.user.save()
        self.client.login(username="profuser", password="StrongPass99!")
        response = self.client.get(reverse("profile"))
        self.assertNotContains(response, "Request Verification")


# ============================================================ #
#  Verification Request (#46 — tenant requests verification)
# ============================================================ #


class RequestVerificationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tenant1", password="StrongPass99!"
        )

    def test_requires_login(self):
        response = self.client.get(reverse("request-verification"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_page_loads(self):
        self.client.login(username="tenant1", password="StrongPass99!")
        response = self.client.get(reverse("request-verification"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Request Tenant Verification")

    def test_submit_verification_request(self):
        self.client.login(username="tenant1", password="StrongPass99!")
        response = self.client.post(
            reverse("request-verification"),
            {
                "address": "123 Main St, Apt 4B",
                "borough": "MANHATTAN",
                "zip_code": "10001",
                "document_type": "lease",
                "document_description": "Lease agreement dated Jan 2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(VerificationRequest.objects.filter(user=self.user).exists())
        vr = VerificationRequest.objects.get(user=self.user)
        self.assertEqual(vr.status, VerificationRequest.STATUS_PENDING)
        self.assertEqual(vr.address, "123 Main St, Apt 4B")

    def test_already_verified_redirects(self):
        self.user.role = User.ROLE_VERIFIED_TENANT
        self.user.save()
        self.client.login(username="tenant1", password="StrongPass99!")
        response = self.client.get(reverse("request-verification"))
        self.assertEqual(response.status_code, 302)

    def test_duplicate_pending_blocked(self):
        self.client.login(username="tenant1", password="StrongPass99!")
        VerificationRequest.objects.create(
            user=self.user,
            address="Old address",
            document_type="lease",
            status=VerificationRequest.STATUS_PENDING,
        )
        response = self.client.post(
            reverse("request-verification"),
            {
                "address": "New address",
                "borough": "BROOKLYN",
                "zip_code": "11201",
                "document_type": "utility_bill",
                "document_description": "ConEd bill",
            },
        )
        self.assertEqual(response.status_code, 200)  # re-renders with error
        self.assertEqual(VerificationRequest.objects.filter(user=self.user).count(), 1)

    def test_can_resubmit_after_rejection(self):
        self.client.login(username="tenant1", password="StrongPass99!")
        VerificationRequest.objects.create(
            user=self.user,
            address="Old address",
            document_type="lease",
            status=VerificationRequest.STATUS_REJECTED,
        )
        response = self.client.post(
            reverse("request-verification"),
            {
                "address": "New address",
                "borough": "QUEENS",
                "zip_code": "11375",
                "document_type": "bank_statement",
                "document_description": "Chase statement",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(VerificationRequest.objects.filter(user=self.user).count(), 2)

    @override_settings(MEDIA_ROOT="/tmp/tenantguard_test_media/")
    def test_submit_with_document_upload(self):
        self.client.login(username="tenant1", password="StrongPass99!")
        doc = SimpleUploadedFile(
            "lease.pdf",
            b"%PDF-1.4 fake content",
            content_type="application/pdf",
        )
        response = self.client.post(
            reverse("request-verification"),
            {
                "address": "500 Broadway",
                "borough": "MANHATTAN",
                "zip_code": "10012",
                "document_type": "lease",
                "document_description": "Lease dated Jan 2026",
                "document": doc,
            },
        )
        self.assertEqual(response.status_code, 302)
        vr = VerificationRequest.objects.get(user=self.user)
        self.assertTrue(vr.document)
        self.assertIn("lease", vr.document.name)

    def test_submit_without_document_still_works(self):
        self.client.login(username="tenant1", password="StrongPass99!")
        response = self.client.post(
            reverse("request-verification"),
            {
                "address": "600 Broadway",
                "borough": "MANHATTAN",
                "zip_code": "10012",
                "document_type": "utility_bill",
                "document_description": "ConEd bill",
            },
        )
        self.assertEqual(response.status_code, 302)
        vr = VerificationRequest.objects.get(user=self.user)
        self.assertFalse(vr.document)

    def test_rejects_invalid_file_type(self):
        self.client.login(username="tenant1", password="StrongPass99!")
        bad_file = SimpleUploadedFile(
            "malware.exe",
            b"malicious content",
            content_type="application/octet-stream",
        )
        response = self.client.post(
            reverse("request-verification"),
            {
                "address": "700 Broadway",
                "borough": "MANHATTAN",
                "zip_code": "10012",
                "document_type": "lease",
                "document": bad_file,
            },
        )
        self.assertEqual(response.status_code, 200)  # re-renders with error
        self.assertFalse(VerificationRequest.objects.filter(user=self.user).exists())
        self.assertContains(response, "Unsupported file type")


class VerificationStatusViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="statususer", password="StrongPass99!"
        )

    def test_requires_login(self):
        response = self.client.get(reverse("verification-status"))
        self.assertEqual(response.status_code, 302)

    def test_shows_empty_state(self):
        self.client.login(username="statususer", password="StrongPass99!")
        response = self.client.get(reverse("verification-status"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "haven't submitted")

    def test_shows_verification_requests(self):
        self.client.login(username="statususer", password="StrongPass99!")
        VerificationRequest.objects.create(
            user=self.user, address="55 Water St", document_type="lease"
        )
        response = self.client.get(reverse("verification-status"))
        self.assertContains(response, "55 Water St")


# ============================================================ #
#  Admin Verification Queue (#47 — admin approve/reject)
# ============================================================ #


class AdminVerificationQueueViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin1", password="StrongPass99!", role=User.ROLE_ADMIN
        )
        self.public = User.objects.create_user(
            username="public1", password="StrongPass99!"
        )
        self.applicant = User.objects.create_user(
            username="applicant1", password="StrongPass99!"
        )
        self.vr = VerificationRequest.objects.create(
            user=self.applicant,
            address="100 Broadway",
            borough="MANHATTAN",
            document_type="lease",
        )

    def test_public_user_denied(self):
        self.client.login(username="public1", password="StrongPass99!")
        response = self.client.get(reverse("admin-verification-queue"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_redirected(self):
        response = self.client.get(reverse("admin-verification-queue"))
        self.assertEqual(response.status_code, 302)

    def test_admin_sees_queue(self):
        self.client.login(username="admin1", password="StrongPass99!")
        response = self.client.get(reverse("admin-verification-queue"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "100 Broadway")
        self.assertContains(response, "applicant1")

    def test_queue_filter_pending(self):
        self.client.login(username="admin1", password="StrongPass99!")
        response = self.client.get(
            reverse("admin-verification-queue"), {"status": "pending"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "100 Broadway")

    def test_queue_filter_approved_empty(self):
        self.client.login(username="admin1", password="StrongPass99!")
        response = self.client.get(
            reverse("admin-verification-queue"), {"status": "approved"}
        )
        self.assertNotContains(response, "100 Broadway")

    def test_queue_filter_all(self):
        self.client.login(username="admin1", password="StrongPass99!")
        response = self.client.get(
            reverse("admin-verification-queue"), {"status": "all"}
        )
        self.assertContains(response, "100 Broadway")


class AdminVerificationReviewViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin2", password="StrongPass99!", role=User.ROLE_ADMIN
        )
        self.applicant = User.objects.create_user(
            username="applicant2", password="StrongPass99!"
        )
        self.vr = VerificationRequest.objects.create(
            user=self.applicant,
            address="200 Park Ave",
            borough="MANHATTAN",
            nta_code="MN03",
            zip_code="10166",
            document_type="utility_bill",
            document_description="ConEd bill Feb 2026",
        )

    def test_review_page_loads(self):
        self.client.login(username="admin2", password="StrongPass99!")
        response = self.client.get(
            reverse("admin-verification-review", args=[self.vr.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "200 Park Ave")
        self.assertContains(response, "applicant2")

    def test_approve_request(self):
        from communities.models import Community, CommunityMembership
        from mapview.models import NTARiskScore

        # Create NTA and Community for auto-assignment
        nta = NTARiskScore.objects.create(
            nta_code="MN03", nta_name="Midtown", borough="Manhattan"
        )
        community = Community.objects.create(nta=nta, name="Midtown Community")

        self.client.login(username="admin2", password="StrongPass99!")
        response = self.client.post(
            reverse("admin-verification-review", args=[self.vr.pk]),
            {"action": "approve", "admin_notes": "Verified via ConEd bill"},
        )
        self.assertEqual(response.status_code, 302)
        self.vr.refresh_from_db()
        self.applicant.refresh_from_db()
        self.assertEqual(self.vr.status, VerificationRequest.STATUS_APPROVED)
        self.assertEqual(self.vr.admin_notes, "Verified via ConEd bill")
        self.assertEqual(self.vr.reviewed_by, self.admin)
        self.assertIsNotNone(self.vr.reviewed_at)
        self.assertEqual(self.applicant.role, User.ROLE_VERIFIED_TENANT)

        # Verify automatic community membership creation
        membership = CommunityMembership.objects.filter(
            user=self.applicant, community=community
        ).first()
        self.assertIsNotNone(membership)
        self.assertTrue(membership.is_active)

    def test_reject_request(self):
        self.client.login(username="admin2", password="StrongPass99!")
        response = self.client.post(
            reverse("admin-verification-review", args=[self.vr.pk]),
            {"action": "reject", "admin_notes": "Document unclear"},
        )
        self.assertEqual(response.status_code, 302)
        self.vr.refresh_from_db()
        self.applicant.refresh_from_db()
        self.assertEqual(self.vr.status, VerificationRequest.STATUS_REJECTED)
        self.assertEqual(self.applicant.role, User.ROLE_PUBLIC)  # role unchanged

    def test_public_user_cannot_review(self):
        User.objects.create_user(username="pub", password="StrongPass99!")
        self.client.login(username="pub", password="StrongPass99!")
        response = self.client.get(
            reverse("admin-verification-review", args=[self.vr.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_404_for_nonexistent_request(self):
        self.client.login(username="admin2", password="StrongPass99!")
        response = self.client.get(reverse("admin-verification-review", args=[99999]))
        self.assertEqual(response.status_code, 404)


# ============================================================ #
#  Verified badge visibility (#45)
# ============================================================ #


class VerifiedBadgeTests(TestCase):
    def test_nav_shows_verified_badge(self):
        User.objects.create_user(
            username="vuser", password="StrongPass99!", role=User.ROLE_VERIFIED_TENANT
        )
        self.client.login(username="vuser", password="StrongPass99!")
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "nav-verified")

    def test_nav_no_badge_for_public(self):
        User.objects.create_user(username="puser", password="StrongPass99!")
        self.client.login(username="puser", password="StrongPass99!")
        response = self.client.get(reverse("dashboard"))
        self.assertNotContains(response, "nav-verified")


# ============================================================ #
#  Permission gates (decorators)
# ============================================================ #


class PermissionGateTests(TestCase):
    """
    Test the verified_tenant_required and admin_required decorators
    indirectly through the admin queue view (admin_required) and
    ensure public users get 403.
    """

    def test_admin_required_blocks_public(self):
        User.objects.create_user(username="pub2", password="StrongPass99!")
        self.client.login(username="pub2", password="StrongPass99!")
        response = self.client.get(reverse("admin-verification-queue"))
        self.assertEqual(response.status_code, 403)

    def test_admin_required_allows_admin_role(self):
        User.objects.create_user(
            username="adm", password="StrongPass99!", role=User.ROLE_ADMIN
        )
        self.client.login(username="adm", password="StrongPass99!")
        response = self.client.get(reverse("admin-verification-queue"))
        self.assertEqual(response.status_code, 200)

    def test_admin_required_allows_superuser(self):
        User.objects.create_superuser(
            username="su2", password="StrongPass99!", email="su2@test.com"
        )
        self.client.login(username="su2", password="StrongPass99!")
        response = self.client.get(reverse("admin-verification-queue"))
        self.assertEqual(response.status_code, 200)
