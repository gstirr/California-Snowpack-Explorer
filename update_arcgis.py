
import json
import math
import os
from pathlib import Path

from arcgis.gis import GIS
from arcgis.features import FeatureLayer

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

PORTAL_URL = "https://geochicoonline.maps.arcgis.com"
LAYER_ITEM_ID = "a491f2c9260b4b3db8f50b8988a6048c"
GEOJSON_PATH = Path("outputs/snowpack_stations_current.geojson")

# Keep disabled until the dry run succeeds.
WRITE_ENABLED = (
    os.getenv("AGOL_WRITE_ENABLED", "false").lower() == "true"
)

# --------------------------------------------------
# CONNECT TO ARCGIS ONLINE
# --------------------------------------------------

gis = GIS(
    PORTAL_URL,
    os.environ["AGOL_USERNAME"],
    os.environ["AGOL_PASSWORD"]
)

if gis.users.me is None:
    raise RuntimeError("ArcGIS authentication failed.")

print("ArcGIS authentication successful.")

item = gis.content.get(LAYER_ITEM_ID)

if item is None:
    raise RuntimeError("Hosted feature layer item not found.")

print(f"Item title: {item.title}")
print(f"Item type: {item.type}")
print(f"Service URL: {item.url}")

if item.type != "Feature Service":
    raise RuntimeError("Expected a Feature Service item.")

# Connect directly through the service URL.
# This avoids the item.layers issue from the previous run.

service_url = (item.url or "").rstrip("/")

if service_url.endswith("/FeatureServer"):
    layer_url = service_url + "/0"
elif "/FeatureServer/" in service_url:
    layer_url = service_url
else:
    raise RuntimeError("Invalid feature layer service URL.")

layer = FeatureLayer(layer_url, gis=gis)

print(f"Connected to layer: {layer.properties.name}")
print(f"Existing station count: {layer.query(return_count_only=True)}")

# --------------------------------------------------
# LOAD GEOJSON
# --------------------------------------------------

if not GEOJSON_PATH.exists():
    raise FileNotFoundError(f"Missing GeoJSON: {GEOJSON_PATH}")

with GEOJSON_PATH.open(encoding="utf-8") as f:
    geojson = json.load(f)

source_features = geojson["features"]

if not source_features:
    raise RuntimeError("GeoJSON contains no stations.")

print(f"GeoJSON stations: {len(source_features)}")

# --------------------------------------------------
# INSPECT FIELD STRUCTURE
# --------------------------------------------------

fields = {
    field["name"].lower(): field
    for field in layer.properties.fields
}

if "station_id" not in fields:
    raise RuntimeError("Hosted layer has no Station_ID field.")

id_field = fields["station_id"]["name"]
oid_field = layer.properties.objectIdField

source_properties = source_features[0]["properties"]

source_field_names = {
    name.lower(): name
    for name in source_properties
}

if "station_id" not in source_field_names:
    raise RuntimeError("GeoJSON has no Station_ID field.")

source_id_field = source_field_names["station_id"]

# Protect system-managed ArcGIS fields.

excluded = {
    oid_field.lower(),
    id_field.lower(),
    "globalid",
    "shape__area",
    "shape__length",
    "creationdate",
    "creator",
    "editdate",
    "editor",
}

supported_types = {
    "esriFieldTypeString",
    "esriFieldTypeInteger",
    "esriFieldTypeSmallInteger",
    "esriFieldTypeSingle",
    "esriFieldTypeDouble",
    "esriFieldTypeBigInteger",
}

editable_fields = {}

for lower_name, field in fields.items():

    if lower_name in excluded:
        continue

    if lower_name not in source_field_names:
        continue

    if not field.get("editable", True):
        continue

    if field["type"] not in supported_types:
        continue

    editable_fields[field["name"]] = (
        source_field_names[lower_name],
        field,
    )

print("\n--- FIELD MATCHING ---")
print(f"Matching editable fields: {list(editable_fields)}")

if not editable_fields:
    raise RuntimeError(
        "No matching editable fields. No updates performed."
    )

# --------------------------------------------------
# RETRIEVE EXISTING STATIONS
# --------------------------------------------------

existing = layer.query(
    where="1=1",
    out_fields=f"{oid_field},{id_field}",
    return_geometry=False,
    return_all_records=True,
)

def normalize_id(value):
    if value is None:
        return ""
    return str(value).strip().upper()

station_lookup = {}

for feature in existing.features:

    attrs = feature.attributes
    station_id = normalize_id(attrs.get(id_field))

    if not station_id:
        continue

    if station_id in station_lookup:
        raise RuntimeError(
            f"Duplicate hosted station: {station_id}"
        )

    station_lookup[station_id] = attrs[oid_field]

print(f"Existing stations indexed: {len(station_lookup)}")

# --------------------------------------------------
# CONVERT ATTRIBUTE VALUES
# --------------------------------------------------

def convert_value(value, field):

    if value is None or value == "":
        return None

    field_type = field["type"]

    if field_type == "esriFieldTypeString":

        value = str(value)
        max_length = field.get("length")

        if max_length and len(value) > max_length:
            raise ValueError(
                f"Value exceeds field length: {field['name']}"
            )

        return value

    if field_type in {
        "esriFieldTypeInteger",
        "esriFieldTypeSmallInteger",
        "esriFieldTypeBigInteger",
    }:

        number = float(value)

        if not math.isfinite(number) or not number.is_integer():
            raise ValueError(
                f"Invalid integer for {field['name']}: {value}"
            )

        return int(number)

    number = float(value)

    if not math.isfinite(number):
        return None

    return number

# --------------------------------------------------
# PREPARE STATION UPDATES
# --------------------------------------------------

updates = []
unmatched = []
seen = set()

for feature in source_features:

    properties = feature["properties"]

    station_id = normalize_id(
        properties.get(source_id_field)
    )

    if not station_id:
        raise RuntimeError(
            "Source station has no Station_ID."
        )

    if station_id in seen:
        raise RuntimeError(
            f"Duplicate source station: {station_id}"
        )

    seen.add(station_id)

    if station_id not in station_lookup:
        unmatched.append(station_id)
        continue

    attributes = {
        oid_field: station_lookup[station_id]
    }

    for target_name, (source_name, field) in editable_fields.items():

        value = properties.get(source_name)

        # Preserve existing values when data is missing.
        if value is None or value == "":
            continue

        converted = convert_value(value, field)

        if converted is None:
            continue

        attributes[target_name] = converted

    if len(attributes) > 1:
        updates.append({
            "attributes": attributes
        })

# --------------------------------------------------
# VALIDATE BEFORE WRITING
# --------------------------------------------------

print("\n--- UPDATE SUMMARY ---")
print(f"Source stations: {len(source_features)}")
print(f"Existing hosted stations: {len(station_lookup)}")
print(f"Stations ready to update: {len(updates)}")
print(f"Unmatched source stations: {len(unmatched)}")
print(f"Unmatched IDs: {unmatched[:20]}")

if (
    len(updates) < 20
    or len(updates) < len(source_features) * 0.8
):
    raise RuntimeError(
        "Too many unmatched stations. Updates cancelled."
    )

# --------------------------------------------------
# DRY RUN OR LIVE UPDATE
# --------------------------------------------------

if not WRITE_ENABLED:

    print("\nDRY RUN SUCCESSFUL.")
    print("No ArcGIS records were modified.")

else:

    capabilities = layer.properties.capabilities

    if "Update" not in [
        capability.strip()
        for capability in capabilities.split(",")
    ]:
        raise RuntimeError(
            f"Layer does not support updates: {capabilities}"
        )

    print("\nUpdating ArcGIS hosted feature layer...")

    updated = 0

    for start in range(0, len(updates), 50):

        batch = updates[start:start + 50]

        result = layer.edit_features(
            updates=batch,
            rollback_on_failure=True,
        )

        results = result.get("updateResults", [])

        if len(results) != len(batch) or not all(
            r.get("success") for r in results
        ):
            raise RuntimeError(
                f"ArcGIS update failed: {results}"
            )

        updated += len(results)

        print(f"Updated {updated} stations.")

    print(f"\nSUCCESS: Updated {updated} stations.")
    print("Existing geometries preserved.")
    print("Feature layer item ID unchanged.")
