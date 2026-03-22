from django.test import TestCase
from django.urls import reverse

from accounts.models import User, VerificationRequest
from mapview.models import NTARiskScore
from .models import Post, Comment, Report


class CommunitiesTests(TestCase):
    def setUp(self):
        # Create NTA
        self.nta = NTARiskScore.objects.create(
            nta_code="MN01", nta_name="Marble Hill-Inwood", borough="Manhattan"
        )
        self.nta2 = NTARiskScore.objects.create(
            nta_code="BK01", nta_name="Greenpoint", borough="Brooklyn"
        )

        # Create Users
        self.public_user = User.objects.create_user(
            username="public", password="password123", role=User.ROLE_PUBLIC
        )

        self.verified_user = User.objects.create_user(
            username="verified_mn01",
            password="password123",
            role=User.ROLE_VERIFIED_TENANT,
        )
        VerificationRequest.objects.create(
            user=self.verified_user,
            nta_code="MN01",
            status=VerificationRequest.STATUS_APPROVED,
            document_type="lease",
        )

        self.verified_user2 = User.objects.create_user(
            username="verified_bk01",
            password="password123",
            role=User.ROLE_VERIFIED_TENANT,
        )
        VerificationRequest.objects.create(
            user=self.verified_user2,
            nta_code="BK01",
            status=VerificationRequest.STATUS_APPROVED,
            document_type="lease",
        )

        # Create Post
        self.post = Post.objects.create(
            nta=self.nta,
            author=self.verified_user,
            title="Heating issues in building A",
            content="Anyone else having no heat?",
        )

    def test_forum_index_read_access(self):
        """Any user can view the communities index."""
        response = self.client.get(reverse("communities:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Marble Hill-Inwood")

    def test_nta_forum_read_access(self):
        """Any user can view an NTA forum."""
        response = self.client.get(
            reverse("communities:nta_forum", args=[self.nta.nta_code])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Heating issues in building A")

    def test_post_detail_read_access(self):
        """Any user can read a post inside a forum."""
        response = self.client.get(
            reverse("communities:post_detail", args=[self.nta.nta_code, self.post.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Anyone else having no heat?")

    def test_unverified_cannot_post(self):
        """Public users cannot post to a forum."""
        self.client.login(username="public", password="password123")
        # Should be blocked and redirected
        response = self.client.get(
            reverse("communities:create_post", args=[self.nta.nta_code])
        )
        self.assertRedirects(
            response, reverse("communities:nta_forum", args=[self.nta.nta_code])
        )

        response = self.client.post(
            reverse("communities:create_post", args=[self.nta.nta_code]),
            {"title": "Test", "content": "Test"},
        )
        self.assertRedirects(
            response, reverse("communities:nta_forum", args=[self.nta.nta_code])
        )

    def test_verified_wrong_nta_cannot_post(self):
        """Verified users cannot post in an NTA they don't reside in."""
        self.client.login(username="verified_bk01", password="password123")
        response = self.client.post(
            reverse("communities:create_post", args=[self.nta.nta_code]),
            {"title": "Test", "content": "Test"},
        )
        self.assertRedirects(
            response, reverse("communities:nta_forum", args=[self.nta.nta_code])
        )

    def test_verified_correct_nta_can_post_and_comment(self):
        """Verified users can post in their own NTA forum."""
        self.client.login(username="verified_mn01", password="password123")

        # Test creation view
        response = self.client.get(
            reverse("communities:create_post", args=[self.nta.nta_code])
        )
        self.assertEqual(response.status_code, 200)

        # Submit post
        response = self.client.post(
            reverse("communities:create_post", args=[self.nta.nta_code]),
            {"title": "New Resident", "content": "Hello everyone!"},
        )
        new_post = Post.objects.get(title="New Resident")
        self.assertRedirects(
            response,
            reverse("communities:post_detail", args=[self.nta.nta_code, new_post.id]),
        )

        # Test commenting
        response = self.client.post(
            reverse("communities:post_detail", args=[self.nta.nta_code, self.post.id]),
            {"content": "I am having the same issue."},
        )
        self.assertRedirects(
            response,
            reverse("communities:post_detail", args=[self.nta.nta_code, self.post.id]),
        )
        self.assertTrue(
            Comment.objects.filter(content="I am having the same issue.").exists()
        )

    def test_create_report(self):
        """Logged in users can report a post."""
        self.client.login(username="public", password="password123")

        response = self.client.post(
            reverse("communities:report_content", args=[self.nta.nta_code])
            + f"?post_id={self.post.id}",
            {"reason": "Spam post"},
        )
        self.assertRedirects(
            response,
            reverse("communities:post_detail", args=[self.nta.nta_code, self.post.id]),
        )
        self.assertTrue(Report.objects.filter(reason="Spam post").exists())

    def test_report_user(self):
        self.client.login(username="public", password="password123")
        self.client.post(
            reverse("communities:report_content", args=[self.nta.nta_code])
            + f"?user_id={self.verified_user.id}",
            {"reason": "Suspicious"},
        )
        self.assertTrue(
            Report.objects.filter(reported_user=self.verified_user).exists()
        )

    def test_moderation_queue(self):
        User.objects.create_superuser(username="admin1", password="password123")
        self.client.login(username="admin1", password="password123")
        response = self.client.get(reverse("communities:moderation_queue"))
        self.assertEqual(response.status_code, 200)

    def test_ban_user(self):
        User.objects.create_superuser(username="admin2", password="password123")
        self.client.login(username="admin2", password="password123")
        Report.objects.create(
            reported_user=self.verified_user,
            reported_by=self.public_user,
            reason="Spam",
        )
        self.client.post(reverse("communities:ban_user", args=[self.verified_user.id]))
        self.verified_user.refresh_from_db()
        self.assertFalse(self.verified_user.is_active)

    def test_inbox_access(self):
        """Only verified tenants can access inbox."""
        self.client.login(username="public", password="password123")
        response = self.client.get(reverse("communities:inbox"))
        self.assertRedirects(response, reverse("communities:index"))

        self.client.login(username="verified_mn01", password="password123")
        response = self.client.get(reverse("communities:inbox"))
        self.assertEqual(response.status_code, 200)

    def test_direct_messaging(self):
        """Verified tenants can message each other."""
        self.client.login(username="verified_mn01", password="password123")
        # Send message
        response = self.client.post(
            reverse("communities:chat", args=[self.verified_user2.id]),
            {"content": "Hello neighbor!"},
        )
        self.assertRedirects(
            response, reverse("communities:chat", args=[self.verified_user2.id])
        )

        # Check receiver inbox
        self.client.login(username="verified_bk01", password="password123")
        response = self.client.get(reverse("communities:inbox"))
        self.assertContains(response, "Hello neighbor!")
