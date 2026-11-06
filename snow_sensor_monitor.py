import os

import json

import pandas as pd

import folium





# --------------------------------------------------

# SETTINGS

# --------------------------------------------------



SWE_URL = "https://cdec.water.ca.gov/dynamicapp/getAll?sens_num=3"

STATIONS_URL = "https://cdec.water.ca.gov/reportapp/javareports?name=SnowSensors"



OUTPUT_DIR = "outputs"



os.makedirs(OUTPUT_DIR, exist_ok=True)





# --------------------------------------------------

# 1. DOWNLOAD LIVE CDEC DATA

# --------------------------------------------------



print("California Snow Sensor Monitor")

print("--------------------------------")

print("Downloading current SWE observations...")



snow = pd.read_html(SWE_URL)[0]



print("Downloading active snow sensor metadata...")



stations = pd.read_html(STATIONS_URL)[0]



print("CDEC data downloaded successfully.")





# --------------------------------------------------

# 2. CLEAN LIVE SWE DATA

# --------------------------------------------------



snow_clean = snow[

    snow["ID"].astype(str).str.match(r"^[A-Z0-9]{3}$")

].copy()



snow_clean["Elevation_ft"] = (

    snow_clean["Elev."]

    .astype(str)

    .str.replace("'", "", regex=False)

    .astype(float)

)



snow_clean["SWE_in"] = (

    snow_clean["Value"]

    .astype(str)

    .str.replace('"', "", regex=False)

    .astype(float)

)



# Preserve the original sensor value.

# Negative SWE cannot represent physical snowpack,

# so a separate analysis field is clipped at zero.

snow_clean["SWE_analysis"] = (

    snow_clean["SWE_in"].clip(lower=0)

)



print(

    f"Live SWE observations cleaned: "

    f"{len(snow_clean)}"

)





# --------------------------------------------------

# 3. CLEAN STATION METADATA

# --------------------------------------------------



stations.columns = [

    "ID",

    "Station Name",

    "Elevation_ft",

    "Latitude",

    "Longitude",

    "April1_Avg_SWE",

    "Operator"

]



stations_clean = stations[

    stations["ID"]

    .astype(str)

    .str.match(r"^[A-Z0-9]{3}$")

].copy()



stations_clean["Latitude"] = pd.to_numeric(

    stations_clean["Latitude"],

    errors="coerce"

)



stations_clean["Longitude"] = pd.to_numeric(

    stations_clean["Longitude"],

    errors="coerce"

)





# --------------------------------------------------

# 4. JOIN LIVE DATA TO SPATIAL METADATA

# --------------------------------------------------



snow_map = snow_clean.merge(

    stations_clean[

        [

            "ID",

            "Latitude",

            "Longitude",

            "April1_Avg_SWE",

            "Operator"

        ]

    ],

    on="ID",

    how="left"

)



print(

    f"Stations joined: {len(snow_map)}"

)



print(

    "Stations missing coordinates: "

    f"{snow_map['Latitude'].isna().sum()}"

)





# --------------------------------------------------

# 5. PROCESS OBSERVATION TIMES

# --------------------------------------------------



snow_map["Observation_Time"] = pd.to_datetime(

    snow_map["Date/Time"],

    errors="coerce"

)



latest_observation = (

    snow_map["Observation_Time"].max()

)



snow_map["Hours_Behind_Latest"] = (

    latest_observation

    - snow_map["Observation_Time"]

).dt.total_seconds() / 3600





# --------------------------------------------------

# 6. QA/QC

# --------------------------------------------------



def check_quality(row):



    flags = []



    if row["SWE_in"] < 0:

        flags.append("NEGATIVE_SWE")



    if (

        pd.isna(row["Latitude"])

        or pd.isna(row["Longitude"])

    ):

        flags.append("MISSING_COORDINATES")



    if row["Hours_Behind_Latest"] >= 6:

        flags.append("DELAYED_6H")



    if flags:

        return "; ".join(flags)



    return "OK"





snow_map["QC_Status"] = snow_map.apply(

    check_quality,

    axis=1

)



ok_count = (

    snow_map["QC_Status"] == "OK"

).sum()



negative_count = (

    snow_map["QC_Status"]

    .str.contains("NEGATIVE_SWE")

    .sum()

)



missing_coordinates_count = (

    snow_map["QC_Status"]

    .str.contains("MISSING_COORDINATES")

    .sum()

)



delayed_count = (

    snow_map["QC_Status"]

    .str.contains("DELAYED_6H")

    .sum()

)



print()

print("QA/QC SUMMARY")

print("-------------")

print(

    f"Latest observation: "

    f"{latest_observation}"

)

print(

    f"Total observations: "

    f"{len(snow_map)}"

)

print(

    f"OK: {ok_count}"

)

print(

    f"Negative SWE: {negative_count}"

)

print(

    "Missing coordinates: "

    f"{missing_coordinates_count}"

)

print(

    f"Delayed 6+ hours: "

    f"{delayed_count}"

)





# --------------------------------------------------

# 7. PREPARE CLEAN EXPORT TABLE

# --------------------------------------------------



export_data = snow_map[

    [

        "ID",

        "Station Name",

        "Elevation_ft",

        "Latitude",

        "Longitude",

        "Observation_Time",

        "SWE_in",

        "SWE_analysis",

        "Hours_Behind_Latest",

        "Operator",

        "QC_Status"

    ]

].copy()



export_data = export_data.rename(

    columns={

        "Station Name": "Station_Name",

        "SWE_in": "SWE_Raw_in",

        "SWE_analysis": "SWE_Clean_in"

    }

)





# --------------------------------------------------

# 8. EXPORT CSV

# --------------------------------------------------



csv_path = os.path.join(

    OUTPUT_DIR,

    "california_snow_sensors_current.csv"

)



export_data.to_csv(

    csv_path,

    index=False

)



print()

print(

    f"CSV exported: "

    f"{len(export_data)} observations"

)





# --------------------------------------------------

# 9. EXPORT QA/QC REPORT

# --------------------------------------------------



quality_issues = export_data[

    export_data["QC_Status"] != "OK"

].copy()



qc_path = os.path.join(

    OUTPUT_DIR,

    "snow_sensor_quality_issues.csv"

)



quality_issues.to_csv(

    qc_path,

    index=False

)



print(

    "QA/QC report exported: "

    f"{len(quality_issues)} flagged observations"

)





# --------------------------------------------------

# 10. EXPORT GEOJSON

# --------------------------------------------------



geojson_data = {

    "type": "FeatureCollection",

    "features": []

}



spatial_data = export_data.dropna(

    subset=["Latitude", "Longitude"]

)



for _, row in spatial_data.iterrows():



    operator = (

        None

        if pd.isna(row["Operator"])

        else str(row["Operator"])

    )



    feature = {

        "type": "Feature",



        "geometry": {

            "type": "Point",

            "coordinates": [

                float(row["Longitude"]),

                float(row["Latitude"])

            ]

        },



        "properties": {

            "ID": str(row["ID"]),

            "Station_Name": str(

                row["Station_Name"]

            ),

            "Elevation_ft": float(

                row["Elevation_ft"]

            ),

            "Observation_Time": str(

                row["Observation_Time"]

            ),

            "SWE_Raw_in": float(

                row["SWE_Raw_in"]

            ),

            "SWE_Clean_in": float(

                row["SWE_Clean_in"]

            ),

            "Operator": operator,

            "QC_Status": str(

                row["QC_Status"]

            )

        }

    }



    geojson_data["features"].append(

        feature

    )



geojson_path = os.path.join(

    OUTPUT_DIR,

    "california_snow_sensors_current.geojson"

)



with open(

    geojson_path,

    "w",

    encoding="utf-8"

) as file:



    json.dump(

        geojson_data,

        file,

        indent=2

    )



print(

    "GeoJSON exported: "

    f"{len(geojson_data['features'])} "

    "point features"

)





# --------------------------------------------------

# 11. CREATE INTERACTIVE MAP

# --------------------------------------------------



snow_map_view = folium.Map(

    location=[38.5, -120.0],

    zoom_start=6,

    tiles="OpenStreetMap"

)



for _, row in spatial_data.iterrows():



    swe = row["SWE_Clean_in"]



    if swe == 0:

        color = "gray"

        category = "No measurable SWE"



    elif swe < 1:

        color = "lightblue"

        category = "Less than 1 inch"



    elif swe < 5:

        color = "blue"

        category = "1–5 inches"



    else:

        color = "darkblue"

        category = "5+ inches"



    folium.CircleMarker(

        location=[

            row["Latitude"],

            row["Longitude"]

        ],

        radius=6,

        color=color,

        weight=1,

        fill=True,

        fill_color=color,

        fill_opacity=0.8,



        tooltip=(

            f"{row['Station_Name']} | "

            f"{swe:.2f} in SWE"

        ),



        popup=(

            f"<b>{row['Station_Name']}</b><br>"

            f"Station ID: {row['ID']}<br>"

            f"Elevation: "

            f"{row['Elevation_ft']:.0f} ft<br>"

            f"SWE: {swe:.2f} in<br>"

            f"QA/QC: {row['QC_Status']}<br>"

            f"Category: {category}"

        )

    ).add_to(snow_map_view)





# --------------------------------------------------

# 12. ADD MAP TITLE AND LEGEND

# --------------------------------------------------



map_date = latest_observation.strftime(

    "%B %d, %Y"

)



title_and_legend = f"""

<div style="

    position: fixed;

    top: 10px;

    left: 50px;

    z-index: 9999;

    background-color: white;

    padding: 10px 14px;

    border: 1px solid gray;

    border-radius: 5px;

    font-family: Arial;

">

    <b>California Snow Sensor Monitor</b><br>



    <span style="font-size: 12px;">

        CDEC SWE observations — {map_date}

    </span>



    <hr style="margin: 6px 0;">



    <span style="color: gray;">●</span>

    No measurable SWE<br>



    <span style="color: lightblue;">●</span>

    Less than 1 inch<br>



    <span style="color: blue;">●</span>

    1–5 inches<br>



    <span style="color: darkblue;">●</span>

    5+ inches

</div>

"""



snow_map_view.get_root().html.add_child(

    folium.Element(title_and_legend)

)



map_path = os.path.join(

    OUTPUT_DIR,

    "california_snow_sensor_map.html"

)



snow_map_view.save(

    map_path

)





# --------------------------------------------------


# BEGIN DWR REGIONAL INTEGRATION

# --------------------------------------------------
# 13. HYDROLOGIC REGION SPATIAL ANALYSIS
# --------------------------------------------------

import geopandas as gpd
import requests

print()
print("Downloading California DWR hydrologic regions...")

region_url = (
    "https://gis.water.ca.gov/arcgis/rest/services/"
    "Boundaries/i03_Hydrologic_Regions/FeatureServer/0/query"
)


from pathlib import Path

region_cache = (
    Path(__file__).resolve().parent
    / "data"
    / "dwr_hydrologic_regions.geojson"
)

if region_cache.exists():

    print("Loading cached DWR hydrologic regions...")

    regions_gdf = gpd.read_file(region_cache)

else:

    print("No cached boundaries found. Downloading...")

    response = requests.get(
        region_url,
        params={
            "where": "1=1",
            "outFields": "HR_NAME",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson"
        },
        timeout=60
    )

    response.raise_for_status()

    region_features = response.json()["features"]

    regions_gdf = gpd.GeoDataFrame.from_features(
        region_features,
        crs="EPSG:4326"
    )

    region_cache.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    regions_gdf.to_file(
        region_cache,
        driver="GeoJSON",
        index=False
    )

    print("DWR boundaries cached successfully.")

# Validate boundaries before spatial analysis
assert len(regions_gdf) > 0
assert "HR_NAME" in regions_gdf.columns
assert regions_gdf.crs is not None

regions_gdf = regions_gdf.to_crs("EPSG:4326")

# Convert current station records to spatial features
station_points = export_data.dropna(
    subset=["Latitude", "Longitude"]
).copy()

station_gdf = gpd.GeoDataFrame(
    station_points,
    geometry=gpd.points_from_xy(
        station_points["Longitude"],
        station_points["Latitude"]
    ),
    crs="EPSG:4326"
)

# Assign each station to its DWR hydrologic region
station_regions = gpd.sjoin(
    station_gdf,
    regions_gdf[["HR_NAME", "geometry"]],
    how="left",
    predicate="intersects"
)

# Prevent accidental duplication at polygon boundaries
assert not station_regions["ID"].duplicated().any(), (
    "Spatial join produced duplicate station records"
)

region_lookup = station_regions[
    ["ID", "HR_NAME"]
].copy()

regional_export = export_data.merge(
    region_lookup,
    on="ID",
    how="left",
    validate="one_to_one"
)

# Distinguish Nevada stations from stations without coordinates
regional_export["Hydrologic_Region"] = (
    regional_export["HR_NAME"]
    .fillna("Outside California DWR regions")
)

missing_coordinates = regional_export[
    ["Latitude", "Longitude"]
].isna().any(axis=1)

regional_export.loc[
    missing_coordinates, "Hydrologic_Region"
] = "Not mapped"

# Only QC-approved observations are used in regional averages
regional_export["SWE_Valid_in"] = (
    regional_export["SWE_Clean_in"].where(
        regional_export["QC_Status"].eq("OK")
    )
)

regional_export = regional_export.rename(
    columns={
        "ID": "Station_ID",
        "Hours_Behind_Latest": "Hours_Behind"
    }
)

regional_export = regional_export.drop(
    columns=["HR_NAME"]
)

regional_export["Observation_Time"] = pd.to_datetime(
    regional_export["Observation_Time"],
    errors="coerce"
).dt.strftime("%Y-%m-%d %H:%M:%S")

# Regional summary statistics
regional_data = regional_export[
    ~regional_export["Hydrologic_Region"].isin(
        ["Outside California DWR regions", "Not mapped"]
    )
].copy()

regional_summary = (
    regional_data.groupby("Hydrologic_Region")
    .agg(
        Total_Stations=("Station_ID", "count"),
        Valid_Stations=("SWE_Valid_in", "count"),
        Average_SWE_in=("SWE_Valid_in", "mean"),
        Median_SWE_in=("SWE_Valid_in", "median"),
        Maximum_SWE_in=("SWE_Valid_in", "max"),
        Average_Elevation_ft=("Elevation_ft", "mean")
    )
    .reset_index()
)

# Export enhanced station CSV
regional_export.to_csv(
    os.path.join(
        OUTPUT_DIR, "snowpack_stations_current.csv"
    ),
    index=False
)

# Export enhanced GeoJSON
mapped_stations = regional_export.dropna(
    subset=["Latitude", "Longitude"]
).copy()

mapped_gdf = gpd.GeoDataFrame(
    mapped_stations,
    geometry=gpd.points_from_xy(
        mapped_stations["Longitude"],
        mapped_stations["Latitude"]
    ),
    crs="EPSG:4326"
)

mapped_gdf.to_file(
    os.path.join(
        OUTPUT_DIR, "snowpack_stations_current.geojson"
    ),
    driver="GeoJSON",
    index=False
)

# Export regional statistics
regional_summary.to_csv(
    os.path.join(
        OUTPUT_DIR, "regional_swe_summary.csv"
    ),
    index=False
)

print()
print("DWR REGIONAL ANALYSIS COMPLETE")
print("------------------------------")
print("DWR polygons:", len(regions_gdf))
print("Stations:", len(regional_export))
print("Mapped stations:", len(mapped_gdf))
print("Assigned to regions:", len(regional_data))
print("Regional summaries:", len(regional_summary))
print("Enhanced CSV, GeoJSON and regional summary exported.")

# END DWR REGIONAL INTEGRATION


# BEGIN HISTORICAL SWE INTEGRATION

# --------------------------------------------------
# 14. DOWNLOAD AND ANALYZE HISTORICAL SWE
# --------------------------------------------------

import io
import time
import requests

print()
print("Downloading historical SWE observations...")

historical_url = (
    "https://cdec.water.ca.gov/dynamicapp/req/CSVDataServlet"
)

latest_time = pd.to_datetime(
    regional_export["Observation_Time"]
).max()

# Include an extra day to cover the 14-day comparison.
start_date = (
    latest_time.normalize() - pd.Timedelta(days=15)
).strftime("%Y-%m-%d")

end_date = (
    latest_time.normalize() + pd.Timedelta(days=1)
).strftime("%Y-%m-%d")

station_ids = (
    regional_export["Station_ID"].dropna()
    .astype(str).unique().tolist()
)

historical_batches = []

# Request 10 stations at a time.
for batch_start in range(0, len(station_ids), 10):

    batch_ids = station_ids[batch_start:batch_start + 10]

    response = requests.get(
        historical_url,
        params={
            "Stations": ",".join(batch_ids),
            "SensorNums": "3",
            "dur_code": "H",
            "Start": start_date,
            "End": end_date
        },
        timeout=90
    )

    response.raise_for_status()

    try:
        batch = pd.read_csv(
            io.StringIO(response.text),
            dtype=str
        )
    except pd.errors.EmptyDataError:
        batch = pd.DataFrame()

    if not batch.empty:

        required = {"STATION_ID", "DATE TIME", "VALUE"}

        if not required.issubset(batch.columns):
            raise ValueError(
                "Unexpected historical CDEC response columns: "
                + str(batch.columns.tolist())
            )

        historical_batches.append(batch)

    print(
        f"Historical batch "
        f"{batch_start // 10 + 1}: "
        f"{len(batch)} records"
    )

    if batch_start + 10 < len(station_ids):
        time.sleep(1.5)

if not historical_batches:
    raise RuntimeError(
        "No historical SWE observations were downloaded."
    )

history_raw = pd.concat(
    historical_batches,
    ignore_index=True
)

# --------------------------------------------------
# 15. CLEAN HISTORICAL OBSERVATIONS
# --------------------------------------------------

history_clean = history_raw.copy()

history_clean["Observation_Time"] = pd.to_datetime(
    history_clean["DATE TIME"].str.strip(),
    format="%Y%m%d %H%M",
    errors="coerce"
)

history_clean["SWE_raw_in"] = pd.to_numeric(
    history_clean["VALUE"],
    errors="coerce"
)

history_clean = history_clean.dropna(
    subset=["STATION_ID", "Observation_Time"]
)

history_clean = (
    history_clean
    .sort_values(["STATION_ID", "Observation_Time"])
    .drop_duplicates(
        subset=["STATION_ID", "Observation_Time"],
        keep="last"
    )
    .copy()
)

# Negative readings are retained for QA,
# but excluded from SWE trend calculations.
history_clean["SWE_analysis"] = (
    history_clean["SWE_raw_in"]
    .where(history_clean["SWE_raw_in"] >= 0)
)

history_clean["History_QC"] = "OK"

history_clean.loc[
    history_clean["SWE_raw_in"].isna(),
    "History_QC"
] = "MISSING_SWE"

history_clean.loc[
    history_clean["SWE_raw_in"] < 0,
    "History_QC"
] = "NEGATIVE_SWE"

history_clean["Extreme_Negative_Review"] = (
    history_clean["SWE_raw_in"] < -5
)

history_export_auto = history_clean[
    [
        "STATION_ID",
        "Observation_Time",
        "SWE_raw_in",
        "SWE_analysis",
        "History_QC",
        "Extreme_Negative_Review"
    ]
].copy()

history_export_auto.to_csv(
    os.path.join(OUTPUT_DIR, "swe_history_15d.csv"),
    index=False
)

# --------------------------------------------------
# 16. CALCULATE TIMESTAMP-ALIGNED SWE CHANGES
# --------------------------------------------------

history_by_station = {
    sid: group.sort_values("Observation_Time")
    for sid, group in history_export_auto.groupby("STATION_ID")
}

def calculate_current_trends(station):

    sid = station["Station_ID"]
    current_time = pd.to_datetime(
        station["Observation_Time"],
        errors="coerce"
    )
    current_swe = station["SWE_Raw_in"]

    result = {
        "Station_ID": sid,
        "Change_24h": float("nan"),
        "Change_7d": float("nan"),
        "Change_14d": float("nan")
    }

    if (
        pd.isna(current_time)
        or pd.isna(current_swe)
        or current_swe < 0
        or station["QC_Status"] != "OK"
    ):
        return result

    if latest_time - current_time > pd.Timedelta(hours=6):
        return result

    station_history = history_by_station.get(sid)

    if station_history is None:
        return result

    station_history = station_history[
        station_history["SWE_analysis"].notna()
        & (station_history["Observation_Time"] <= current_time)
    ]

    for days, field in [
        (1, "Change_24h"),
        (7, "Change_7d"),
        (14, "Change_14d")
    ]:

        target_time = current_time - pd.Timedelta(days=days)

        earlier = station_history[
            station_history["Observation_Time"] <= target_time
        ]

        if earlier.empty:
            continue

        previous = earlier.iloc[-1]

        gap = target_time - previous["Observation_Time"]

        if gap <= pd.Timedelta(hours=2):
            result[field] = round(
                current_swe - previous["SWE_analysis"],
                2
            )

    return result


trends_auto = pd.DataFrame([
    calculate_current_trends(station)
    for _, station in regional_export.iterrows()
])

regional_export = regional_export.merge(
    trends_auto,
    on="Station_ID",
    how="left",
    validate="one_to_one"
)

# --------------------------------------------------
# 17. UPDATE ARCGIS EXPORTS WITH HISTORICAL TRENDS
# --------------------------------------------------

regional_export.to_csv(
    os.path.join(
        OUTPUT_DIR, "snowpack_stations_current.csv"
    ),
    index=False
)

mapped_stations = regional_export.dropna(
    subset=["Latitude", "Longitude"]
).copy()

mapped_gdf = gpd.GeoDataFrame(
    mapped_stations,
    geometry=gpd.points_from_xy(
        mapped_stations["Longitude"],
        mapped_stations["Latitude"]
    ),
    crs="EPSG:4326"
)

mapped_gdf.to_file(
    os.path.join(
        OUTPUT_DIR, "snowpack_stations_current.geojson"
    ),
    driver="GeoJSON",
    index=False
)

# Calculate regional trends from QC-approved stations only.
valid_trend_regions = regional_export[
    (regional_export["QC_Status"] == "OK")
    & (~regional_export["Hydrologic_Region"].isin(
        ["Not mapped", "Outside California DWR regions"]
    ))
]

region_trends = (
    valid_trend_regions.groupby("Hydrologic_Region")
    .agg(
        Average_24h_Change=("Change_24h", "mean"),
        Average_7d_Change=("Change_7d", "mean"),
        Average_14d_Change=("Change_14d", "mean"),
        Stations_With_24h_Trend=("Change_24h", "count"),
        Stations_With_7d_Trend=("Change_7d", "count"),
        Stations_With_14d_Trend=("Change_14d", "count")
    )
    .reset_index()
)

regional_summary = regional_summary.merge(
    region_trends,
    on="Hydrologic_Region",
    how="left",
    validate="one_to_one"
)

regional_summary.to_csv(
    os.path.join(
        OUTPUT_DIR, "regional_swe_summary.csv"
    ),
    index=False
)

print()
print("HISTORICAL SWE ANALYSIS COMPLETE")
print("--------------------------------")
print("Historical records:", len(history_export_auto))
print(
    "Stations with history:",
    history_export_auto["STATION_ID"].nunique()
)
print("24-hour trends:", trends_auto["Change_24h"].notna().sum())
print("7-day trends:", trends_auto["Change_7d"].notna().sum())
print("14-day trends:", trends_auto["Change_14d"].notna().sum())
print("ArcGIS exports updated with trend fields.")

# END HISTORICAL SWE INTEGRATION


# BEGIN ENHANCED INTERACTIVE MAP

# --------------------------------------------------
# 18. BUILD ENHANCED INTERACTIVE MAP
# --------------------------------------------------

from html import escape

print()
print("Building enhanced interactive map...")

enhanced_map = folium.Map(
    location=[38.5, -120.0],
    zoom_start=6,
    tiles=None,
    control_scale=True
)

folium.TileLayer(
    tiles=(
        "https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Topo_Map/MapServer/tile/{z}/{y}/{x}"
    ),
    attr="Tiles © Esri",
    name="Esri World Topographic Map",
    control=False
).add_to(enhanced_map)

view_settings = [
    ("Current SWE", "SWE_Valid_in"),
    ("24-Hour SWE Change", "Change_24h"),
    ("7-Day SWE Change", "Change_7d"),
    ("14-Day SWE Change", "Change_14d"),
    ("Data Quality", "QC_Status")
]

map_layers = {}

for index, (view_name, field) in enumerate(view_settings):

    layer = folium.FeatureGroup(
        name=view_name,
        overlay=False,
        show=(index == 0)
    )

    layer.add_to(enhanced_map)
    map_layers[view_name] = layer


def classify_map_value(view_name, station):

    qc = station["QC_Status"]

    if view_name == "Data Quality":

        if qc == "OK":
            return "#219653", "No current QC flags"

        if qc == "NEGATIVE_SWE":
            return "#F59E0B", "Negative SWE"

        if qc == "MISSING_COORDINATES":
            return "#64748B", "Missing coordinates"

        if qc == "DELAYED_6H":
            return "#8B5CF6", "Delayed observation"

        return "#D9534F", str(qc)

    if view_name == "Current SWE":

        value = station["SWE_Valid_in"]

        if pd.isna(value):
            return "#D1D5DB", "Unavailable / QC excluded"

        if value == 0:
            return "#64748B", "No measurable SWE"

        if value < 1:
            return "#7DD3FC", "Less than 1 inch"

        if value < 5:
            return "#2563EB", "1–5 inches"

        return "#1E3A8A", "5+ inches"

    field = dict(view_settings)[view_name]
    value = station[field]

    if pd.isna(value):
        return "#D1D5DB", "Trend unavailable"

    if value > 0.05:
        return "#219653", "Increasing SWE"

    if value < -0.05:
        return "#D9534F", "Decreasing SWE"

    return "#64748B", "Little change"


def display_number(value, suffix=""):

    if pd.isna(value):
        return "Unavailable"

    return f"{value:+.2f}{suffix}"



# BEGIN STATION HISTORY CHARTS

def build_swe_history_chart(station_id):

    history = history_by_station.get(str(station_id))

    if history is None or history.empty:
        return "<p>No historical SWE data available.</p>"

    h = history[
        ["Observation_Time", "SWE_analysis"]
    ].copy()

    h["Observation_Time"] = pd.to_datetime(
        h["Observation_Time"], errors="coerce"
    )

    h["SWE_analysis"] = pd.to_numeric(
        h["SWE_analysis"], errors="coerce"
    )

    h = h.dropna(subset=["Observation_Time"])
    h = h.sort_values("Observation_Time")

    if h.empty:
        return "<p>No historical SWE data available.</p>"

    # End the chart at the last valid SWE observation,
    # not at an empty future hourly record.
    valid_times = h.loc[
        h["SWE_analysis"].notna(),
        "Observation_Time"
    ]

    if valid_times.empty:
        return "<p>No valid historical SWE readings.</p>"

    end_time = valid_times.max()
    start_time = end_time - pd.Timedelta(days=14)

    h = h[
        (h["Observation_Time"] >= start_time)
        & (h["Observation_Time"] <= end_time)
    ]

    valid = h["SWE_analysis"].dropna()

    if valid.empty:
        return "<p>No valid historical SWE readings.</p>"

    maximum = max(float(valid.max()), 1.0)

    points = []
    previous_time = None

    for _, observation in h.iterrows():

        t = observation["Observation_Time"]
        value = observation["SWE_analysis"]

        if pd.isna(value):
            previous_time = None
            continue

        fraction = (
            (t - start_time).total_seconds()
            / (14 * 24 * 3600)
        )

        x = 35 + fraction * 250
        y = 90 - (float(value) / maximum) * 75

        command = (
            "M" if previous_time is None
            or t - previous_time > pd.Timedelta(hours=3)
            else "L"
        )

        points.append(f"{command}{x:.1f},{y:.1f}")
        previous_time = t

    path = " ".join(points)

    return f"""
    <div style="margin-top:10px;">
        <b>14-Day SWE History</b>

        <svg width="300" height="120"
             viewBox="0 0 300 120">

            <line x1="35" y1="15" x2="35" y2="90"
                  stroke="#888"/>

            <line x1="35" y1="90" x2="285" y2="90"
                  stroke="#888"/>

            <path d="{path}"
                  fill="none"
                  stroke="#2563EB"
                  stroke-width="2"/>

            <text x="2" y="17" font-size="10">
                {maximum:.1f} in
            </text>

            <text x="20" y="90" font-size="10">0</text>

            <text x="35" y="108" font-size="10">
                {start_time:%b %d}
            </text>

            <text x="285" y="108"
                  text-anchor="end" font-size="10">
                {end_time:%b %d}
            </text>
        </svg>

        <div style="font-size:10px;color:#666;">
            {len(valid)} valid hourly observations.
            Missing or invalid values excluded.
        </div>
    </div>
    """

# END STATION HISTORY CHARTS

mapped_rows = regional_export.dropna(
    subset=["Latitude", "Longitude"]
)

for _, station in mapped_rows.iterrows():

    station_name = escape(str(station["Station_Name"]))
    station_id = escape(str(station["Station_ID"]))
    region = escape(str(station["Hydrologic_Region"]))
    qc_status = escape(str(station["QC_Status"]))

    swe = station["SWE_Valid_in"]

    swe_label = (
        f"{swe:.2f} in"
        if pd.notna(swe)
        else "Unavailable / QC excluded"
    )

    history_chart = build_swe_history_chart(station["Station_ID"])

    popup_html = f'''
    <div style="font-family:Arial;min-width:230px;">
        <b>{station_name}</b><br>
        Station: {station_id}<br>
        Region: {region}<br>
        Elevation: {station["Elevation_ft"]:.0f} ft
        <hr>
        <b>Current SWE:</b> {swe_label}<br>
        <b>24-hour change:</b>
        {display_number(station["Change_24h"], " in")}<br>
        <b>7-day change:</b>
        {display_number(station["Change_7d"], " in")}<br>
        <b>14-day change:</b>
        {display_number(station["Change_14d"], " in")}
        <hr>
        <b>QA/QC:</b> {qc_status}<br>
        <b>Observed:</b>
        {escape(str(station["Observation_Time"]))}
        <hr>
        {history_chart}
    </div>
    '''

    for view_name, field in view_settings:

        fill_color, category = classify_map_value(
            view_name, station
        )

        outline_color = (
            "#333333"
            if station["QC_Status"] == "OK"
            else "#F59E0B"
        )

        folium.CircleMarker(
            location=[
                float(station["Latitude"]),
                float(station["Longitude"])
            ],
            radius=6,
            color=outline_color,
            weight=2,
            fill=True,
            fill_color=fill_color,
            fill_opacity=0.85,
            tooltip=(
                f"{station_name} ({station_id}) | {category}"
            ),
            popup=folium.Popup(
                popup_html,
                max_width=350
            )
        ).add_to(map_layers[view_name])


folium.LayerControl(
    position="topright",
    collapsed=False
).add_to(enhanced_map)

# Compact explanatory panel
map_title = '''
<div style="
    position:fixed;
    top:12px;
    left:50px;
    z-index:9999;
    background:white;
    padding:12px;
    border:1px solid #ccc;
    border-radius:6px;
    font-family:Arial;
    font-size:13px;
    box-shadow:0 2px 8px #0002;
">
    <b>California Snowpack Explorer</b><br>
    <span style="font-size:11px;">
        CDEC Snow-Water Equivalent
    </span>
    <hr>
    <b>Current SWE:</b><br>
    <span style="color:#64748B;">●</span> 0 in<br>
    <span style="color:#7DD3FC;">●</span> Under 1 in<br>
    <span style="color:#2563EB;">●</span> 1–5 in<br>
    <span style="color:#1E3A8A;">●</span> 5+ in<br>
    <br>
    <b>Trend views:</b><br>
    <span style="color:#219653;">●</span> Increasing<br>
    <span style="color:#D9534F;">●</span> Decreasing<br>
    <span style="color:#64748B;">●</span> Little change<br>
    <span style="color:#D1D5DB;">●</span> Unavailable<br>
    <br>
    <span style="font-size:11px;">
        
<b>Data Quality:</b><br>
<span style="color:#219653;">●</span> Valid observation<br>
<span style="color:#F59E0B;">●</span> Negative SWE<br>
<span style="color:#8B5CF6;">●</span> Delayed observation<br>
<br>
<span style="display:inline-block;width:11px;height:11px;
border:2px solid #F59E0B;border-radius:50%;
vertical-align:middle;"></span>
Orange outline = QC flag.<br>

        Select a view in the upper-right.
    </span>
</div>
'''

enhanced_map.get_root().html.add_child(
    folium.Element(map_title)
)

# Replace the previous standalone HTML map
enhanced_map_path = os.path.join(
    OUTPUT_DIR,
    "california_snow_sensor_map.html"
)


# BEGIN STATION SEARCH

from folium.plugins import Search

search_features = []

for _, station in mapped_rows.iterrows():
    search_features.append({
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [
                float(station["Longitude"]),
                float(station["Latitude"])
            ]
        },
        "properties": {
            "Search_Label": (
                f'{station["Station_Name"]} '
                f'({station["Station_ID"]})'
            )
        }
    })

search_index = folium.GeoJson(
    {
        "type": "FeatureCollection",
        "features": search_features
    },
    name="Station Search Index",
    control=False,
    marker=folium.Marker(
        icon=folium.DivIcon(
            html="",
            icon_size=(0, 0)
        )
    )
).add_to(enhanced_map)

Search(
    layer=search_index,
    search_label="Search_Label",
    geom_type="Point",
    placeholder="Search station name or ID",
    collapsed=False,
    position="topright",
    search_zoom=9
).add_to(enhanced_map)

print("Station search indexed:", len(search_features))

# END STATION SEARCH


# BEGIN AUTO MAP EXTENT

enhanced_map.fit_bounds([
    [
        float(mapped_rows["Latitude"].min()) - 0.3,
        float(mapped_rows["Longitude"].min()) - 0.3
    ],
    [
        float(mapped_rows["Latitude"].max()) + 0.3,
        float(mapped_rows["Longitude"].max()) + 0.3
    ]
])

# END AUTO MAP EXTENT

enhanced_map.save(enhanced_map_path)

print("ENHANCED MAP COMPLETE")
print("---------------------")
print("Mapped stations:", len(mapped_rows))
print("Selectable views:", len(map_layers))
print("Basemap: Esri World Topographic Map")
print("Saved:", enhanced_map_path)

# END ENHANCED INTERACTIVE MAP



# FINISHED

# --------------------------------------------------



print(

    "Interactive map exported."

)



print()

print(

    "California Snow Sensor Monitor complete."

)

print(

    f"Outputs saved to: {OUTPUT_DIR}"

)