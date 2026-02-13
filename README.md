Trash Dashboard

This repo contains a Streamlit app that reads a trash survey Excel workbook and produces:
- dashboards and figures
- a map view (when coordinates exist)
- a data quality review page
- an Add Entry form for raw master workbooks
- a cleaning step that writes a cleaned workbook (Clean_Long, Events_clean, QC_Report, Needs_Fixes)

Privacy
Do not commit real field data to GitHub.
This repo creates a fake sample workbook at data/sample_trash.xlsx so the app can run without private files.

Quick start
1) Install Python 3.10+ (3.11 is fine)
2) Install packages:
   pip install -r requirements.txt
3) Run the app:
   streamlit run app.py

Using your real workbook (local only)
Set environment variables so your paths stay off the repo:
- TRASH_INPUT_XLSX (path to your raw master workbook)
- TRASH_OUTPUT_XLSX (path where the cleaned workbook should be written)
- TRASH_OVERRIDES_CSV (optional overrides file)
Then open the app and use the Cleaning page.

Cleaning
The Cleaning page runs:
  python -m scripts.clean_trash_db
That script reads TRASH_INPUT_XLSX and writes TRASH_OUTPUT_XLSX.

What to screenshot for your GitHub page
- Dashboard (filters + totals)
- Figures page (top items or monthly totals)
- Map page (on the fake sample data)
- Data Quality Review page
- Cleaning page output
