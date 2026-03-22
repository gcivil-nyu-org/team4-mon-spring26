from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model

from mapview.models import NTARiskScore
from .models import Post, Comment, Report, DirectMessage
from .forms import PostForm, CommentForm, ReportForm, DirectMessageForm
from django.db.models import Q

User = get_user_model()


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
    user_id = request.GET.get("user_id")

    post = None
    comment = None
    reported_user = None

    if post_id:
        post = get_object_or_404(Post, id=post_id, nta=nta)
    elif comment_id:
        comment = get_object_or_404(Comment, id=comment_id, post__nta=nta)
    elif user_id:
        reported_user = get_object_or_404(User, id=user_id)
    else:
        raise PermissionDenied(
            "Must provide post_id, comment_id, or user_id to report."
        )

    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reported_by = request.user
            if post:
                report.post = post
            if comment:
                report.comment = comment
            if reported_user:
                report.reported_user = reported_user
            report.save()

            messages.success(request, "Report submitted successfully to admins.")
            # Redirect back to the context
            if post:
                return redirect(
                    "communities:post_detail", nta_code=nta.nta_code, post_id=post.id
                )
            elif comment:
                return redirect(
                    "communities:post_detail",
                    nta_code=nta.nta_code,
                    post_id=comment.post.id,
                )
            else:
                return redirect("communities:nta_forum", nta_code=nta.nta_code)
    else:
        form = ReportForm()

    context = {
        "nta": nta,
        "form": form,
        "post": post,
        "comment": comment,
        "reported_user": reported_user,
    }
    return render(request, "communities/report.html", context)


@user_passes_test(
    lambda u: u.is_authenticated
    and (u.is_staff or u.is_superuser or getattr(u, "is_admin_user", False))
)
def moderation_queue(request):
    reports = Report.objects.filter(resolved=False).select_related(
        "post", "comment", "reported_user", "reported_by"
    )
    context = {"reports": reports}
    return render(request, "communities/moderation_queue.html", context)


@user_passes_test(
    lambda u: u.is_authenticated
    and (u.is_staff or u.is_superuser or getattr(u, "is_admin_user", False))
)
def resolve_report(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    report.resolved = True
    report.save()
    messages.success(request, f"Report #{report.id} marked as resolved.")
    return redirect("communities:moderation_queue")


@user_passes_test(
    lambda u: u.is_authenticated
    and (u.is_staff or u.is_superuser or getattr(u, "is_admin_user", False))
)
def delete_reported_content(request, report_id):
    report = get_object_or_404(Report, id=report_id)
    if report.post:
        report.post.delete()
        messages.success(request, "Reported post has been deleted.")
    elif report.comment:
        report.comment.delete()
        messages.success(request, "Reported comment has been deleted.")

    report.resolved = True
    report.save()
    return redirect("communities:moderation_queue")


@user_passes_test(
    lambda u: u.is_authenticated
    and (u.is_staff or u.is_superuser or getattr(u, "is_admin_user", False))
)
def ban_user(request, user_id):
    user_to_ban = get_object_or_404(User, id=user_id)
    user_to_ban.is_active = False
    user_to_ban.save()
    messages.success(
        request, f"User {user_to_ban.username} has been banned (deactivated)."
    )

    # Resolve all outstanding reports against this user
    Report.objects.filter(reported_user=user_to_ban, resolved=False).update(
        resolved=True
    )

    return redirect("communities:moderation_queue")


@login_required
def inbox(request):
    if not getattr(request.user, 'is_verified_tenant', False) and not getattr(request.user, 'is_admin_user', False):
        messages.error(request, "Only verified tenants can access direct messages.")
        return redirect('communities:index')

    messages_qs = DirectMessage.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user)
    ).order_by('-created_at')

    users = set()
    latest_messages = []
    
    for msg in messages_qs:
        other_user = msg.receiver if msg.sender == request.user else msg.sender
        if other_user not in users:
            users.add(other_user)
            latest_messages.append(msg)

    context = {
        'conversations': latest_messages,
    }
    return render(request, 'communities/inbox.html', context)

@login_required
def chat(request, user_id):
    if not getattr(request.user, 'is_verified_tenant', False) and not getattr(request.user, 'is_admin_user', False):
        messages.error(request, "Only verified tenants can send or receive messages.")
        return redirect('communities:index')

    other_user = get_object_or_404(User, id=user_id)
    if not getattr(other_user, 'is_verified_tenant', False) and not getattr(other_user, 'is_admin_user', False):
        messages.error(request, "You can only message verified tenants.")
        return redirect('communities:inbox')

    DirectMessage.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)

    messages_qs = DirectMessage.objects.filter(
        Q(sender=request.user, receiver=other_user) | 
        Q(sender=other_user, receiver=request.user)
    ).order_by('created_at')

    if request.method == 'POST':
        form = DirectMessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.receiver = other_user
            msg.save()
            return redirect('communities:chat', user_id=other_user.id)
    else:
        form = DirectMessageForm()

    context = {
        'other_user': other_user,
        'chat_messages': messages_qs,
        'form': form,
    }
    return render(request, 'communities/chat.html', context)
