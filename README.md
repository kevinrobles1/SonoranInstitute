Sonoran Institute Trash Dashboard (Internship Project)

Overview
This repository contains a Streamlit dashboard and data pipeline I built during my Database Specialist internship with the Sonoran Institute (Santa Cruz River program). The project supports a long term trash monitoring effort by improving data quality, making analysis repeatable, and producing charts and maps used for reporting.

Because the underlying dataset includes sensitive operational details (locations, field notes, and internal records), real data is not included in this public repository. This repo is set up to run in a safe demo mode using a generated sample workbook that matches the same structure as the real system.

What this project does
1) Loads trash survey workbooks (raw or cleaned)
- Supports a raw “master” workbook format (wide table with grouped headers)
- Supports a cleaned format with standardized long tables used for analysis

2) Cleaning pipeline (repeatable)
- Converts raw wide tables into a long format table used for charts (Clean_Long)
- Produces event level views (Events_clean)
- Generates quality control outputs:
  - QC_Report (summary checks)
  - Needs_Fixes (events needing manual review or overrides)

3) Dashboard and analysis
- Filterable dashboard by date range, site, trash group, and item
- Time series totals (monthly)
- Top items and top groups
- Site comparisons
- Items per m2 (normalization by surveyed area)

4) Mapping
- Plots event locations (when coordinates are available)
- Uses OpenStreetMap basemap for quick exploration

5) Data entry workflow (optional)
- “Add Entry” form for appending new events to a raw master workbook
- If the master workbook is locked, writes to a staging file for later merge

Privacy and data handling
No real program data is committed to this repository.
The real workbook can include exact coordinates, site identifiers, and field notes. To protect partners and operations, all data used for demonstration is synthetic.

If you are a collaborator and need access to the real dataset or internal deployment details, contact me directly.

Tech stack
- Python
- Streamlit (UI)
- pandas, numpy (data processing)
- plotly (interactive charts)
- openpyxl (Excel I/O)

Repo structure (recommended)
- app.py                         Streamlit app entry point
- scripts/clean_trash_db.py       Cleaning pipeline (writes cleaned workbook outputs)
- scripts/make_sample_workbook.py Generates a demo workbook with the same schema
- data/                           Local only (ignored by git)
- requirements.txt                Python dependencies
- .gitignore                      Blocks committing real data or outputs

How to run (demo mode, no private data)
1) Create and activate a virtual environment (optional but recommended)
2) Install dependencies:
   pip install -r requirements.txt
3) Run the app:
   streamlit run app.py

On first run, the app will create a synthetic sample workbook in:
  data/sample_trash.xlsx
This allows the dashboard, figures, map, and QC views to run without any private files.

How to run with a real workbook (local only)
You can point the app at a local workbook without committing it by setting environment variables:

Windows PowerShell:
  $env:TRASH_INPUT_XLSX="C:\path\to\Trash database.xlsx"
  $env:TRASH_OUTPUT_XLSX="C:\path\to\Trash database_CLEANED.xlsx"
  $env:TRASH_OVERRIDES_CSV="C:\path\to\site_overrides.csv"

macOS/Linux:
  export TRASH_INPUT_XLSX="/path/to/Trash database.xlsx"
  export TRASH_OUTPUT_XLSX="/path/to/Trash database_CLEANED.xlsx"
  export TRASH_OVERRIDES_CSV="/path/to/site_overrides.csv"

Then run:
  streamlit run app.py

Cleaning workflow
The app includes a Cleaning page that runs the cleaning pipeline and rebuilds the cleaned workbook outputs. This is the intended refresh flow for analysis and reporting.

Screenshots (add these to raise portfolio quality)
Add images to a folder like docs/ and link them here:
- Dashboard (filters + KPIs)
- Figures (Top items, Totals over time)
- Map (sample points)
- Data Quality Review (QC_Report + computed checks)
- Needs Fixes (example of flagged events)

Example:
docs/dashboard.png
docs/figures.png
docs/map.png
docs/qc.png

Impact (fill in with your real results)
- Reduced manual cleaning time by [X] hours per reporting cycle
- Added automated QC checks to catch missing dates, duplicate event IDs, and bad coordinates
- Made reporting charts reproducible from a single cleaned long table
- Improved usability for program staff by providing a single dashboard for filtering and exports

About me
Kevin Robles
Email: robleslopezkevindanniel@gmail.com
LinkedIn: www.linkedin.com/in/kevin-robles1
