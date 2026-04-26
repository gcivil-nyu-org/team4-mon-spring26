import json
from pathlib import Path
from urllib.parse import quote

import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from django.contrib.auth.decorators import user_passes_test

from .models import (
    Complaint311,
    HPDViolation,
    NTARiskScore,
    ScoreRecencyConfig,
    ScoreThreshold,
)


def _is_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.is_staff or getattr(user, "is_admin_user", False)
    )


PROCESSED_GEOJSON_PATH = (
    Path(settings.BASE_DIR) / "data" / "processed" / "nyc_nta_phase1.geojson"
)
BOUNDARY_LEVEL_PATHS = {
    "nta": Path(settings.BASE_DIR) / "data" / "processed" / "nyc_nta_phase1.geojson",
    "mid": Path(settings.BASE_DIR) / "data" / "processed" / "nyc_nta_zoom_mid.geojson",
    "block": Path(settings.BASE_DIR)
    / "data"
    / "processed"
    / "nyc_nta_zoom_block.geojson",
}
MAPBOX_GEOCODE_BASE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"


def dashboard_view(request):
    thresholds = list(
        ScoreThreshold.objects.order_by("max_score").values(
            "name", "max_score", "color"
        )
    )

    # Defaults if none in DB
    if not thresholds:
        thresholds = [
            {"name": "High Risk", "max_score": 5.0, "color": "#dc2626"},
            {"name": "Medium Risk", "max_score": 7.5, "color": "#eab308"},
            {"name": "Low Risk", "max_score": 10.0, "color": "#16a34a"},
        ]

    return render(
        request,
        "mapview/dashboard.html",
        {
            "mapbox_access_token": settings.MAPBOX_ACCESS_TOKEN,
            "thresholds": json.dumps(thresholds),
        },
    )


@require_GET
def nta_geojson_view(request):
    try:
        with PROCESSED_GEOJSON_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except FileNotFoundError:
        return JsonResponse(
            {"error": "Processed GeoJSON file not found. Run data preparation first."},
            status=500,
        )
    except json.JSONDecodeError:
        return JsonResponse({"error": "Processed GeoJSON file is invalid."}, status=500)

    return JsonResponse(payload)


def _overlay_db_scores(payload):
    """Replace placeholder scores with real DB scores when available."""
    scores = {s.nta_code: s for s in NTARiskScore.objects.all()}
    if not scores:
        return
    for feature in payload.get("features", []):
        nta_code = feature["properties"].get("nta_code")
        if nta_code and nta_code in scores:
            s = scores[nta_code]
            feature["properties"]["placeholder_score"] = s.risk_score
            feature["properties"]["placeholder_summary"] = s.summary
            if s.top_complaint_types:
                feature["properties"]["top_issues"] = s.top_complaint_types
            feature["properties"]["total_violations"] = s.total_violations
            feature["properties"]["total_complaints"] = s.total_complaints


@require_GET
def boundary_geojson_view(request):
    level = request.GET.get("level", "nta").strip().lower()
    file_path = BOUNDARY_LEVEL_PATHS.get(level)
    if not file_path:
        return JsonResponse(
            {"error": 'Invalid level. Expected one of: "nta", "mid", "block".'},
            status=400,
        )

    try:
        with file_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except FileNotFoundError:
        return JsonResponse(
            {
                "error": f'GeoJSON for level "{level}" is not available. Run data preparation first.'
            },
            status=500,
        )
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": f'GeoJSON for level "{level}" is invalid.'}, status=500
        )

    # Overlay real risk scores from the database when available
    _overlay_db_scores(payload)

    return JsonResponse(payload)


@require_GET
def geocode_view(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 3:
        return JsonResponse(
            {"error": "Query must be at least 3 characters long."},
            status=400,
        )

    if not settings.MAPBOX_ACCESS_TOKEN:
        return JsonResponse(
            {"error": "MAPBOX_ACCESS_TOKEN is not configured on the server."},
            status=503,
        )

    encoded_query = quote(query, safe="")
    url = f"{MAPBOX_GEOCODE_BASE_URL}/{encoded_query}.json"
    params = {
        "access_token": settings.MAPBOX_ACCESS_TOKEN,
        "autocomplete": "true",
        "limit": 1,
        "types": "address,place",
        "bbox": "-74.25559,40.49612,-73.70001,40.91553",
    }

    try:
        response = requests.get(url, params=params, timeout=8)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return JsonResponse({"error": "Geocoding service request failed."}, status=502)
    except ValueError:
        return JsonResponse(
            {"error": "Geocoding service returned invalid data."}, status=502
        )

    features = data.get("features", [])
    if not features:
        return JsonResponse({"error": "No matching address found."}, status=404)

    top = features[0]
    center = top.get("center", [])
    if len(center) != 2:
        return JsonResponse({"error": "No valid coordinates returned."}, status=502)

    return JsonResponse(
        {
            "query": query,
            "label": top.get("place_name", query),
            "lng": center[0],
            "lat": center[1],
        }
    )


# ---------- Sprint 2: Violation / Complaint detail APIs ------------------- #


@require_GET
def nta_violations_view(request):
    """Return recent HPD violations for a given NTA area."""
    nta_code = request.GET.get("nta_code", "").strip()
    if not nta_code:
        return JsonResponse({"error": "nta_code parameter is required."}, status=400)

    try:
        limit = min(int(request.GET.get("limit", 50)), 200)
    except (ValueError, TypeError):
        limit = 50

    base_qs = HPDViolation.objects.filter(nta_code=nta_code).order_by(
        "-inspection_date"
    )
    total_count = base_qs.count()
    qs = base_qs[:limit]

    violations = [
        {
            "violation_id": v.violation_id,
            "address": v.address,
            "apartment": v.apartment,
            "violation_class": v.violation_class,
            "inspection_date": (
                v.inspection_date.isoformat() if v.inspection_date else None
            ),
            "nov_description": v.nov_description,
            "current_status": v.current_status,
            "violation_status": v.violation_status,
            "latitude": v.latitude,
            "longitude": v.longitude,
        }
        for v in qs
    ]

    return JsonResponse(
        {
            "nta_code": nta_code,
            "count": total_count,
            "returned_count": len(violations),
            "violations": violations,
        }
    )


@require_GET
def nta_complaints_view(request):
    """Return recent 311 complaints for a given NTA area."""
    nta_code = request.GET.get("nta_code", "").strip()
    if not nta_code:
        return JsonResponse({"error": "nta_code parameter is required."}, status=400)

    try:
        limit = min(int(request.GET.get("limit", 50)), 200)
    except (ValueError, TypeError):
        limit = 50

    base_qs = Complaint311.objects.filter(nta_code=nta_code).order_by("-created_date")
    total_count = base_qs.count()
    qs = base_qs[:limit]

    complaints = [
        {
            "unique_key": c.unique_key,
            "created_date": c.created_date.isoformat() if c.created_date else None,
            "complaint_type": c.complaint_type,
            "descriptor": c.descriptor,
            "incident_address": c.incident_address,
            "status": c.status,
            "resolution_description": c.resolution_description,
            "latitude": c.latitude,
            "longitude": c.longitude,
        }
        for c in qs
    ]

    return JsonResponse(
        {
            "nta_code": nta_code,
            "count": total_count,
            "returned_count": len(complaints),
            "complaints": complaints,
        }
    )


@require_GET
def nta_risk_summary_view(request):
    """Return the computed risk summary for a specific NTA."""
    nta_code = request.GET.get("nta_code", "").strip()
    if not nta_code:
        return JsonResponse({"error": "nta_code parameter is required."}, status=400)

    try:
        score = NTARiskScore.objects.get(nta_code=nta_code)
    except NTARiskScore.DoesNotExist:
        return JsonResponse(
            {"error": "No computed risk data for this NTA."}, status=404
        )

    return JsonResponse(
        {
            "nta_code": score.nta_code,
            "nta_name": score.nta_name,
            "borough": score.borough,
            "risk_score": score.risk_score,
            "total_violations": score.total_violations,
            "total_complaints": score.total_complaints,
            "class_a_violations": score.class_a_violations,
            "class_b_violations": score.class_b_violations,
            "class_c_violations": score.class_c_violations,
            "top_complaint_types": score.top_complaint_types,
            "summary": score.summary,
            "last_updated": score.last_updated.isoformat(),
        }
    )


@user_passes_test(_is_admin)
def ingestion_dashboard_view(request):
    """Admin-only page for managing data ingestion."""
    recency = ScoreRecencyConfig.load()
    return render(
        request,
        "mapview/ingestion_dashboard.html",
        {
            "recency_choices": ScoreRecencyConfig.RECENCY_CHOICES,
            "current_recency": recency.recency_window,
        },
    )
