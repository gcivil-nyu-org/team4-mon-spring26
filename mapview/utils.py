"""Utility functions for mapview app."""

import json
import math
from pathlib import Path


def get_nta_code_from_coordinates(lat, lng):
    """
    Given latitude and longitude, return the NTA code by checking which
    NTA polygon contains the point.

    Returns None if coordinates are outside NYC or if GeoJSON data is unavailable.
    """
    try:
        from shapely.geometry import Point, shape
        from shapely.strtree import STRtree
    except ImportError:
        return None

    # Load NTA GeoJSON data
    nta_geojson_path = Path(__file__).parent.parent / "data" / "raw" / "nyc_nta.geojson"

    if not nta_geojson_path.exists():
        return None

    try:
        with open(nta_geojson_path, "r", encoding="utf-8") as f:
            nta_data = json.load(f)
    except (IOError, json.JSONDecodeError):
        return None

    # Build spatial index
    nta_geoms = []
    nta_codes = []
    for feature in nta_data.get("features", []):
        # The raw GeoJSON uses 'nta2020' as the field name
        code = feature.get("properties", {}).get("nta2020")
        if code:
            nta_geoms.append(shape(feature["geometry"]))
            nta_codes.append(code)

    if not nta_geoms:
        return None

    tree = STRtree(nta_geoms)
    pt = Point(lng, lat)  # Note: shapely uses (x, y) = (lng, lat)

    # Query spatial index and check containment
    for idx in tree.query(pt):
        if nta_geoms[int(idx)].contains(pt):
            return nta_codes[int(idx)]

    return None


def calculate_risk_score(weighted_issue_count, min_log_weight=None, max_log_weight=None):
    """Convert weighted issue counts into a 0-10 score where 10 is safest.

    Scores are calibrated against the current recompute window so they preserve
    spread across neighborhoods instead of collapsing toward one color bucket.
    """
    if weighted_issue_count <= 0:
        return 10.0

    log_weight = math.log1p(weighted_issue_count)
    if min_log_weight is None or max_log_weight is None:
        return round(max(0.0, min(10.0, 10.0 - log_weight * 1.2)), 1)

    if math.isclose(min_log_weight, max_log_weight):
        return 5.0

    normalized = (log_weight - min_log_weight) / (max_log_weight - min_log_weight)
    return round(max(0.0, min(10.0, 10.0 * (1.0 - normalized))), 1)


def build_risk_summary(risk_score, total_violations, total_complaints):
    """Return the user-facing summary for an NTA score."""
    if risk_score <= 3.0:
        return (
            f"High-risk area — {total_violations} HPD violations and "
            f"{total_complaints} complaints on record. Immediate concerns present."
        )
    if risk_score <= 6.0:
        return (
            f"Moderate-risk area — {total_violations} violations and "
            f"{total_complaints} complaints. Some issues but generally manageable."
        )
    return (
        f"Lower-risk area — {total_violations} violations and "
        f"{total_complaints} complaints. Relatively stable conditions."
    )
