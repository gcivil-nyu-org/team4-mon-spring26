import json
from pathlib import Path
from urllib.parse import quote

import requests
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

PROCESSED_GEOJSON_PATH = Path(settings.BASE_DIR) / "data" / "processed" / "nyc_nta_phase1.geojson"
BOUNDARY_LEVEL_PATHS = {
    "nta": Path(settings.BASE_DIR) / "data" / "processed" / "nyc_nta_phase1.geojson",
    "mid": Path(settings.BASE_DIR) / "data" / "processed" / "nyc_nta_zoom_mid.geojson",
    "block": Path(settings.BASE_DIR) / "data" / "processed" / "nyc_nta_zoom_block.geojson",
}
MAPBOX_GEOCODE_BASE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"


def dashboard_view(request):
    return render(
        request,
        "mapview/dashboard.html",
        {"mapbox_access_token": settings.MAPBOX_ACCESS_TOKEN},
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
            {"error": f'GeoJSON for level "{level}" is not available. Run data preparation first.'},
            status=500,
        )
    except json.JSONDecodeError:
        return JsonResponse({"error": f'GeoJSON for level "{level}" is invalid.'}, status=500)

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
        return JsonResponse({"error": "Geocoding service returned invalid data."}, status=502)

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
