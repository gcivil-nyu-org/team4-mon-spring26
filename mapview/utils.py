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


def calculate_risk_score(
    weighted_issue_count, min_log_weight=None, max_log_weight=None
):
    """Convert weighted issue counts into a 0-10 score where 10 is safest.

    Scores mostly use an absolute log scale so dense neighborhoods are not
    punished just because they are the highest-volume NTA in the current run.
    A smaller relative component keeps some contrast across the map.
    """
    if weighted_issue_count <= 0:
        return 10.0

    absolute_weight = 0.7
    relative_weight = 0.3
    absolute_multiplier = 0.7

    log_weight = math.log1p(weighted_issue_count)
    absolute_score = max(0.0, min(10.0, 10.0 - log_weight * absolute_multiplier))

    if min_log_weight is None or max_log_weight is None:
        return round(absolute_score, 1)

    if math.isclose(min_log_weight, max_log_weight):
        relative_score = 5.0
    else:
        normalized = (log_weight - min_log_weight) / (max_log_weight - min_log_weight)
        relative_score = max(0.0, min(10.0, 10.0 * (1.0 - normalized)))

    blended_score = (absolute_score * absolute_weight) + (
        relative_score * relative_weight
    )
    return round(max(0.0, min(10.0, blended_score)), 1)


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
