"""Admin-only API views for the data ingestion dashboard."""

import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from .ingestion import is_job_running, run_ingestion_job
from .models import (
    Complaint311,
    HPDViolation,
    IngestionJob,
    IngestionSchedule,
    NTARiskScore,
    ScoreRecencyConfig,
)


def _admin_required(view_func):
    """Decorator: require authenticated admin/superuser."""
    from functools import wraps

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)
        if not (
            request.user.is_superuser
            or request.user.is_staff
            or getattr(request.user, "is_admin_user", False)
        ):
            return JsonResponse({"error": "Admin access required."}, status=403)
        return view_func(request, *args, **kwargs)

    return _wrapped


@_admin_required
@require_GET
def ingestion_status_view(request):
    """Return current/latest ingestion job status."""
    job = IngestionJob.objects.first()
    if not job:
        return JsonResponse({"status": "idle", "job": None})

    return JsonResponse(
        {
            "status": "running" if job.is_running else job.status,
            "job": _job_to_dict(job),
        }
    )


@_admin_required
@require_http_methods(["POST"])
def ingestion_start_view(request):
    """Start a manual ingestion job."""
    if is_job_running():
        return JsonResponse(
            {"error": "An ingestion job is already running."}, status=409
        )

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    limit = body.get("limit", 10000)
    sources = body.get("sources", "both")

    # Validate
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10000
    limit = max(1000, min(500000, limit))

    if sources not in ("both", "hpd_only", "311_only"):
        sources = "both"

    job = IngestionJob.objects.create(
        trigger_type=IngestionJob.TRIGGER_MANUAL,
        requested_limit=limit,
        sources=sources,
        records_target=limit,
    )

    run_ingestion_job(job.pk)

    return JsonResponse({"message": "Ingestion started.", "job": _job_to_dict(job)})


@_admin_required
@require_GET
def ingestion_history_view(request):
    """Return last 50 ingestion runs."""
    jobs = IngestionJob.objects.all()[:50]
    return JsonResponse(
        {"history": [_job_to_dict(j) for j in jobs]},
    )


@_admin_required
@require_GET
def ingestion_stats_view(request):
    """Return database statistics."""
    hpd_count = HPDViolation.objects.count()
    complaints_count = Complaint311.objects.count()
    nta_count = NTARiskScore.objects.count()

    hpd_latest = HPDViolation.objects.order_by("-ingested_at").first()
    complaints_latest = Complaint311.objects.order_by("-ingested_at").first()

    hpd_oldest = (
        HPDViolation.objects.order_by("inspection_date")
        .exclude(inspection_date__isnull=True)
        .first()
    )
    hpd_newest = HPDViolation.objects.order_by("-inspection_date").first()

    complaints_oldest = (
        Complaint311.objects.order_by("created_date")
        .exclude(created_date__isnull=True)
        .first()
    )
    complaints_newest = Complaint311.objects.order_by("-created_date").first()

    last_job = IngestionJob.objects.filter(status=IngestionJob.STATUS_COMPLETED).first()

    recency = ScoreRecencyConfig.load()

    return JsonResponse(
        {
            "hpd_violations": hpd_count,
            "complaints_311": complaints_count,
            "scored_neighborhoods": nta_count,
            "last_ingestion": (last_job.completed_at.isoformat() if last_job else None),
            "hpd_date_range": {
                "oldest": (
                    hpd_oldest.inspection_date.isoformat()
                    if hpd_oldest and hpd_oldest.inspection_date
                    else None
                ),
                "newest": (
                    hpd_newest.inspection_date.isoformat()
                    if hpd_newest and hpd_newest.inspection_date
                    else None
                ),
            },
            "complaints_date_range": {
                "oldest": (
                    complaints_oldest.created_date.isoformat()
                    if complaints_oldest and complaints_oldest.created_date
                    else None
                ),
                "newest": (
                    complaints_newest.created_date.isoformat()
                    if complaints_newest and complaints_newest.created_date
                    else None
                ),
            },
            "last_ingested_at": {
                "hpd": (hpd_latest.ingested_at.isoformat() if hpd_latest else None),
                "complaints": (
                    complaints_latest.ingested_at.isoformat()
                    if complaints_latest
                    else None
                ),
            },
            "recency_window": recency.recency_window,
            "recency_label": recency.get_recency_window_display(),
        }
    )


@_admin_required
@require_http_methods(["GET", "POST"])
def ingestion_schedule_view(request):
    """Get or update the ingestion schedule config."""
    schedule = IngestionSchedule.load()

    if request.method == "GET":
        return JsonResponse(_schedule_to_dict(schedule))

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    if "is_enabled" in body:
        schedule.is_enabled = bool(body["is_enabled"])
    if "interval_value" in body:
        schedule.interval_value = max(1, int(body["interval_value"]))
    if "interval_unit" in body and body["interval_unit"] in ("hours", "days"):
        schedule.interval_unit = body["interval_unit"]
    if "run_time" in body:
        schedule.run_time = body["run_time"]
    if "record_limit" in body:
        schedule.record_limit = max(1000, min(500000, int(body["record_limit"])))
    if "sources" in body and body["sources"] in ("both", "hpd_only", "311_only"):
        schedule.sources = body["sources"]

    # Compute next_run_at
    if schedule.is_enabled:
        from datetime import timedelta

        now = timezone.now()
        if schedule.interval_unit == "hours":
            delta = timedelta(hours=schedule.interval_value)
        else:
            delta = timedelta(days=schedule.interval_value)
        schedule.next_run_at = now + delta
    else:
        schedule.next_run_at = None

    schedule.save()
    return JsonResponse(_schedule_to_dict(schedule))


@_admin_required
@require_http_methods(["GET", "POST"])
def ingestion_recency_view(request):
    """Get or set the score recency window."""
    config = ScoreRecencyConfig.load()

    if request.method == "GET":
        return JsonResponse(
            {
                "recency_window": config.recency_window,
                "label": config.get_recency_window_display(),
                "last_recomputed_at": (
                    config.last_recomputed_at.isoformat()
                    if config.last_recomputed_at
                    else None
                ),
            }
        )

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON."}, status=400)

    new_window = body.get("recency_window")
    valid = [c[0] for c in ScoreRecencyConfig.RECENCY_CHOICES]
    if new_window not in valid:
        return JsonResponse(
            {"error": f"Invalid recency_window. Choose from: {valid}"}, status=400
        )

    old_window = config.recency_window
    config.recency_window = new_window
    config.save()

    # If changed, trigger a background recompute
    if new_window != old_window:
        if is_job_running():
            return JsonResponse(
                {
                    "message": "Recency updated. Recompute deferred — a job is running.",
                    "recency_window": config.recency_window,
                    "label": config.get_recency_window_display(),
                }
            )

        job = IngestionJob.objects.create(
            trigger_type=IngestionJob.TRIGGER_MANUAL,
            requested_limit=0,
            sources=IngestionJob.SOURCE_BOTH,
            current_step="Recomputing risk scores with new recency window",
        )
        run_ingestion_job(job.pk)

    return JsonResponse(
        {
            "message": "Recency window updated.",
            "recency_window": config.recency_window,
            "label": config.get_recency_window_display(),
        }
    )


def _job_to_dict(job):
    return {
        "id": job.pk,
        "status": job.status,
        "trigger_type": job.trigger_type,
        "sources": job.sources,
        "requested_limit": job.requested_limit,
        "current_step": job.current_step,
        "records_fetched": job.records_fetched,
        "records_target": job.records_target,
        "current_batch": job.current_batch,
        "total_batches": job.total_batches,
        "hpd_created": job.hpd_created,
        "hpd_updated": job.hpd_updated,
        "complaints_created": job.complaints_created,
        "complaints_updated": job.complaints_updated,
        "neighborhoods_scored": job.neighborhoods_scored,
        "elapsed_seconds": round(job.elapsed_seconds, 1),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
    }


def _schedule_to_dict(schedule):
    return {
        "is_enabled": schedule.is_enabled,
        "interval_value": schedule.interval_value,
        "interval_unit": schedule.interval_unit,
        "run_time": str(schedule.run_time),
        "record_limit": schedule.record_limit,
        "sources": schedule.sources,
        "last_run_at": (
            schedule.last_run_at.isoformat() if schedule.last_run_at else None
        ),
        "next_run_at": (
            schedule.next_run_at.isoformat() if schedule.next_run_at else None
        ),
    }
