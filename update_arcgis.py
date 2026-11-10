
import os
from arcgis.gis import GIS

PORTAL_URL = "https://geochicoonline.maps.arcgis.com"
LAYER_ITEM_ID = "45bf7b8ead57497e94810ecbed1b61a5"

# Authenticate using GitHub Actions Secrets
gis = GIS(
    PORTAL_URL,
    os.environ["AGOL_USERNAME"],
    os.environ["AGOL_PASSWORD"]
)

# Verify authentication
user = gis.users.me
if user is None:
    raise RuntimeError("ArcGIS authentication failed.")

print(f"Authenticated as: {user.username}")

# Find the existing hosted feature layer
item = gis.content.get(LAYER_ITEM_ID)

if item is None:
    raise RuntimeError("Hosted feature layer not found.")

if not item.layers:
    raise RuntimeError("Item contains no feature layers.")

layer = item.layers[0]

print(f"Found layer: {item.title}")
print(f"Layer owner: {item.owner}")
print(f"Station count: {layer.query(return_count_only=True)}")
print("Connection test successful. No data modified.")
