#!/usr/bin/env python3
"""Build multi-level NYC GeoJSON files with placeholder livability data."""

import argparse
import hashlib
import json
from pathlib import Path

from shapely.geometry import box, mapping, shape
from shapely.strtree import STRtree

ISSUE_PACKS = [
    ["Rodent sightings", "Mold complaints", "Heating outages"],
    ["Noise complaints", "Trash overflow", "Water leaks"],
    ["Elevator outages", "Pest reports", "Heating issues"],
    ["Illegal dumping", "Street noise", "Plumbing complaints"],
    ["Building maintenance delays", "Boiler complaints", "Air quality concerns"],
]

SUMMARY_BY_BAND = {
    "low": "High complaint pressure in this area with frequent quality-of-life issues.",
    "mid": "Mixed livability profile with recurring but manageable complaint volume.",
    "high": "Relatively stable area with fewer severe complaints and better livability.",
}


def round_coords(value, precision=6):
    if isinstance(value, list):
        return [round_coords(item, precision=precision) for item in value]
    if isinstance(value, float):
        return round(value, precision)
    return value


def deterministic_score(nta_code):
    digest = hashlib.sha256(nta_code.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) % 101
    return round(bucket / 10.0, 1)


def get_summary(score):
    if score <= 3.9:
        return SUMMARY_BY_BAND["low"]
    if score <= 6.9:
        return SUMMARY_BY_BAND["mid"]
    return SUMMARY_BY_BAND["high"]


def get_issues(nta_code):
    digest = hashlib.sha256(f"{nta_code}-issues".encode("utf-8")).hexdigest()
    index = int(digest[:6], 16) % len(ISSUE_PACKS)
    return ISSUE_PACKS[index]


def build_feature(raw_feature):
    props = raw_feature.get("properties", {})
    nta_code = props.get("nta2020")
    nta_name = props.get("ntaname")
    borough = props.get("boroname")
    score = deterministic_score(nta_code)
    return {
        "type": "Feature",
        "properties": {
            "nta_code": nta_code,
            "nta_name": nta_name,
            "borough": borough,
            "placeholder_score": score,
            "placeholder_summary": get_summary(score),
            "top_issues": get_issues(nta_code),
        },
        "geometry": round_coords(raw_feature.get("geometry")),
    }


def should_include(raw_feature):
    props = raw_feature.get("properties", {})
    return (
        props.get("ntatype") == "0"
        and bool(props.get("nta2020"))
        and bool(props.get("ntaname"))
        and bool(props.get("boroname"))
    )


def transform(raw_geojson):
    features = [
        build_feature(f) for f in raw_geojson.get("features", []) if should_include(f)
    ]
    return {"type": "FeatureCollection", "features": features}


def deterministic_grid_size(nta_code, level):
    digest = hashlib.sha256(f"{nta_code}-{level}-grid".encode("utf-8")).hexdigest()
    bucket = int(digest[:6], 16)
    if level == "mid":
        return 2 + (bucket % 2)  # 2-3
    elif level == "building":
        return 3 + (bucket % 3)  # 3-5 sub-areas per block
    return 4 + (bucket % 3)  # 4-6


def adjusted_score(parent_score, child_id):
    digest = hashlib.sha256(f"{child_id}-score".encode("utf-8")).hexdigest()
    bucket = int(digest[:4], 16) % 5
    offset = [-0.6, -0.3, 0.0, 0.3, 0.6][bucket]
    return round(min(10.0, max(0.0, parent_score + offset)), 1)


def iter_polygon_parts(geometry):
    if geometry.geom_type == "Polygon":
        yield geometry
    elif geometry.geom_type == "MultiPolygon":
        for geom in geometry.geoms:
            yield geom


def subdivide_feature(base_feature, level):
    geom = shape(base_feature["geometry"])
    props = base_feature["properties"]
    grid_size = deterministic_grid_size(props["nta_code"], level)
    min_x, min_y, max_x, max_y = geom.bounds
    step_x = (max_x - min_x) / grid_size
    step_y = (max_y - min_y) / grid_size
    cells = []
    idx = 0
    for x_i in range(grid_size):
        for y_i in range(grid_size):
            candidate = box(
                min_x + (x_i * step_x),
                min_y + (y_i * step_y),
                min_x + ((x_i + 1) * step_x),
                min_y + ((y_i + 1) * step_y),
            )
            clipped = geom.intersection(candidate)
            if clipped.is_empty:
                continue
            # Ignore tiny slivers so zoomed layers remain performant and readable.
            if clipped.area < 1e-8:
                continue
            for part in iter_polygon_parts(clipped):
                cell_id = f"{props['nta_code']}-{level}-{idx}"
                idx += 1
                score = adjusted_score(props["placeholder_score"], cell_id)
                cells.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "cell_id": cell_id,
                            "parent_nta_code": props["nta_code"],
                            "nta_code": props["nta_code"],
                            "nta_name": props["nta_name"],
                            "borough": props["borough"],
                            "placeholder_score": score,
                            "placeholder_summary": get_summary(score),
                            "top_issues": get_issues(cell_id),
                            "division_level": level,
                        },
                        "geometry": round_coords(mapping(part), precision=6),
                    }
                )
    return cells


def build_mid_layer(nta_geojson):
    mid_features = []
    for feature in nta_geojson["features"]:
        mid_features.extend(subdivide_feature(feature, level="mid"))
    return {"type": "FeatureCollection", "features": mid_features}


def build_nta_geometry_index(nta_geojson):
    geoms = []
    props_by_index = {}
    for feature in nta_geojson["features"]:
        geom = shape(feature["geometry"])
        idx = len(geoms)
        geoms.append(geom)
        props_by_index[idx] = feature["properties"]
    return STRtree(geoms), geoms, props_by_index


def find_parent_nta_for_point(point, tree, geoms, props_by_index):
    for idx in tree.query(point):
        candidate = geoms[int(idx)]
        if candidate.contains(point) or candidate.intersects(point):
            props = props_by_index.get(int(idx))
            if props:
                return props
    return None


def build_block_layer(blocks_geojson, nta_geojson):
    tree, geoms, props_by_index = build_nta_geometry_index(nta_geojson)
    block_features = []
    missing_matches = 0
    for feature in blocks_geojson.get("features", []):
        geom = shape(feature["geometry"])
        if geom.is_empty:
            continue
        point = geom.representative_point()
        parent = find_parent_nta_for_point(point, tree, geoms, props_by_index)
        if not parent:
            missing_matches += 1
            continue
        raw_props = feature.get("properties", {})
        block_id = raw_props.get("geoid") or raw_props.get("bctcb2020")
        if not block_id:
            continue
        score = adjusted_score(parent["placeholder_score"], block_id)
        block_features.append(
            {
                "type": "Feature",
                "properties": {
                    "cell_id": block_id,
                    "geoid": raw_props.get("geoid"),
                    "ct2020": raw_props.get("ct2020"),
                    "cb2020": raw_props.get("cb2020"),
                    "parent_nta_code": parent["nta_code"],
                    "nta_code": parent["nta_code"],
                    "nta_name": parent["nta_name"],
                    "borough": parent["borough"],
                    "placeholder_score": score,
                    "placeholder_summary": get_summary(score),
                    "top_issues": get_issues(block_id),
                    "division_level": "block",
                },
                "geometry": round_coords(feature["geometry"], precision=6),
            }
        )
    if missing_matches:
        print(
            f"Warning: skipped {missing_matches} block features without parent NTA match."
        )
    return {"type": "FeatureCollection", "features": block_features}


def build_building_layer(block_geojson):
    building_features = []
    for feature in block_geojson.get("features", []):
        building_features.extend(subdivide_feature(feature, level="building"))
    return {"type": "FeatureCollection", "features": building_features}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default="data/raw/nyc_nta.geojson",
        help="Path to raw NTA GeoJSON input.",
    )
    parser.add_argument(
        "--blocks-input",
        default="data/raw/nyc_census_blocks_2020.geojson",
        help="Path to raw NYC census blocks GeoJSON input.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory for processed GeoJSON outputs.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8") as infile:
        raw_geojson = json.load(infile)
    with Path(args.blocks_input).open("r", encoding="utf-8") as infile:
        blocks_geojson = json.load(infile)

    nta_geojson = transform(raw_geojson)
    mid_geojson = build_mid_layer(nta_geojson)
    block_geojson = build_block_layer(blocks_geojson, nta_geojson)
    building_geojson = build_building_layer(block_geojson)

    outputs = [
        (output_dir / "nyc_nta_phase1.geojson", nta_geojson),
        (output_dir / "nyc_nta_zoom_mid.geojson", mid_geojson),
        (output_dir / "nyc_nta_zoom_block.geojson", block_geojson),
        (output_dir / "nyc_nta_zoom_building.geojson", building_geojson),
    ]
    for path, payload in outputs:
        with path.open("w", encoding="utf-8") as outfile:
            json.dump(payload, outfile, separators=(",", ":"))
        size_kb = path.stat().st_size / 1024
        print(f"Wrote {len(payload['features'])} features to {path} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
