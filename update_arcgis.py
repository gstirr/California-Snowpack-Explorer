
import os
from arcgis.gis import GIS
from arcgis.features import FeatureLayer

PORTAL_URL = "https://geochicoonline.maps.arcgis.com"
LAYER_ITEM_ID = "a491f2c9260b4b3db8f50b8988a6048c"

gis = GIS(
    PORTAL_URL,
    os.environ["AGOL_USERNAME"],
    os.environ["AGOL_PASSWORD"]
)

user = gis.users.me
if user is None:
    raise RuntimeError("ArcGIS authentication failed.")

print("ArcGIS authentication successful.")

item = gis.content.get(LAYER_ITEM_ID)
if item is None:
    raise RuntimeError("Item not found.")

print(f"Item title: {item.title}")
print(f"Item type: {item.type}")
print(f"Service URL: {item.url}")

# Access the feature layer directly using its service URL.
service_url = (item.url or "").rstrip("/")

if service_url.endswith("/FeatureServer"):
    layer_url = service_url + "/0"
elif "/FeatureServer/" in service_url:
    layer_url = service_url
else:
    raise RuntimeError("Item does not have a valid feature layer URL.")

layer = FeatureLayer(layer_url, gis=gis)

print(f"Station count: {layer.query(return_count_only=True)}")
print("Connection test successful. No data modified.")

import json
from pathlib import Path

geojson_path = Path("outputs/snowpack_stations_current.geojson")

with geojson_path.open(encoding="utf-8") as f:
    geojson = json.load(f)

features = geojson["features"]

print("\n--- GEOJSON DATA ---")
print(f"Number of stations: {len(features)}")
print("GeoJSON fields:")
print(list(features[0]["properties"].keys()))

print("\n--- ARCGIS HOSTED LAYER ---")
print("Hosted layer fields:")
for field in layer.properties.fields:
    print(f"{field['name']} ({field['type']})")

print(f"Geometry type: {layer.properties.geometryType}")
print(f"Editing capabilities: {layer.properties.capabilities}")

print("\nField inspection complete. No data modified.")
