from django.urls import path
from . import views

app_name = "communities"

urlpatterns = [
    path("", views.forum_index, name="index"),
    path("<str:nta_code>/", views.nta_forum, name="nta_forum"),
    path("<str:nta_code>/post/new/", views.create_post, name="create_post"),
    path("<str:nta_code>/post/<int:post_id>/", views.post_detail, name="post_detail"),
    path("<str:nta_code>/report/", views.report_content, name="report_content"),
]
