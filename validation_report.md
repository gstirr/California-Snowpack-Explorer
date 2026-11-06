# California Snowpack Explorer
## Validation Report

Generated: 2026-11-06 13:06

### Project Overview

The California Snowpack Explorer retrieves California
Data Exchange Center (CDEC) snow-water equivalent (SWE)
observations, applies quality-control checks, calculates
historical changes, and exports GIS-ready datasets.

### Dataset Summary

| Metric | Value |
|---|---:|
| Current stations | 123 |
| Mapped stations | 120 |
| Historical records | 46585 |
| Valid historical records | 37519 |
| QA/QC flagged stations | 22 |
| 24-hour SWE trends | 100 |
| 7-day SWE trends | 93 |
| 14-day SWE trends | 88 |

### Automated Validation

| Check | Result |
|---|---|
| Python syntax | PASS |
| Unique station IDs | PASS |
| No flagged stations with trends | PASS |
| No valid future-relative historical records | PASS |
| Five map views have expected marker count | PASS |
| Historical charts included | PASS |
| Station search included | PASS |

### Independent Trend Validation

A separate notebook audit independently recalculated
SWE changes using historical observations and compared
the results with the exported trend fields.

Results from the November 6, 2026 audit:

- 24-hour changes: 100 of 100 matched
- 7-day changes: 93 of 93 matched
- 14-day changes: 88 of 88 matched
- Total: 281 of 281 matched within 0.011 inches

These results document the earlier audit and are not
independently recalculated by this report-generation cell.

### Data Quality Rules

- Negative SWE readings are flagged and excluded from
  valid SWE calculations.
- Stations missing coordinates are excluded from
  spatial point exports.
- QC-flagged stations do not receive calculated trends.
- Missing or invalid historical readings are excluded
  from historical calculations.
- Historical comparisons use station-specific timestamps.

### Outputs

- Current station CSV
- Station GeoJSON
- Historical SWE CSV
- Hydrologic region summary
- Interactive HTML map with five selectable views
- Station search and historical SWE charts

### Remaining Verification

CDEC source timestamp conventions and daylight-saving
time handling require independent verification.

Automated checks verify internal consistency, but do
not establish that all source observations are correct.

### Technical Stack

Python, pandas, GeoPandas, Folium, CDEC data services,
ArcGIS-compatible CSV and GeoJSON exports.
