#!/usr/bin/env python
"""Debug NTA code lookup from coordinates."""

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tenantguard.settings")
django.setup()

from mapview.utils import get_nta_code_from_coordinates

# Test coordinates from 405 East 42nd Street, New York, NY 10017
lat = 40.748709
lng = -73.969147

print(f"Testing NTA lookup for coordinates: ({lat}, {lng})")
print(f"Address: 405 East 42nd Street, New York, NY 10017")
print()

nta_code = get_nta_code_from_coordinates(lat, lng)

if nta_code:
    print(f"✓ SUCCESS: NTA code found: {nta_code}")
else:
    print(f"✗ FAILED: No NTA code found")
    print()
    print("Debugging...")

    # Check if file exists
    from pathlib import Path

    nta_path = Path(__file__).parent / "data" / "raw" / "nyc_nta.geojson"
    print(f"GeoJSON path: {nta_path}")
    print(f"File exists: {nta_path.exists()}")

    if nta_path.exists():
        import json

        with open(nta_path) as f:
            data = json.load(f)
        print(f"Features count: {len(data.get('features', []))}")

        # Check first feature
        if data.get("features"):
            first = data["features"][0]
            props = first.get("properties", {})
            print(f"First feature NTA code: {props.get('nta_code')}")
            print(f"Sample properties: {list(props.keys())[:5]}")
