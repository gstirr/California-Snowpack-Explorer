
import os
from arcgis.gis import GIS
from arcgis.features import FeatureLayer

PORTAL_URL = "https://geochicoonline.maps.arcgis.com"
LAYER_ITEM_ID = "45bf7b8ead57497e94810ecbed1b61a5"

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
