from pathlib import Path
import pandas as pd

project = Path(__file__).resolve().parent.parent
outputs = project / "outputs"

current = pd.read_csv(
    outputs / "snowpack_stations_current.csv"
)

history = pd.read_csv(
    outputs / "swe_history_15d.csv"
)

html = (
    outputs / "california_snow_sensor_map.html"
).read_text(encoding="utf-8")

results = {}

# Test 1: Station IDs must be unique
results["Unique station IDs"] = (
    current["Station_ID"].is_unique
)

# Test 2: Stations with coordinates
mapped = current.dropna(
    subset=["Latitude", "Longitude"]
)

results["Mapped stations exist"] = len(mapped) > 0

# Test 3: No invalid stations with trends
trend_cols = [
    "Change_24h",
    "Change_7d",
    "Change_14d"
]

flagged = current[
    current["QC_Status"] != "OK"
]

results["Flagged stations have no trends"] = (
    not flagged[trend_cols].notna().any().any()
)

# Test 4: No negative cleaned SWE values
cleaned = pd.to_numeric(
    current["SWE_Valid_in"],
    errors="coerce"
)

results["No negative cleaned SWE"] = (
    (cleaned.dropna() >= 0).all()
)

# Test 5: No negative valid historical SWE
valid_history = history[
    history["History_QC"] == "OK"
]

results["Valid history is nonnegative"] = (
    valid_history["SWE_analysis"].notna().all()
    and (valid_history["SWE_analysis"] >= 0).all()
)

# Test 6: No valid historical records after
# the latest current observation, comparing
# timestamps as recorded
current_times = pd.to_datetime(
    current["Observation_Time"],
    errors="coerce"
)

history_times = pd.to_datetime(
    history["Observation_Time"],
    errors="coerce"
)

latest_current = current_times.max()

future_valid = history[
    (history_times > latest_current)
    & (history["History_QC"] == "OK")
    & history["SWE_analysis"].notna()
]

results["No valid future-relative readings"] = (
    len(future_valid) == 0
)

# Test 7: Map contains five markers per station
expected_markers = len(mapped) * 5
actual_markers = html.count("L.circleMarker(")

results["Map marker count"] = (
    actual_markers == expected_markers
)

# Test 8: Search exists
results["Station search"] = (
    "Search_Label" in html
)

# Test 9: Historical charts exist
results["Historical charts"] = (
    "14-Day SWE History" in html
)

# Test 10: All five views exist
views = [
    "Current SWE",
    "24-Hour SWE Change",
    "7-Day SWE Change",
    "14-Day SWE Change",
    "Data Quality"
]

results["Five map views"] = all(
    view in html for view in views
)

# Test 11: Independent trend comparisons
current["Station_ID"] = (
    current["Station_ID"].astype(str).str.strip().str.upper()
)

history["STATION_ID"] = (
    history["STATION_ID"].astype(str).str.strip().str.upper()
)

current["Observation_Time"] = current_times
history["Observation_Time"] = history_times

valid = history[
    (history["History_QC"] == "OK")
    & history["SWE_analysis"].notna()
].sort_values("Observation_Time")

groups = {
    sid: group
    for sid, group in valid.groupby("STATION_ID")
}

periods = {
    "Change_24h": pd.Timedelta(hours=24),
    "Change_7d": pd.Timedelta(days=7),
    "Change_14d": pd.Timedelta(days=14)
}

compared = 0
mismatches = 0
unverifiable = 0

for _, station in current.iterrows():

    if station["QC_Status"] != "OK":
        continue

    sid = station["Station_ID"]
    station_history = groups.get(sid)

    if station_history is None:
        unverifiable += int(
            station[list(periods)].notna().sum()
        )
        continue

    for field, offset in periods.items():

        exported = station[field]

        if pd.isna(exported):
            continue

        target = station["Observation_Time"] - offset

        candidates = station_history[
            (station_history["Observation_Time"] <= target)
            & (
                station_history["Observation_Time"]
                >= target - pd.Timedelta(hours=2)
            )
        ]

        if candidates.empty:
            unverifiable += 1
            continue

        historical_swe = candidates.iloc[-1]["SWE_analysis"]

        calculated = (
            station["SWE_Valid_in"] - historical_swe
        )

        compared += 1

        if abs(float(exported) - float(calculated)) > 0.011:
            mismatches += 1

results["Historical trend calculations"] = (
    compared > 0
    and mismatches == 0
    and unverifiable == 0
)

# Display results
print("=" * 50)
print("CALIFORNIA SNOWPACK EXPLORER - AUTOMATED TESTS")
print("=" * 50)

for name, passed in results.items():
    print(
        f"{name}:",
        "PASS" if passed else "FAIL"
    )

passed_count = sum(results.values())
total = len(results)

print("\n" + "-" * 50)
print(f"TESTS PASSED: {passed_count}/{total}")
print("Trend comparisons:", compared)
print("Trend mismatches:", mismatches)
print("Unverifiable exported trends:", unverifiable)
print("Mapped stations:", len(mapped))
print("Map markers:", actual_markers)

if passed_count == total:
    print("\nALL TESTS PASSED")
else:
    print("\nSOME TESTS REQUIRE INVESTIGATION")
    raise SystemExit(1)
