"""Utility functions for mapview app."""

import json
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
