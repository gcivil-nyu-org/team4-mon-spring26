"""Map ↔ Community integration API views."""

from django.db.models import Count, Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import NTARiskScore, ScoreRecencyConfig


@require_GET
def community_preview_view(request, nta_code):
    """Lightweight community data for map popup: member count, post count, recent posts."""
    try:
        nta = NTARiskScore.objects.get(nta_code=nta_code)
    except NTARiskScore.DoesNotExist:
        return JsonResponse({"error": "NTA not found."}, status=404)

    community = getattr(nta, "community", None)
    if not community:
        return JsonResponse(
            {
                "nta_code": nta_code,
                "nta_name": nta.nta_name,
                "has_community": False,
                "member_count": 0,
                "post_count": 0,
                "recent_posts": [],
            }
        )

    recent_posts = (
        nta.posts.filter(is_active=True)
        .select_related("author")
        .order_by("-created_at")[:5]
    )

    is_member = False
    if request.user.is_authenticated:
        is_member = community.members.filter(user=request.user, is_active=True).exists()

    return JsonResponse(
        {
            "nta_code": nta_code,
            "nta_name": nta.nta_name,
            "has_community": True,
            "member_count": community.member_count,
            "post_count": community.post_count,
            "is_member": is_member,
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
def community_activity_view(request):
    """All NTAs with post_count + member_count for activity heatmap layer."""
    from communities.models import Community

    communities = Community.objects.select_related("nta").annotate(
        active_members=Count("members", filter=Q(members__is_active=True)),
        active_posts=Count("nta__posts", filter=Q(nta__posts__is_active=True)),
    )

    data = []
    for c in communities:
        data.append(
            {
                "nta_code": c.nta.nta_code,
                "nta_name": c.nta.nta_name,
                "member_count": c.active_members,
                "post_count": c.active_posts,
                "activity_score": c.active_members + c.active_posts,
            }
        )

    return JsonResponse({"communities": data})


@require_GET
def my_marker_view(request):
    """Return the authenticated user's verified coords + NTA info for map pin."""
    if not request.user.is_authenticated:
        return JsonResponse({"has_marker": False})

    user = request.user
    nta_code = user.verified_nta_code
    lat = user.verified_lat
    lng = user.verified_lng

    if not nta_code:
        return JsonResponse({"has_marker": False})

    try:
        nta = NTARiskScore.objects.get(nta_code=nta_code)
    except NTARiskScore.DoesNotExist:
        return JsonResponse({"has_marker": False})

    community = getattr(nta, "community", None)

    return JsonResponse(
        {
            "has_marker": True,
            "nta_code": nta_code,
            "nta_name": nta.nta_name,
            "risk_score": nta.risk_score,
            "lat": lat,
            "lng": lng,
            "member_count": community.member_count if community else 0,
            "post_count": community.post_count if community else 0,
        }
    )


@require_GET
def recency_label_view(request):
    """Return the current recency window label for the map UI."""
    config = ScoreRecencyConfig.load()
    return JsonResponse(
        {
            "recency_window": config.recency_window,
            "label": config.get_recency_window_display(),
        }
    )
