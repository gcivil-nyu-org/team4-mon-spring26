from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum, Value, IntegerField
from django.db.models.functions import Coalesce

from mapview.models import NTARiskScore
from .models import Community, Post, Comment, Report, DirectMessage, PostVote
from .forms import PostForm, CommentForm, ReportForm, DirectMessageForm

User = get_user_model()


def _posts_with_vote_data(queryset, user):
    posts = queryset.annotate(
        vote_score_value=Coalesce(
            Sum("votes__value"),
            Value(0),
            output_field=IntegerField(),
        )
    )
    if user.is_authenticated:
        user_votes = {
            vote.post_id: vote.value
            for vote in PostVote.objects.filter(
                user=user, post_id__in=posts.values_list("id", flat=True)
            )
        }
    else:
        user_votes = {}

    for post in posts:
        post.vote_score_value = getattr(post, "vote_score_value", 0)
        post.current_user_vote = user_votes.get(post.id, 0)
    return posts


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


def can_comment_in_nta(user, nta_code):
    """Only verified tenants of the matching NTA can comment."""
    return (
        user.is_authenticated
        and getattr(user, "is_verified_tenant", False)
        and user.verified_nta_code == nta_code
    )


def forum_index(request):
    """List of all NTA forums with My Community section."""
    search = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "name")

    communities = Community.objects.select_related("nta").annotate(
        active_members=Count("members", filter=Q(members__is_active=True)),
        active_posts=Count("nta__posts", filter=Q(nta__posts__is_active=True)),
    )

    if search:
        communities = communities.filter(name__icontains=search)

    sort_map = {
        "name": "name",
        "most_active": "-active_posts",
        "most_members": "-active_members",
        "highest_risk": "nta__risk_score",
    }
    communities = communities.order_by(sort_map.get(sort, "name"))

    # My community info
    my_community = None
    my_nta = None
    if request.user.is_authenticated and getattr(
        request.user, "is_verified_tenant", False
    ):
        nta_code = request.user.verified_nta_code
        if nta_code:
            try:
                my_community = Community.objects.select_related("nta").get(
                    nta_id=nta_code
                )
                my_nta = my_community.nta
            except Community.DoesNotExist:
                pass

    # Fallback: if no communities exist yet, show NTAs directly
    if not communities.exists():
        ntas = NTARiskScore.objects.all().order_by("nta_name")
    else:
        ntas = None

    context = {
        "communities": communities,
        "ntas": ntas,
        "my_community": my_community,
        "my_nta": my_nta,
        "search": search,
        "sort": sort,
    }
    return render(request, "communities/index.html", context)


def nta_forum(request, nta_code):
    nta = get_object_or_404(NTARiskScore, nta_code=nta_code)
    posts = _posts_with_vote_data(
        nta.posts.filter(is_active=True).select_related("author"),
        request.user,
    )
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
    post_vote = PostVote.objects.filter(post=post).aggregate(
        score=Coalesce(Sum("value"), Value(0), output_field=IntegerField())
    )
    post.vote_score_value = post_vote["score"]
    post.current_user_vote = 0
    if request.user.is_authenticated:
        existing_vote = PostVote.objects.filter(post=post, user=request.user).first()
        if existing_vote:
            post.current_user_vote = existing_vote.value

    can_post = is_verified_for_nta(request.user, nta_code)
    can_comment = can_comment_in_nta(request.user, nta_code)

    form = CommentForm()

    if request.method == "POST":
        if not can_comment:
            messages.error(
                request,
                f"You must be a verified resident of {nta.nta_name} to post a reply.",
            )
            return redirect(
                "communities:post_detail", nta_code=nta.nta_code, post_id=post.id
            )
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
        "can_comment": can_comment,
    }
    return render(request, "communities/post_detail.html", context)


@login_required
def vote_post(request, nta_code, post_id):
    if request.method != "POST":
        raise PermissionDenied("POST request required.")

    nta = get_object_or_404(NTARiskScore, nta_code=nta_code)
    post = get_object_or_404(Post, id=post_id, nta=nta, is_active=True)

    if not is_verified_for_nta(request.user, nta_code):
        messages.error(
            request, f"You must be a verified resident of {nta.nta_name} to vote."
        )
        return redirect("communities:post_detail", nta_code=nta_code, post_id=post_id)

    try:
        value = int(request.POST.get("value", "0"))
    except ValueError:
        raise PermissionDenied("Invalid vote value.")

    if value not in (PostVote.VALUE_UPVOTE, PostVote.VALUE_DOWNVOTE):
        raise PermissionDenied("Invalid vote value.")

    vote, created = PostVote.objects.get_or_create(
        post=post,
        user=request.user,
        defaults={"value": value},
    )
    if not created:
        if vote.value == value:
            vote.delete()
            messages.success(request, "Vote removed.")
        else:
            vote.value = value
            vote.save(update_fields=["value", "updated_at"])
            messages.success(request, "Vote updated.")
    else:
        messages.success(request, "Vote recorded.")

    return redirect("communities:post_detail", nta_code=nta_code, post_id=post_id)


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
        form = PostForm(request.POST, request.FILES)
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

    if post and post.author == request.user:
        messages.error(request, "You cannot report your own post.")
        return redirect(
            "communities:post_detail", nta_code=nta.nta_code, post_id=post.id
        )

    if comment and comment.author == request.user:
        messages.error(request, "You cannot report your own comment.")
        return redirect(
            "communities:post_detail",
            nta_code=nta.nta_code,
            post_id=comment.post.id,
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
        report.post = None
        messages.success(request, "Reported post has been deleted.")
    elif report.comment:
        report.comment.delete()
        report.comment = None
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
    if not getattr(request.user, "is_verified_tenant", False) and not getattr(
        request.user, "is_admin_user", False
    ):
        messages.error(request, "Only verified tenants can access direct messages.")
        return redirect("communities:index")

    messages_qs = DirectMessage.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user)
    ).order_by("-created_at")

    users = set()
    latest_messages = []

    for msg in messages_qs:
        other_user = msg.receiver if msg.sender == request.user else msg.sender
        if other_user not in users:
            users.add(other_user)
            latest_messages.append(msg)

    context = {
        "conversations": latest_messages,
    }
    return render(request, "communities/inbox.html", context)


@login_required
def chat(request, user_id):
    if not getattr(request.user, "is_verified_tenant", False) and not getattr(
        request.user, "is_admin_user", False
    ):
        messages.error(request, "Only verified tenants can send or receive messages.")
        return redirect("communities:index")

    other_user = get_object_or_404(User, id=user_id)
    if not getattr(other_user, "is_verified_tenant", False) and not getattr(
        other_user, "is_admin_user", False
    ):
        messages.error(request, "You can only message verified tenants.")
        return redirect("communities:inbox")

    DirectMessage.objects.filter(
        sender=other_user, receiver=request.user, is_read=False
    ).update(is_read=True)

    messages_qs = DirectMessage.objects.filter(
        Q(sender=request.user, receiver=other_user)
        | Q(sender=other_user, receiver=request.user)
    ).order_by("created_at")

    if request.method == "POST":
        form = DirectMessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.sender = request.user
            msg.receiver = other_user
            msg.save()
            return redirect("communities:chat", user_id=other_user.id)
    else:
        form = DirectMessageForm()

    context = {
        "other_user": other_user,
        "chat_messages": messages_qs,
        "form": form,
    }
    return render(request, "communities/chat.html", context)


@login_required
def edit_post(request, nta_code, post_id):
    nta = get_object_or_404(NTARiskScore, nta_code=nta_code)
    post = get_object_or_404(Post, id=post_id, nta=nta, is_active=True)

    # Only author or admin can edit
    is_admin = getattr(request.user, "is_admin_user", False)
    if post.author != request.user and not is_admin:
        messages.error(request, "You can only edit your own posts.")
        return redirect("communities:post_detail", nta_code=nta_code, post_id=post_id)

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, "Post updated successfully.")
            return redirect(
                "communities:post_detail", nta_code=nta_code, post_id=post.id
            )
    else:
        form = PostForm(instance=post)

    context = {"nta": nta, "form": form, "post": post, "editing": True}
    return render(request, "communities/create_post.html", context)


@login_required
def delete_post(request, nta_code, post_id):
    nta = get_object_or_404(NTARiskScore, nta_code=nta_code)
    post = get_object_or_404(Post, id=post_id, nta=nta)

    is_admin = getattr(request.user, "is_admin_user", False)
    if post.author != request.user and not is_admin:
        messages.error(request, "You can only delete your own posts.")
        return redirect("communities:post_detail", nta_code=nta_code, post_id=post_id)

    if request.method == "POST":
        post.is_active = False
        post.save(update_fields=["is_active"])
        messages.success(request, "Post deleted.")
        return redirect("communities:nta_forum", nta_code=nta_code)

    context = {"nta": nta, "post": post}
    return render(request, "communities/delete_post.html", context)


@login_required
def my_posts_view(request):
    posts = (
        Post.objects.filter(author=request.user, is_active=True)
        .select_related("nta")
        .order_by("-created_at")
    )
    context = {"posts": posts}
    return render(request, "communities/my_posts.html", context)
