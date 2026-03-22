from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied

from mapview.models import NTARiskScore
from .models import Post, Comment
from .forms import PostForm, CommentForm, ReportForm


def is_verified_for_nta(user, nta_code):
    """Helper to check if user implicitly has access to post in this NTA"""
    if not user.is_authenticated:
        return False
    if getattr(user, "is_admin_user", False):
        return True  # Admins can post anywhere
    if getattr(user, "is_verified_tenant", False):
        # Check their verified NTA
        return user.verified_nta_code == nta_code
    return False


def forum_index(request):
    """List of all NTA forums, or redirect to user's local forum."""
    ntas = NTARiskScore.objects.all().order_by("nta_name")
    context = {
        "ntas": ntas,
    }
    return render(request, "communities/index.html", context)


def nta_forum(request, nta_code):
    nta = get_object_or_404(NTARiskScore, nta_code=nta_code)
    posts = nta.posts.all().select_related("author")
    can_post = is_verified_for_nta(request.user, nta_code)

    context = {
        "nta": nta,
        "posts": posts,
        "can_post": can_post,
    }
    return render(request, "communities/forum.html", context)


def post_detail(request, nta_code, post_id):
    nta = get_object_or_404(NTARiskScore, nta_code=nta_code)
    post = get_object_or_404(Post, id=post_id, nta=nta)
    comments = post.comments.all().select_related("author")

    can_post = is_verified_for_nta(request.user, nta_code)

    form = CommentForm()

    if request.method == "POST" and can_post:
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.save()
            messages.success(request, "Comment added successfully.")
            return redirect(
                "communities:post_detail", nta_code=nta.nta_code, post_id=post.id
            )

    context = {
        "nta": nta,
        "post": post,
        "comments": comments,
        "form": form,
        "can_post": can_post,
    }
    return render(request, "communities/post_detail.html", context)


@login_required
def create_post(request, nta_code):
    nta = get_object_or_404(NTARiskScore, nta_code=nta_code)

    # Must be verified for this specific NTA
    if not is_verified_for_nta(request.user, nta_code):
        messages.error(
            request, f"You must be a verified resident of {nta.nta_name} to post."
        )
        return redirect("communities:nta_forum", nta_code=nta.nta_code)

    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.nta = nta
            post.author = request.user
            post.save()
            messages.success(request, "Discussion started successfully.")
            return redirect(
                "communities:post_detail", nta_code=nta.nta_code, post_id=post.id
            )
    else:
        form = PostForm()

    context = {
        "nta": nta,
        "form": form,
    }
    return render(request, "communities/create_post.html", context)


@login_required
def report_content(request, nta_code):
    nta = get_object_or_404(NTARiskScore, nta_code=nta_code)
    post_id = request.GET.get("post_id")
    comment_id = request.GET.get("comment_id")

    post = None
    comment = None

    if post_id:
        post = get_object_or_404(Post, id=post_id, nta=nta)
    elif comment_id:
        comment = get_object_or_404(Comment, id=comment_id, post__nta=nta)
    else:
        raise PermissionDenied("Must provide post_id or comment_id to report.")

    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reported_by = request.user
            if post:
                report.post = post
            if comment:
                report.comment = comment
            report.save()

            messages.success(request, "Report submitted successfully to admins.")
            # Redirect back to the context
            redirect_post_id = post.id if post else comment.post.id
            return redirect(
                "communities:post_detail",
                nta_code=nta.nta_code,
                post_id=redirect_post_id,
            )
    else:
        form = ReportForm()

    context = {
        "nta": nta,
        "form": form,
        "post": post,
        "comment": comment,
    }
    return render(request, "communities/report.html", context)
