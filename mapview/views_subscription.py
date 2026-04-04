"""Views for area subscriptions, notifications, and risk history (Epics #5, #8)."""

import json

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from .models import AreaSubscription, Notification, NTARiskScore, RiskScoreHistory


def _login_required_json(view_func):
    """Decorator: return 401 JSON for unauthenticated requests."""

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)
        return view_func(request, *args, **kwargs)

    return wrapper


# ------------------------------------------------------------------ #
#  Risk Score History (Epic #5)
# ------------------------------------------------------------------ #


@require_GET
def risk_history_view(request):
    """Return risk score history for a specific NTA."""
    nta_code = request.GET.get("nta_code", "").strip()
    if not nta_code:
        return JsonResponse({"error": "nta_code parameter is required."}, status=400)

    try:
        limit = min(int(request.GET.get("limit", 20)), 100)
    except (ValueError, TypeError):
        limit = 20

    records = RiskScoreHistory.objects.filter(nta_code=nta_code)[:limit]

    history = [
        {
            "risk_score": r.risk_score,
            "previous_score": r.previous_score,
            "score_delta": r.score_delta,
            "total_violations": r.total_violations,
            "total_complaints": r.total_complaints,
            "recorded_at": r.recorded_at.isoformat(),
        }
        for r in records
    ]

    return JsonResponse(
        {"nta_code": nta_code, "count": len(history), "history": history}
    )


@require_GET
def risk_changes_view(request):
    """Return NTAs with the most significant recent score changes."""
    try:
        limit = min(int(request.GET.get("limit", 20)), 50)
    except (ValueError, TypeError):
        limit = 20

    # Get the latest history record per NTA with non-zero delta
    from django.db.models import Max

    latest_ids = (
        RiskScoreHistory.objects.values("nta_code")
        .annotate(latest_id=Max("id"))
        .values_list("latest_id", flat=True)
    )

    records = (
        RiskScoreHistory.objects.filter(id__in=latest_ids)
        .exclude(score_delta=0.0)
        .order_by("-score_delta")[:limit]
    )

    changes = [
        {
            "nta_code": r.nta_code,
            "nta_name": r.nta_name,
            "risk_score": r.risk_score,
            "previous_score": r.previous_score,
            "score_delta": r.score_delta,
            "recorded_at": r.recorded_at.isoformat(),
        }
        for r in records
    ]

    return JsonResponse({"count": len(changes), "changes": changes})


# ------------------------------------------------------------------ #
#  Area Subscriptions (Epic #8)
# ------------------------------------------------------------------ #


@_login_required_json
@require_GET
def subscription_list_view(request):
    """List the current user's area subscriptions."""
    subs = AreaSubscription.objects.filter(user=request.user).order_by("-created_at")
    data = [
        {
            "id": s.id,
            "nta_code": s.nta_code,
            "nta_name": s.nta_name,
            "delivery_method": s.delivery_method,
            "threshold": s.threshold,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat(),
        }
        for s in subs
    ]
    return JsonResponse({"subscriptions": data})


@_login_required_json
@require_http_methods(["POST"])
def subscription_create_view(request):
    """Subscribe to risk alerts for an NTA area."""
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    nta_code = body.get("nta_code", "").strip()
    if not nta_code:
        return JsonResponse({"error": "nta_code is required."}, status=400)

    # Resolve NTA name
    nta_name = body.get("nta_name", "")
    if not nta_name:
        try:
            score = NTARiskScore.objects.get(nta_code=nta_code)
            nta_name = score.nta_name
        except NTARiskScore.DoesNotExist:
            nta_name = nta_code

    delivery = body.get("delivery_method", AreaSubscription.DELIVERY_IN_APP)
    valid_methods = [c[0] for c in AreaSubscription.DELIVERY_CHOICES]
    if delivery not in valid_methods:
        return JsonResponse(
            {"error": f"Invalid delivery_method. Choose from: {valid_methods}"},
            status=400,
        )

    threshold = float(body.get("threshold", 0.5))

    sub, created = AreaSubscription.objects.update_or_create(
        user=request.user,
        nta_code=nta_code,
        defaults={
            "nta_name": nta_name,
            "delivery_method": delivery,
            "threshold": threshold,
            "is_active": True,
        },
    )

    return JsonResponse(
        {
            "id": sub.id,
            "nta_code": sub.nta_code,
            "nta_name": sub.nta_name,
            "delivery_method": sub.delivery_method,
            "threshold": sub.threshold,
            "is_active": sub.is_active,
            "created": created,
        },
        status=201 if created else 200,
    )


@_login_required_json
@require_http_methods(["POST", "DELETE"])
def subscription_update_view(request, pk):
    """Update or delete a subscription."""
    try:
        sub = AreaSubscription.objects.get(pk=pk, user=request.user)
    except AreaSubscription.DoesNotExist:
        return JsonResponse({"error": "Subscription not found."}, status=404)

    if request.method == "DELETE":
        sub.delete()
        return JsonResponse({"message": "Subscription deleted."})

    # POST = update
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    if "delivery_method" in body:
        valid_methods = [c[0] for c in AreaSubscription.DELIVERY_CHOICES]
        if body["delivery_method"] in valid_methods:
            sub.delivery_method = body["delivery_method"]
    if "threshold" in body:
        sub.threshold = float(body["threshold"])
    if "is_active" in body:
        sub.is_active = bool(body["is_active"])

    sub.save()
    return JsonResponse(
        {
            "id": sub.id,
            "nta_code": sub.nta_code,
            "nta_name": sub.nta_name,
            "delivery_method": sub.delivery_method,
            "threshold": sub.threshold,
            "is_active": sub.is_active,
        }
    )


# ------------------------------------------------------------------ #
#  Notifications (Epic #8)
# ------------------------------------------------------------------ #


@_login_required_json
@require_GET
def notification_list_view(request):
    """List notifications for the current user."""
    unread_only = request.GET.get("unread", "").lower() == "true"
    qs = Notification.objects.filter(user=request.user)
    if unread_only:
        qs = qs.filter(is_read=False)

    try:
        limit = min(int(request.GET.get("limit", 20)), 100)
    except (ValueError, TypeError):
        limit = 20

    notifications = [
        {
            "id": n.id,
            "type": n.notification_type,
            "title": n.title,
            "message": n.message,
            "nta_code": n.nta_code,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        }
        for n in qs[:limit]
    ]

    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()

    return JsonResponse(
        {
            "notifications": notifications,
            "unread_count": unread_count,
        }
    )


@_login_required_json
@require_http_methods(["POST"])
def notification_read_view(request, pk):
    """Mark a notification as read."""
    try:
        notif = Notification.objects.get(pk=pk, user=request.user)
    except Notification.DoesNotExist:
        return JsonResponse({"error": "Notification not found."}, status=404)

    notif.is_read = True
    notif.save(update_fields=["is_read"])
    return JsonResponse({"message": "Marked as read."})


@_login_required_json
@require_http_methods(["POST"])
def notification_read_all_view(request):
    """Mark all notifications as read for the current user."""
    count = Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True
    )
    return JsonResponse({"message": f"Marked {count} notifications as read."})
