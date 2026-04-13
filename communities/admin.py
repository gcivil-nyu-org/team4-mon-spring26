from django.contrib import admin

from .models import Comment, Community, CommunityMembership, DirectMessage, Post, Report


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ["name", "nta", "member_count", "post_count", "created_at"]
    search_fields = ["name"]


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "community", "is_active", "joined_at"]
    list_filter = ["is_active"]
    raw_id_fields = ["user", "community"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "nta",
        "author",
        "category",
        "is_pinned",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_pinned", "is_active", "category", "created_at"]
    search_fields = ["title", "content", "author__username"]
    raw_id_fields = ["author"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["id", "post", "author", "created_at"]
    search_fields = ["content", "author__username"]
    raw_id_fields = ["author", "post"]


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "sender", "receiver", "is_read", "created_at"]
    list_filter = ["is_read"]
    search_fields = ["sender__username", "receiver__username", "content"]
    raw_id_fields = ["sender", "receiver"]


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["id", "reported_by", "report_target", "resolved", "created_at"]
    list_filter = ["resolved"]
    search_fields = ["reason", "reported_by__username"]
    raw_id_fields = ["reported_by", "reported_user", "post", "comment", "message"]

    @admin.display(description="Target")
    def report_target(self, obj):
        if obj.post:
            return f"Post: {obj.post.title[:30]}"
        elif obj.comment:
            return f"Comment #{obj.comment.id}"
        elif obj.message:
            return f"Message #{obj.message.id}"
        elif obj.reported_user:
            return f"User: {obj.reported_user.username}"
        return "Unknown"
