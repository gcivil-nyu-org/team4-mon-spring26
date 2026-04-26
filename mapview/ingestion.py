"""Background ingestion runner — executes IngestionJob in a thread.

Usage:
    from mapview.ingestion import run_ingestion_job
    run_ingestion_job(job_id)  # spawns a daemon thread
"""

import logging
import math
import threading
from datetime import datetime, timezone as dt_timezone

import requests
from django.conf import settings
from django.db.models import Count
from django.utils import timezone

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()

HPD_VIOLATIONS_URL = "https://data.cityofnewyork.us/resource/wvxf-dwi5.json"
COMPLAINTS_311_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
BATCH_SIZE = 5000

HOUSING_COMPLAINT_TYPES = [
    "HEAT/HOT WATER",
    "PLUMBING",
    "PAINT/PLASTER",
    "WATER LEAK",
    "GENERAL CONSTRUCTION",
    "ELECTRIC",
    "DOOR/WINDOW",
    "FLOORING/STAIRS",
    "ELEVATOR",
    "SAFETY",
    "APPLIANCE",
    "Noise - Residential",
    "UNSANITARY CONDITION",
    "PEST CONTROL",
]


def _extract_violation_class(record):
    """Return a normalized HPD violation class from the API payload."""
    raw_value = record.get("violationclass") or record.get("class") or ""
    return str(raw_value).strip().upper()


def is_job_running():
    """Check if any ingestion job is currently running."""
    from mapview.models import IngestionJob

    return IngestionJob.objects.filter(status=IngestionJob.STATUS_RUNNING).exists()


def run_ingestion_job(job_id):
    """Spawn a daemon thread to execute the ingestion job."""
    t = threading.Thread(target=_execute_job, args=(job_id,), daemon=True)
    t.start()
    return t


def _execute_job(job_id):
    """Main execution — runs in background thread."""
    import django

    django.setup()
    from mapview.models import IngestionJob, ScoreRecencyConfig

    try:
        job = IngestionJob.objects.get(pk=job_id)
    except IngestionJob.DoesNotExist:
        logger.error("IngestionJob %s not found", job_id)
        return

    if not _LOCK.acquire(blocking=False):
        job.status = IngestionJob.STATUS_FAILED
        job.error_message = "Another ingestion job is already running."
        job.save()
        return

    try:
        job.status = IngestionJob.STATUS_RUNNING
        job.started_at = timezone.now()
        job.save()

        limit = job.requested_limit
        sources = job.sources
        total_steps = 3 if sources == IngestionJob.SOURCE_BOTH else 2

        step = 0

        # Step 1: HPD violations
        if sources in (IngestionJob.SOURCE_BOTH, IngestionJob.SOURCE_HPD):
            step += 1
            job.current_step = f"Step {step}/{total_steps}: Ingesting HPD violations"
            job.save()
            hpd_c, hpd_u = _ingest_hpd(job, limit)
            job.hpd_created = hpd_c
            job.hpd_updated = hpd_u
            job.save()

        # Step 2: 311 complaints
        if sources in (IngestionJob.SOURCE_BOTH, IngestionJob.SOURCE_311):
            step += 1
            job.current_step = f"Step {step}/{total_steps}: Ingesting 311 complaints"
            job.save()
            c_c, c_u = _ingest_311(job, limit)
            job.complaints_created = c_c
            job.complaints_updated = c_u
            job.save()

        # Step 3: Compute risk scores
        step += 1
        job.current_step = f"Step {step}/{total_steps}: Computing risk scores"
        job.save()

        recency_config = ScoreRecencyConfig.load()
        scored = _compute_risk_scores(recency_config, job)
        job.neighborhoods_scored = scored
        recency_config.last_recomputed_at = timezone.now()
        recency_config.save()

        # Send alerts for significant score changes
        _send_risk_change_alerts(job)

        job.status = IngestionJob.STATUS_COMPLETED
        job.completed_at = timezone.now()
        job.current_step = "Completed"
        job.save()

    except Exception as exc:
        logger.exception("Ingestion job %s failed", job_id)
        job.status = IngestionJob.STATUS_FAILED
        job.error_message = str(exc)[:2000]
        job.completed_at = timezone.now()
        job.current_step = "Failed"
        job.save()
    finally:
        _LOCK.release()


def _parse_date(value):
    """Parse date from NYC Open Data API format (e.g., '2024-03-15T00:00:00.000')."""
    if not value:
        return None
    try:
        # Extract date portion before 'T'
        date_str = value.split("T")[0] if "T" in value else value
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, AttributeError, TypeError):
        return None


def _parse_datetime(value):
    """Parse datetime from NYC Open Data API format (e.g., '2024-03-15T14:30:00.000')."""
    if not value:
        return None
    try:
        # Remove milliseconds if present
        clean_value = value.split(".")[0] if "." in value else value
        # Parse ISO format datetime
        dt = datetime.strptime(clean_value, "%Y-%m-%dT%H:%M:%S")
        # Make timezone-aware (NYC Open Data uses UTC)
        return dt.replace(tzinfo=dt_timezone.utc)
    except (ValueError, AttributeError, TypeError):
        return None


def _ingest_hpd(job, limit):
    """Ingest HPD violations, updating job progress."""
    from mapview.models import HPDViolation

    app_token = getattr(settings, "NYC_OPEN_DATA_APP_TOKEN", "")
    headers = {"X-App-Token": app_token} if app_token else {}

    total_batches = math.ceil(limit / BATCH_SIZE)
    job.records_target = limit
    job.total_batches = total_batches
    job.save()

    offset = 0
    created = 0
    updated = 0
    batch_num = 0

    while offset < limit:
        batch_limit = min(BATCH_SIZE, limit - offset)
        batch_num += 1
        job.current_batch = batch_num
        job.save()

        params = {
            "$limit": batch_limit,
            "$offset": offset,
            "$order": "inspectiondate DESC",
            "$where": "latitude IS NOT NULL AND longitude IS NOT NULL",
        }

        try:
            resp = requests.get(
                HPD_VIOLATIONS_URL, params=params, headers=headers, timeout=30
            )
            resp.raise_for_status()
            records = resp.json()
        except requests.RequestException as exc:
            logger.warning("HPD API failed at offset %d: %s", offset, exc)
            break

        if not records:
            break

        for rec in records:
            vid = rec.get("violationid")
            if not vid:
                continue
            _, was_created = HPDViolation.objects.update_or_create(
                violation_id=int(vid),
                defaults={
                    "bbl": rec.get("bbl", "") or "",
                    "borough": rec.get("boroname", "") or "",
                    "house_number": rec.get("housenumber", "") or "",
                    "street_name": rec.get("streetname", "") or "",
                    "apartment": rec.get("apartment", "") or "",
                    "zip_code": rec.get("zip", "") or "",
                    "violation_class": _extract_violation_class(rec),
                    "inspection_date": _parse_date(rec.get("inspectiondate")),
                    "approved_date": _parse_date(rec.get("approveddate")),
                    "nov_description": rec.get("novdescription", "") or "",
                    "nov_issued_date": _parse_date(rec.get("novissueddate")),
                    "current_status": rec.get("currentstatus", "") or "",
                    "current_status_id": (
                        int(rec["currentstatusid"])
                        if rec.get("currentstatusid")
                        else None
                    ),
                    "violation_status": rec.get("violationstatus", "") or "",
                    "violation_status_date": _parse_date(
                        rec.get("violationstatusdate")
                    ),
                    "latitude": (
                        float(rec["latitude"]) if rec.get("latitude") else None
                    ),
                    "longitude": (
                        float(rec["longitude"]) if rec.get("longitude") else None
                    ),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        job.records_fetched = offset + len(records)
        job.hpd_created = created
        job.hpd_updated = updated
        job.save()

        offset += len(records)
        if len(records) < batch_limit:
            break

    return created, updated


def _ingest_311(job, limit):
    """Ingest 311 complaints, updating job progress."""
    from mapview.models import Complaint311

    app_token = getattr(settings, "NYC_OPEN_DATA_APP_TOKEN", "")
    headers = {"X-App-Token": app_token} if app_token else {}

    type_clauses = " OR ".join(
        f"complaint_type='{ct}'" for ct in HOUSING_COMPLAINT_TYPES
    )
    where = f"({type_clauses}) AND latitude IS NOT NULL AND longitude IS NOT NULL"

    total_batches = math.ceil(limit / BATCH_SIZE)
    job.records_target = limit
    job.total_batches = total_batches
    job.save()

    offset = 0
    created = 0
    updated = 0
    batch_num = 0

    while offset < limit:
        batch_limit = min(BATCH_SIZE, limit - offset)
        batch_num += 1
        job.current_batch = batch_num
        job.save()

        params = {
            "$limit": batch_limit,
            "$offset": offset,
            "$order": "created_date DESC",
            "$where": where,
        }

        try:
            resp = requests.get(
                COMPLAINTS_311_URL, params=params, headers=headers, timeout=30
            )
            resp.raise_for_status()
            records = resp.json()
        except requests.RequestException as exc:
            logger.warning("311 API failed at offset %d: %s", offset, exc)
            break

        if not records:
            break

        for rec in records:
            key = rec.get("unique_key")
            if not key:
                continue
            _, was_created = Complaint311.objects.update_or_create(
                unique_key=key,
                defaults={
                    "created_date": _parse_datetime(rec.get("created_date")),
                    "closed_date": _parse_datetime(rec.get("closed_date")),
                    "agency": rec.get("agency", "") or "",
                    "complaint_type": rec.get("complaint_type", "") or "",
                    "descriptor": rec.get("descriptor", "") or "",
                    "location_type": rec.get("location_type", "") or "",
                    "incident_address": rec.get("incident_address", "") or "",
                    "incident_zip": rec.get("incident_zip", "") or "",
                    "borough": rec.get("borough", "") or "",
                    "status": rec.get("status", "") or "",
                    "resolution_description": rec.get("resolution_description", "")
                    or "",
                    "bbl": rec.get("bbl", "") or "",
                    "latitude": (
                        float(rec["latitude"]) if rec.get("latitude") else None
                    ),
                    "longitude": (
                        float(rec["longitude"]) if rec.get("longitude") else None
                    ),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        job.records_fetched = offset + len(records)
        job.complaints_created = created
        job.complaints_updated = updated
        job.save()

        offset += len(records)
        if len(records) < batch_limit:
            break

    return created, updated


def _compute_risk_scores(recency_config=None, job=None):
    """Compute risk scores with optional recency filter. Returns count scored."""
    import json
    from pathlib import Path

    from mapview.models import (
        Complaint311,
        HPDViolation,
        NTARiskScore,
        RiskScoreHistory,
    )

    nta_geojson_path = (
        Path(settings.BASE_DIR) / "data" / "processed" / "nyc_nta_phase1.geojson"
    )

    try:
        with nta_geojson_path.open("r", encoding="utf-8") as fh:
            nta_data = json.load(fh)
    except FileNotFoundError:
        logger.error("NTA GeoJSON not found")
        return 0

    nta_lookup = {}
    for feature in nta_data.get("features", []):
        props = feature.get("properties", {})
        code = props.get("nta_code")
        if code:
            nta_lookup[code] = {
                "nta_name": props.get("nta_name", ""),
                "borough": props.get("borough", ""),
            }

    # Snapshot existing scores before recomputation
    old_scores = {
        s.nta_code: s.risk_score
        for s in NTARiskScore.objects.filter(nta_code__in=nta_lookup.keys())
    }

    # Spatial assignment of untagged records
    _assign_nta_codes_spatial(nta_data)

    # Determine recency cutoff
    cutoff = None
    if recency_config:
        cutoff = recency_config.get_cutoff_date()

    scored = 0
    for nta_code, info in nta_lookup.items():
        violations_qs = HPDViolation.objects.filter(nta_code=nta_code)
        complaints_qs = Complaint311.objects.filter(nta_code=nta_code)

        if cutoff:
            violations_qs = violations_qs.filter(inspection_date__gte=cutoff.date())
            complaints_qs = complaints_qs.filter(created_date__gte=cutoff)

        total_violations = violations_qs.count()
        total_complaints = complaints_qs.count()
        class_a = violations_qs.filter(violation_class="A").count()
        class_b = violations_qs.filter(violation_class="B").count()
        class_c = violations_qs.filter(violation_class="C").count()

        top_types = (
            complaints_qs.values("complaint_type")
            .annotate(n=Count("id"))
            .order_by("-n")[:5]
        )
        top_complaint_types = [t["complaint_type"] for t in top_types]

        weighted = (class_c * 3) + (class_b * 2) + class_a + total_complaints
        if weighted == 0:
            risk_score = 10.0
        else:
            risk_score = round(
                max(0.0, min(10.0, 10.0 - math.log1p(weighted) * 1.2)), 1
            )

        if risk_score <= 3.0:
            summary = (
                f"High-risk area — {total_violations} HPD violations and "
                f"{total_complaints} complaints on record. Immediate concerns present."
            )
        elif risk_score <= 6.0:
            summary = (
                f"Moderate-risk area — {total_violations} violations and "
                f"{total_complaints} complaints. Some issues but generally manageable."
            )
        else:
            summary = (
                f"Lower-risk area — {total_violations} violations and "
                f"{total_complaints} complaints. Relatively stable conditions."
            )

        NTARiskScore.objects.update_or_create(
            nta_code=nta_code,
            defaults={
                "nta_name": info["nta_name"],
                "borough": info["borough"],
                "total_violations": total_violations,
                "total_complaints": total_complaints,
                "class_a_violations": class_a,
                "class_b_violations": class_b,
                "class_c_violations": class_c,
                "risk_score": risk_score,
                "top_complaint_types": top_complaint_types,
                "summary": summary,
            },
        )

        # Record score history
        previous = old_scores.get(nta_code)
        delta = round(risk_score - previous, 1) if previous is not None else 0.0
        RiskScoreHistory.objects.create(
            nta_code=nta_code,
            nta_name=info["nta_name"],
            risk_score=risk_score,
            previous_score=previous,
            score_delta=delta,
            total_violations=total_violations,
            total_complaints=total_complaints,
            ingestion_job=job,
        )

        scored += 1

    return scored


def _send_risk_change_alerts(job):
    """Send notifications to users subscribed to areas with significant changes."""
    from django.core.mail import send_mail

    from mapview.models import AreaSubscription, Notification, RiskScoreHistory

    # Get all history records from this job that have significant changes
    changes = RiskScoreHistory.objects.filter(ingestion_job=job).exclude(
        score_delta=0.0
    )

    for change in changes:
        # Find active subscriptions for this NTA
        subscriptions = AreaSubscription.objects.filter(
            nta_code=change.nta_code,
            is_active=True,
        ).select_related("user")

        for sub in subscriptions:
            if abs(change.score_delta) < sub.threshold:
                continue

            direction = "improved" if change.score_delta > 0 else "worsened"
            title = f"Risk score {direction} for {change.nta_name}"
            message = (
                f"The risk score for {change.nta_name} ({change.nta_code}) "
                f"has changed from {change.previous_score}/10 to "
                f"{change.risk_score}/10 ({change.score_delta:+.1f}). "
                f"Current stats: {change.total_violations} violations, "
                f"{change.total_complaints} complaints."
            )

            # In-app notification
            if sub.delivery_method in (
                AreaSubscription.DELIVERY_IN_APP,
                AreaSubscription.DELIVERY_BOTH,
            ):
                Notification.objects.create(
                    user=sub.user,
                    notification_type=Notification.TYPE_RISK_CHANGE,
                    title=title,
                    message=message,
                    nta_code=change.nta_code,
                )

            # Email notification
            if sub.delivery_method in (
                AreaSubscription.DELIVERY_EMAIL,
                AreaSubscription.DELIVERY_BOTH,
            ):
                if sub.user.email:
                    try:
                        send_mail(
                            subject=f"TenantGuard: {title}",
                            message=message,
                            from_email=None,
                            recipient_list=[sub.user.email],
                            fail_silently=True,
                        )
                    except Exception:
                        logger.warning("Failed to send email to %s", sub.user.email)


def _assign_nta_codes_spatial(nta_data):
    """Point-in-polygon assignment using shapely."""
    try:
        from shapely.geometry import Point, shape
        from shapely.strtree import STRtree
    except ImportError:
        return

    from mapview.models import Complaint311, HPDViolation

    nta_geoms = []
    nta_codes = []
    for feature in nta_data.get("features", []):
        code = feature.get("properties", {}).get("nta_code")
        if code:
            nta_geoms.append(shape(feature["geometry"]))
            nta_codes.append(code)

    tree = STRtree(nta_geoms)

    for v in HPDViolation.objects.filter(
        nta_code="", latitude__isnull=False, longitude__isnull=False
    ).iterator(chunk_size=2000):
        pt = Point(v.longitude, v.latitude)
        for idx in tree.query(pt):
            if nta_geoms[int(idx)].contains(pt):
                v.nta_code = nta_codes[int(idx)]
                v.save(update_fields=["nta_code"])
                break

    for c in Complaint311.objects.filter(
        nta_code="", latitude__isnull=False, longitude__isnull=False
    ).iterator(chunk_size=2000):
        pt = Point(c.longitude, c.latitude)
        for idx in tree.query(pt):
            if nta_geoms[int(idx)].contains(pt):
                c.nta_code = nta_codes[int(idx)]
                c.save(update_fields=["nta_code"])
                break
