# Trash Dashboard (Streamlit)  
Interactive analytics, mapping, QA checks, and controlled data entry for the Sonoran Institute trash survey database.

This repository contains a production-style Streamlit application that supports two workflows:

1) **Analytics on a cleaned workbook** (recommended): fast dashboards and figures built from standardized long-format tables.  
2) **Fallback support for a raw master workbook**: parse the original wide “Data” sheet format and still produce the same figures.

The app is designed to reduce analysis errors from inconsistent Excel structure, missing fields, and mixed data types by:
- building “plot-safe” columns (dates, coordinates, labels) when missing
- standardizing counts into one numeric column used by charts
- surfacing known data quality problems and remaining “Needs Fixes” events
- optionally appending new entries to the master workbook (or staging when locked)

---

## Highlights (what a recruiter should notice)

- **Reliable dual-mode ingestion**  
  Automatically detects whether the loaded workbook is cleaned (`Clean_Long`, `Events_clean`) or raw (`Data` sheet) and routes to the correct parsing pipeline.

- **Schema stabilization for plotting**  
  Prevents common dashboard failures (KeyError, non-parsing dates, mixed coordinate types) by deriving:
  - `date_plot`
  - `lat_plot`, `lon_plot`
  - `site_label_plot`
  - `count_for_totals`

- **Data quality reporting built-in**  
  Shows workbook-generated QA (when present) and runs computed checks in-app (duplicates, parse failures, missing survey area, etc.).

- **Map visualization**  
  Interactive site map (Plotly) with event hover data when coordinates exist.

- **Controlled data entry for field updates**  
  Adds new events to the raw master workbook with correct header alignment, and automatically writes to a staging file when Excel locks the master.

- **One-click pipeline refresh**  
  Runs a separate cleaning script (`clean_trash_db.py`) so analysts can regenerate the cleaned workbook without leaving the UI.

---

## Demo (optional but recommended)

If you want this to look “portfolio-ready”, add a screenshot or short GIF of:
- Dashboard filters + monthly totals
- Top items figure
- Map page
- Needs Fixes / QC page

Place images in `docs/` and link them here:

```text
docs/
  dashboard.png
  map.png
  qc.png
