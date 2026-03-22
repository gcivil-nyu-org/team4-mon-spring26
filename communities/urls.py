from django.urls import path
from . import views

app_name = "communities"

urlpatterns = [
    path("", views.forum_index, name="index"),
    # Moderation paths
    path("moderation/queue/", views.moderation_queue, name="moderation_queue"),
    path(
        "moderation/report/<int:report_id>/resolve/",
        views.resolve_report,
        name="resolve_report",
    ),
    path(
        "moderation/report/<int:report_id>/delete_content/",
        views.delete_reported_content,
        name="delete_content",
    ),
    path("moderation/user/<int:user_id>/ban/", views.ban_user, name="ban_user"),
    # Regular user paths
    path("inbox/", views.inbox, name="inbox"),
    path("chat/<int:user_id>/", views.chat, name="chat"),
    path("<str:nta_code>/", views.nta_forum, name="nta_forum"),
    path("<str:nta_code>/post/new/", views.create_post, name="create_post"),
    path("<str:nta_code>/post/<int:post_id>/", views.post_detail, name="post_detail"),
    path("<str:nta_code>/report/", views.report_content, name="report_content"),
]
