# Trash Dashboard (Streamlit)

Interactive analytics, mapping, QA checks, and controlled data entry for the Sonoran Institute trash survey database.

This repo contains a Streamlit app built for two workflows:

1. Cleaned workbook analytics (recommended): fast dashboards and figures from standardized long-format tables.
2. Raw master workbook support (fallback): parses the original wide “Data” sheet and produces the same figures.

The goal is to reduce analysis mistakes caused by inconsistent Excel structure, missing fields, and mixed data types by:
- creating plot-safe columns (dates, coordinates, labels) when missing
- standardizing counts into one numeric column used by charts
- surfacing known QA problems and remaining “Needs Fixes” events
- optionally appending new entries to the master workbook (or writing to staging when the file is locked)

## Highlights

Dual-mode ingestion  
Automatically detects whether the workbook is cleaned (`Clean_Long`, `Events_clean`) or raw (`Data`) and routes to the correct parsing path.

Plot-ready schema stabilization  
Prevents common dashboard failures (KeyError, date parse failures, mixed coordinate formats) by deriving:
- `date_plot`
- `lat_plot`, `lon_plot`
- `site_label_plot`
- `count_for_totals`

Built-in data quality review  
Displays workbook QA sheets when present (`QC_Report`, `Needs_Fixes`) and runs computed checks in-app (duplicate IDs, missing survey area, parse failures, and more).

Map visualization  
Interactive Plotly map with hover details (event ID, date, total items) when coordinates exist.

Controlled data entry  
Adds new events to the raw master workbook with correct header alignment. If Excel locks the file, the app writes to a staging workbook instead.

One-click cleaning refresh  
Runs a separate pipeline script (`clean_trash_db.py`) so users can rebuild the cleaned output without leaving the UI.

## Demo (recommended)

Add a few screenshots or a short GIF. This makes the repo much easier to judge quickly.

Suggested files:
```text
docs/
  dashboard.png
  map.png
  qc.png
