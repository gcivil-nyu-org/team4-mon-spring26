"""JSON API views for communities — consumed by map frontend and community pages."""

from django.db.models import Count, Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import Community, CommunityMembership, Post


@require_GET
def community_list_api(request):
    """List all communities with counts. Supports search and sort."""
    search = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "name")

    qs = Community.objects.select_related("nta").annotate(
        active_members=Count("members", filter=Q(members__is_active=True)),
        active_posts=Count("nta__posts", filter=Q(nta__posts__is_active=True)),
    )

    if search:
        qs = qs.filter(name__icontains=search)

    sort_map = {
        "name": "name",
        "most_active": "-active_posts",
        "most_members": "-active_members",
        "highest_risk": "nta__risk_score",
        "alphabetical": "name",
    }
    qs = qs.order_by(sort_map.get(sort, "name"))

    data = []
    for c in qs:
        data.append(
            {
                "nta_code": c.nta.nta_code,
                "name": c.name,
                "borough": c.nta.borough,
                "risk_score": c.nta.risk_score,
                "member_count": c.active_members,
                "post_count": c.active_posts,
            }
        )

    return JsonResponse({"communities": data})


@require_GET
def my_community_api(request):
    """Return the authenticated user's assigned community."""
    if not request.user.is_authenticated:
        return JsonResponse({"has_community": False, "reason": "not_authenticated"})

    user = request.user
    if not user.is_verified_tenant:
        return JsonResponse({"has_community": False, "reason": "not_verified"})

    nta_code = user.verified_nta_code
    if not nta_code:
        return JsonResponse({"has_community": False, "reason": "no_nta"})

    try:
        community = Community.objects.select_related("nta").get(nta_id=nta_code)
    except Community.DoesNotExist:
        return JsonResponse({"has_community": False, "reason": "no_community"})

    recent_posts = (
        community.nta.posts.filter(is_active=True)
        .select_related("author")
        .order_by("-created_at")[:3]
    )

    return JsonResponse(
        {
            "has_community": True,
            "nta_code": nta_code,
            "name": community.name,
            "borough": community.nta.borough,
            "risk_score": community.nta.risk_score,
            "member_count": community.member_count,
            "post_count": community.post_count,
            "recent_posts": [
                {
                    "id": p.id,
                    "title": p.title,
                    "author": p.author.username,
                    "category": p.category,
                    "category_display": p.get_category_display(),
                    "created_at": p.created_at.isoformat(),
                    "reply_count": p.reply_count,
                }
                for p in recent_posts
            ],
        }
    )


@require_GET
def community_detail_api(request, nta_code):
    """Community detail + stats."""
    try:
        community = Community.objects.select_related("nta").get(nta_id=nta_code)
    except Community.DoesNotExist:
        return JsonResponse({"error": "Community not found."}, status=404)

    is_member = False
    if request.user.is_authenticated:
        is_member = CommunityMembership.objects.filter(
            user=request.user, community=community, is_active=True
        ).exists()

    return JsonResponse(
        {
            "nta_code": nta_code,
            "name": community.name,
            "description": community.description,
            "borough": community.nta.borough,
            "risk_score": community.nta.risk_score,
            "member_count": community.member_count,
            "post_count": community.post_count,
            "is_member": is_member,
        }
    )


@require_GET
def community_posts_api(request, nta_code):
    """Paginated posts for a community."""
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    per_page = 20

    posts = (
        Post.objects.filter(nta_id=nta_code, is_active=True)
        .select_related("author")
        .order_by("-is_pinned", "-created_at")
    )
    total = posts.count()
    page_posts = posts[(page - 1) * per_page : page * per_page]

    return JsonResponse(
        {
            "nta_code": nta_code,
            "page": page,
            "total": total,
            "posts": [
                {
                    "id": p.id,
                    "title": p.title,
                    "content_preview": p.content[:200],
                    "author": p.author.username,
                    "category": p.category,
                    "category_display": p.get_category_display(),
                    "is_pinned": p.is_pinned,
                    "linked_address": p.linked_address,
                    "has_image": bool(p.image),
                    "reply_count": p.reply_count,
                    "created_at": p.created_at.isoformat(),
                }
                for p in page_posts
            ],
        }
    )


@require_GET
def my_posts_api(request):
    """All posts by the authenticated user across communities."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    posts = (
        Post.objects.filter(author=request.user, is_active=True)
        .select_related("nta")
        .order_by("-created_at")
    )

    return JsonResponse(
        {
            "posts": [
                {
                    "id": p.id,
                    "title": p.title,
                    "nta_code": p.nta.nta_code,
                    "nta_name": p.nta.nta_name,
                    "category": p.category,
                    "category_display": p.get_category_display(),
                    "reply_count": p.reply_count,
                    "created_at": p.created_at.isoformat(),
                }
                for p in posts
            ]
        }
    )
