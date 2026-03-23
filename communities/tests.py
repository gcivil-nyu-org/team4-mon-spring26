from django.test import TestCase
from django.urls import reverse

from accounts.models import User, VerificationRequest
from mapview.models import NTARiskScore
from .models import Comment, DirectMessage, Post, Report

# ============================================================ #
#  Model __str__ tests
# ============================================================ #


class PostModelTests(TestCase):
    def setUp(self):
        self.nta = NTARiskScore.objects.create(
            nta_code="MN01", nta_name="Inwood", borough="Manhattan"
        )
        self.user = User.objects.create_user(username="poster", password="password123")

    def test_str(self):
        post = Post.objects.create(
            nta=self.nta, author=self.user, title="Heat issue", content="No heat"
        )
        self.assertEqual(str(post), "Heat issue [MN01]")


class CommentModelTests(TestCase):
    def setUp(self):
        self.nta = NTARiskScore.objects.create(
            nta_code="MN01", nta_name="Inwood", borough="Manhattan"
        )
        self.user = User.objects.create_user(
            username="commenter", password="password123"
        )
        self.post = Post.objects.create(
            nta=self.nta, author=self.user, title="Post A", content="body"
        )

    def test_str(self):
        comment = Comment.objects.create(
            post=self.post, author=self.user, content="Reply"
        )
        self.assertIn("commenter", str(comment))
        self.assertIn("Post A", str(comment))


class DirectMessageModelTests(TestCase):
    def test_str(self):
        u1 = User.objects.create_user(username="sender", password="password123")
        u2 = User.objects.create_user(username="receiver", password="password123")
        msg = DirectMessage.objects.create(sender=u1, receiver=u2, content="Hi")
        self.assertIn("sender", str(msg))
        self.assertIn("receiver", str(msg))


class ReportModelTests(TestCase):
    def setUp(self):
        self.nta = NTARiskScore.objects.create(
            nta_code="MN01", nta_name="Inwood", borough="Manhattan"
        )
        self.user = User.objects.create_user(
            username="reporter", password="password123"
        )
        self.target = User.objects.create_user(
            username="target", password="password123"
        )

    def test_str_post_report(self):
        post = Post.objects.create(
            nta=self.nta, author=self.target, title="Bad post", content="x"
        )
        report = Report.objects.create(post=post, reported_by=self.user, reason="spam")
        self.assertIn("Post: Bad post", str(report))

    def test_str_comment_report(self):
        post = Post.objects.create(
            nta=self.nta, author=self.target, title="P", content="x"
        )
        comment = Comment.objects.create(
            post=post, author=self.target, content="bad comment"
        )
        report = Report.objects.create(
            comment=comment, reported_by=self.user, reason="rude"
        )
        self.assertIn("Comment:", str(report))

    def test_str_message_report(self):
        msg = DirectMessage.objects.create(
            sender=self.target, receiver=self.user, content="spam msg"
        )
        report = Report.objects.create(
            message=msg, reported_by=self.user, reason="spam"
        )
        self.assertIn("Message:", str(report))

    def test_str_user_report(self):
        report = Report.objects.create(
            reported_user=self.target, reported_by=self.user, reason="fake"
        )
        self.assertIn("User: target", str(report))

    def test_str_unknown_report(self):
        report = Report.objects.create(reported_by=self.user, reason="unclear")
        self.assertIn("Unknown", str(report))


# ============================================================ #
#  View tests
# ============================================================ #


class CommunitiesTests(TestCase):
    def setUp(self):
        self.nta = NTARiskScore.objects.create(
            nta_code="MN01", nta_name="Marble Hill-Inwood", borough="Manhattan"
        )
        self.nta2 = NTARiskScore.objects.create(
            nta_code="BK01", nta_name="Greenpoint", borough="Brooklyn"
        )

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

        response = self.client.get(
            reverse("communities:create_post", args=[self.nta.nta_code])
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("communities:create_post", args=[self.nta.nta_code]),
            {"title": "New Resident", "content": "Hello everyone!"},
        )
        new_post = Post.objects.get(title="New Resident")
        self.assertRedirects(
            response,
            reverse("communities:post_detail", args=[self.nta.nta_code, new_post.id]),
        )

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

    def test_report_comment(self):
        """Logged in users can report a comment."""
        self.client.login(username="verified_mn01", password="password123")
        comment = Comment.objects.create(
            post=self.post, author=self.verified_user, content="bad stuff"
        )
        self.client.login(username="public", password="password123")
        response = self.client.post(
            reverse("communities:report_content", args=[self.nta.nta_code])
            + f"?comment_id={comment.id}",
            {"reason": "Offensive comment"},
        )
        self.assertRedirects(
            response,
            reverse("communities:post_detail", args=[self.nta.nta_code, self.post.id]),
        )
        self.assertTrue(Report.objects.filter(comment=comment).exists())

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

    def test_report_no_target_raises_403(self):
        """Report without post_id/comment_id/user_id returns 403."""
        self.client.login(username="public", password="password123")
        response = self.client.get(
            reverse("communities:report_content", args=[self.nta.nta_code])
        )
        self.assertEqual(response.status_code, 403)

    def test_report_get_renders_form(self):
        """GET report page with post_id shows the report form."""
        self.client.login(username="public", password="password123")
        response = self.client.get(
            reverse("communities:report_content", args=[self.nta.nta_code])
            + f"?post_id={self.post.id}"
        )
        self.assertEqual(response.status_code, 200)

    def test_moderation_queue(self):
        User.objects.create_superuser(username="admin1", password="password123")
        self.client.login(username="admin1", password="password123")
        response = self.client.get(reverse("communities:moderation_queue"))
        self.assertEqual(response.status_code, 200)

    def test_resolve_report(self):
        User.objects.create_superuser(username="admin_resolve", password="password123")
        self.client.login(username="admin_resolve", password="password123")
        report = Report.objects.create(
            post=self.post, reported_by=self.public_user, reason="spam"
        )
        response = self.client.post(
            reverse("communities:resolve_report", args=[report.id])
        )
        self.assertRedirects(response, reverse("communities:moderation_queue"))
        report.refresh_from_db()
        self.assertTrue(report.resolved)

    def test_delete_reported_post(self):
        User.objects.create_superuser(username="admin_del", password="password123")
        self.client.login(username="admin_del", password="password123")
        post_to_delete = Post.objects.create(
            nta=self.nta, author=self.verified_user, title="Delete me", content="x"
        )
        report = Report.objects.create(
            post=post_to_delete, reported_by=self.public_user, reason="spam"
        )
        response = self.client.post(
            reverse("communities:delete_content", args=[report.id])
        )
        self.assertRedirects(response, reverse("communities:moderation_queue"))
        self.assertFalse(Post.objects.filter(title="Delete me").exists())
        report.refresh_from_db()
        self.assertTrue(report.resolved)

    def test_delete_reported_comment(self):
        User.objects.create_superuser(username="admin_delc", password="password123")
        self.client.login(username="admin_delc", password="password123")
        comment = Comment.objects.create(
            post=self.post, author=self.verified_user, content="delete this"
        )
        report = Report.objects.create(
            comment=comment, reported_by=self.public_user, reason="rude"
        )
        response = self.client.post(
            reverse("communities:delete_content", args=[report.id])
        )
        self.assertRedirects(response, reverse("communities:moderation_queue"))
        self.assertFalse(Comment.objects.filter(content="delete this").exists())

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

    def test_chat_public_user_blocked(self):
        """Public (non-verified) users cannot access chat."""
        self.client.login(username="public", password="password123")
        response = self.client.get(
            reverse("communities:chat", args=[self.verified_user.id])
        )
        self.assertRedirects(response, reverse("communities:index"))

    def test_chat_to_non_verified_blocked(self):
        """Verified users cannot message non-verified users."""
        self.client.login(username="verified_mn01", password="password123")
        response = self.client.get(
            reverse("communities:chat", args=[self.public_user.id])
        )
        self.assertRedirects(response, reverse("communities:inbox"))

    def test_direct_messaging(self):
        """Verified tenants can message each other."""
        self.client.login(username="verified_mn01", password="password123")
        response = self.client.post(
            reverse("communities:chat", args=[self.verified_user2.id]),
            {"content": "Hello neighbor!"},
        )
        self.assertRedirects(
            response, reverse("communities:chat", args=[self.verified_user2.id])
        )

        self.client.login(username="verified_bk01", password="password123")
        response = self.client.get(reverse("communities:inbox"))
        self.assertContains(response, "Hello neighbor!")

    def test_chat_marks_messages_as_read(self):
        """Opening chat marks unread messages from other user as read."""
        DirectMessage.objects.create(
            sender=self.verified_user2,
            receiver=self.verified_user,
            content="Unread msg",
            is_read=False,
        )
        self.client.login(username="verified_mn01", password="password123")
        self.client.get(reverse("communities:chat", args=[self.verified_user2.id]))
        msg = DirectMessage.objects.get(content="Unread msg")
        self.assertTrue(msg.is_read)
