from django.urls import path
from . import views
from . import views_api

app_name = "communities"

urlpatterns = [
    path("", views.forum_index, name="index"),
    # My posts
    path("my-posts/", views.my_posts_view, name="my_posts"),
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
    # Community API (JSON)
    path("api/list/", views_api.community_list_api, name="api_community_list"),
    path("api/my/", views_api.my_community_api, name="api_my_community"),
    path(
        "api/<str:nta_code>/detail/",
        views_api.community_detail_api,
        name="api_community_detail",
    ),
    path(
        "api/<str:nta_code>/posts/",
        views_api.community_posts_api,
        name="api_community_posts",
    ),
    path("api/my-posts/", views_api.my_posts_api, name="api_my_posts"),
    # HTML views (must be last due to <str:nta_code> catch-all)
    path("<str:nta_code>/", views.nta_forum, name="nta_forum"),
    path("<str:nta_code>/post/new/", views.create_post, name="create_post"),
    path(
        "<str:nta_code>/post/<int:post_id>/",
        views.post_detail,
        name="post_detail",
    ),
    path(
        "<str:nta_code>/post/<int:post_id>/edit/",
        views.edit_post,
        name="edit_post",
    ),
    path(
        "<str:nta_code>/post/<int:post_id>/delete/",
        views.delete_post,
        name="delete_post",
    ),
    path("<str:nta_code>/report/", views.report_content, name="report_content"),
]
