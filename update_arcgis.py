
import json
import os
from pathlib import Path

from arcgis.gis import GIS
from arcgis.features import FeatureLayer

PORTAL_URL = "https://geochicoonline.maps.arcgis.com"
LAYER_ITEM_ID = "a491f2c9260b4b3db8f50b8988a6048c"
GEOJSON_PATH = Path("outputs/snowpack_stations_current.geojson")

# Writing is disabled until explicitly enabled in GitHub Actions.
WRITE_ENABLED = os.getenv("AGOL_WRITE_ENABLED", "false").lower() == "true"

gis = GIS(
    PORTAL_URL,
    os.environ["AGOL_USERNAME"],
    os.environ["AGOL_PASSWORD"]
)

if gis.users.me is None:
    raise RuntimeError("ArcGIS authentication failed.")

item = gis.content.get(LAYER_ITEM_ID)

if item is None or item.type != "Feature Service":
    raise RuntimeError("Expected a hosted feature service item.")

if not item.layers:
    raise RuntimeError("No feature layers found in this service.")

layer = item.layers[0]

print(f"Connected to: {item.title}")
print(f"Feature layer: {layer.properties.name}")

# Read the latest generated GeoJSON.
with GEOJSON_PATH.open(encoding="utf-8") as f:
    geojson = json.load(f)

source_features = geojson["features"]

if not source_features:
    raise RuntimeError("GeoJSON contains no stations.")

# Read the actual ArcGIS schema.
fields = {
    field["name"].lower(): field
    for field in layer.properties.fields
}

if "station_id" not in fields:
    raise RuntimeError("Hosted layer has no Station_ID field.")

id_field = fields["station_id"]["name"]
oid_field = layer.properties.objectIdField

# Never overwrite system-managed fields.
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

# Identify compatible fields by their actual names.
source_properties = source_features[0]["properties"]

source_field_names = {
    name.lower(): name
    for name in source_properties
}

if "station_id" not in source_field_names:
    raise RuntimeError("GeoJSON has no Station_ID field.")

source_id_field = source_field_names["station_id"]

editable_fields = {}

for lower_name, field in fields.items():
    if lower_name in excluded:
        continue

    if lower_name not in source_field_names:
        continue

    if not field.get("editable", True):
        continue

    # Avoid incorrectly converting dates or unsupported field types.
    if field["type"] not in {
        "esriFieldTypeString",
        "esriFieldTypeInteger",
        "esriFieldTypeSmallInteger",
        "esriFieldTypeSingle",
        "esriFieldTypeDouble",
        "esriFieldTypeBigInteger",
    }:
        continue

    editable_fields[field["name"]] = (
        source_field_names[lower_name],
        field,
    )

print(f"GeoJSON stations: {len(source_features)}")
print(f"Hosted layer stations: {layer.query(return_count_only=True)}")
print(f"Matching editable fields: {list(editable_fields)}")

if not editable_fields:
    raise RuntimeError(
        "No matching editable fields. No updates performed."
    )

# Retrieve existing station IDs and OBJECTIDs.
existing = layer.query(
    where="1=1",
    out_fields=f"{oid_field},{id_field}",
    return_geometry=False,
    return_all_records=True,
)

def normalize_id(value):
    return str(value).strip().upper() if value is not None else ""

station_lookup = {}

for feature in existing.features:
    attrs = feature.attributes
    station_id = normalize_id(attrs.get(id_field))

    if not station_id:
        continue

    if station_id in station_lookup:
        raise RuntimeError(f"Duplicate hosted station: {station_id}")

    station_lookup[station_id] = attrs[oid_field]

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

        if not number.is_integer():
            raise ValueError(
                f"Non-integer value for {field['name']}: {value}"
            )

        return int(number)

    return float(value)

# Prepare updates without changing geometries.
updates = []
unmatched = []
seen = set()

for feature in source_features:
    properties = feature["properties"]
    station_id = normalize_id(properties.get(source_id_field))

    if not station_id:
        raise RuntimeError("Source station has no Station_ID.")

    if station_id in seen:
        raise RuntimeError(f"Duplicate source station: {station_id}")

    seen.add(station_id)

    if station_id not in station_lookup:
        unmatched.append(station_id)
        continue

    attributes = {
        oid_field: station_lookup[station_id]
    }

    for target_name, (source_name, field) in editable_fields.items():
        value = properties.get(source_name)

        # Preserve existing values when source data is missing.
        if value is None or value == "":
            continue

        attributes[target_name] = convert_value(value, field)

    if len(attributes) > 1:
        updates.append({"attributes": attributes})

print(f"Stations ready to update: {len(updates)}")
print(f"Unmatched source stations: {len(unmatched)}")
print(f"Unmatched IDs: {unmatched[:20]}")

# Prevent large unexpected mismatches.
if len(updates) < 20 or len(updates) < len(source_features) * 0.8:
    raise RuntimeError(
        "Too many unmatched stations. Updates cancelled."
    )

if not WRITE_ENABLED:
    print("DRY RUN SUCCESSFUL.")
    print("No ArcGIS records were modified.")
else:
    capabilities = layer.properties.capabilities

    if "Update" not in capabilities.split(","):
        raise RuntimeError(
            f"Layer does not advertise Update capability: {capabilities}"
        )

    print("Updating ArcGIS hosted feature layer...")

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

    print(f"SUCCESS: Updated {updated} stations.")
    print("Existing geometries and layer item ID preserved.")
