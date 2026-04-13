from django.db import models
from django.conf import settings
from mapview.models import NTARiskScore


class Community(models.Model):
    """One community per NTA neighbourhood — auto-created via management command."""

    nta = models.OneToOneField(
        NTARiskScore,
        on_delete=models.CASCADE,
        related_name="community",
        to_field="nta_code",
        db_column="nta_code",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Community"
        verbose_name_plural = "Communities"
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.members.filter(is_active=True).count()

    @property
    def post_count(self):
        return self.nta.posts.filter(is_active=True).count()


class CommunityMembership(models.Model):
    """Links a user to their NTA community based on verified address."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_memberships",
    )
    community = models.ForeignKey(
        Community, on_delete=models.CASCADE, related_name="members"
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "community")
        verbose_name = "Community Membership"
        verbose_name_plural = "Community Memberships"

    def __str__(self):
        return f"{self.user.username} → {self.community.name}"


class Post(models.Model):
    CATEGORY_CHOICES = [
        ("general", "General Discussion"),
        ("maintenance", "Maintenance Issue"),
        ("safety", "Safety Concern"),
        ("landlord", "Landlord Issue"),
        ("noise", "Noise Complaint"),
        ("organizing", "Organizing/Meetup"),
        ("question", "Question"),
        ("resource", "Resource Sharing"),
    ]

    nta = models.ForeignKey(
        NTARiskScore,
        on_delete=models.CASCADE,
        related_name="posts",
        to_field="nta_code",
        db_column="nta_code",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_posts",
    )
    title = models.CharField(max_length=200)
    content = models.TextField(max_length=5000)
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="general"
    )
    linked_address = models.CharField(max_length=300, blank=True, default="")
    linked_lat = models.FloatField(null=True, blank=True)
    linked_lng = models.FloatField(null=True, blank=True)
    image = models.ImageField(upload_to="community_posts/%Y/%m/", blank=True, null=True)
    is_pinned = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return f"{self.title} [{self.nta.nta_code}]"

    @property
    def reply_count(self):
        return self.comments.count()


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_comments",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author.username} on {self.post.title}"


class DirectMessage(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_messages",
    )
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message from {self.sender.username} to {self.receiver.username}"


class Report(models.Model):
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, null=True, blank=True, related_name="reports"
    )
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, null=True, blank=True, related_name="reports"
    )
    message = models.ForeignKey(
        DirectMessage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports",
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports_against",
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submitted_reports",
    )
    reason = models.TextField(help_text="Reason for reporting this content.")
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        if self.post:
            target = f"Post: {self.post.title}"
        elif self.comment:
            target = f"Comment: {self.comment.id}"
        elif self.message:
            target = f"Message: {self.message.id}"
        elif self.reported_user:
            target = f"User: {self.reported_user.username}"
        else:
            target = "Unknown"

        return f"Report on {target} by {self.reported_by.username}"
