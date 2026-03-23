import re

with open("scripts/prepare_nta_geojson.py", "r") as f:
    content = f.read()

# Update grid size logic
grid_size_func = """def deterministic_grid_size(nta_code, level):
    digest = hashlib.sha256(f"{nta_code}-{level}-grid".encode("utf-8")).hexdigest()
    bucket = int(digest[:6], 16)
    if level == "mid":
        return 2 + (bucket % 2)  # 2-3
    elif level == "building":
        return 3 + (bucket % 3)  # 3-5 sub-areas per block to simulate buildings
    return 4 + (bucket % 3)  # 4-6"""

content = re.sub(r'def deterministic_grid_size\(nta_code, level\):(.*?)\n\n\n' , grid_size_func + "\n\n\n", content, flags=re.DOTALL)

# Add build_building_layer function
build_building_func = """def build_building_layer(block_geojson):
    building_features = []
    for feature in block_geojson["features"]:
        building_features.extend(subdivide_feature(feature, level="building"))
    return {"type": "FeatureCollection", "features": building_features}

"""

content = contimport re

with open("scripts/pd_
with op_fu    content = f.read()

# Update grid size logic
gridts
# Update grid size l = grid_size_func = """def "    digest = hashlib.sha256(f"{nta_code}-{level}-grid".encode("uc_    bucket = int(digest[:6], 16)
    if level == "mid":
        return 2 + (bucketjs    if level == "mid":
        ai        return 2 + (b      elif level == "building":
       er        return 3 + (bucket %pu    return 4 + (bucket % 3)  # 4-6"""

content = re.sub(r'def deterministic_griut
content = re.sub(r'def deterministi, m
# Add build_building_layer function
build_building_func = """def build_building_layer(block_geojson):
    building_features = []
  n",build_building_func = """def builden    building_features = []
    for feature in block_geojson["feaen    for feature in block_js    y", "w") as f:
    f.write(content)
