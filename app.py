import os
import re
import tempfile
from datetime import datetime, date

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from openpyxl import load_workbook

LOGO_URL = "https://sonoraninstitute.org/wp-content/themes/sonoran-institute-2016/assets/img/si_logo_2018.png"

st.set_page_config(page_title="Trash Dashboard", page_icon="🗑️", layout="wide")


# -----------------------------
# Helpers
# -----------------------------
def find_candidate_workbooks() -> list[str]:
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = []

    obvious = [
        os.path.join(base, "Trash database.xlsx"),
        os.path.join(base, "Data here", "Trash database.xlsx"),
    ]
    for p in obvious:
        if os.path.exists(p):
            candidates.append(p)

    for root in [base, os.path.join(base, "Data here")]:
        if os.path.isdir(root):
            for fn in os.listdir(root):
                if fn.lower().endswith(".xlsx"):
                    full = os.path.join(root, fn)
                    if full not in candidates:
                        candidates.append(full)

    return candidates


def get_mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0.0


def normalize_event_id(x):
    if pd.isna(x):
        return None
    s = str(x).strip()
    if s == "":
        return None
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def parse_date_val(val):
    if pd.isna(val):
        return pd.NaT
    if isinstance(val, (datetime, pd.Timestamp)):
        return pd.to_datetime(val)

    s = str(val).strip()
    if s == "":
        return pd.NaT

    if re.fullmatch(r"\d+(\.0+)?", s):
        s = s.split(".")[0]

    if len(s) == 6:
        return pd.to_datetime(s, format="%y%m%d", errors="coerce")
    if len(s) == 8:
        return pd.to_datetime(s, format="%Y%m%d", errors="coerce")

    return pd.to_datetime(s, errors="coerce")


def multi_to_group_item(col):
    # col is usually a tuple (top, sub) from a 2-row Excel header
    if not isinstance(col, tuple) or len(col) != 2:
        return "Ungrouped", str(col)

    top, sub = col
    top = "" if pd.isna(top) else str(top).strip()
    sub = "" if pd.isna(sub) else str(sub).strip()

    group = top if (top and not top.lower().startswith("unnamed")) else "Ungrouped"
    item = sub if (sub and not sub.lower().startswith("unnamed")) else top

    if item == "":
        item = "Unknown item"

    return group, item


def looks_like_timedelta_text(x) -> bool:
    if pd.isna(x):
        return False
    return ("day" in str(x)) or isinstance(x, pd.Timedelta)


@st.cache_data(show_spinner=False)
def load_workbook_data(workbook_path: str, workbook_mtime: float):
    # Returns: events_df, long_df, site_df, meta dict
    xls = pd.ExcelFile(workbook_path)
    meta = {"sheets": xls.sheet_names}

    if "Data" not in xls.sheet_names:
        raise ValueError("Workbook is missing a sheet named 'Data'.")

    # Data sheet (2-row header)
    df_raw = pd.read_excel(workbook_path, sheet_name="Data", header=[0, 1])

    # Identify the event columns from the second header row
    base_targets = {
        "event id": "event_id",
        "date": "date_raw",
        "surveyed m2": "surveyed_m2_raw",
        "surveyed m^2": "surveyed_m2_raw",
    }

    base_cols = {}
    for col in df_raw.columns:
        sub = str(col[1]).strip().lower()
        if sub in base_targets:
            base_cols[col] = base_targets[sub]

    df = df_raw.copy()
    df.columns = [base_cols.get(c, c) for c in df_raw.columns]

    required = {"event_id", "date_raw", "surveyed_m2_raw"}
    missing = sorted(list(required - set(df.columns)))
    if missing:
        raise ValueError(f"Data sheet is missing required column(s): {missing}")

    # Drop summary rows (blank event id)
    df = df[df["event_id"].notna()].copy()

    df["event_id"] = df["event_id"].apply(normalize_event_id)
    df["date"] = df["date_raw"].apply(parse_date_val)
    df["surveyed_m2"] = pd.to_numeric(df["surveyed_m2_raw"], errors="coerce")

    # Melt to long format (trash item counts)
    value_cols = [c for c in df.columns if isinstance(c, tuple)]
    long_df = df.melt(
        id_vars=["event_id", "date", "surveyed_m2"],
        value_vars=value_cols,
        var_name="col",
        value_name="count_raw",
    )

    group_item = long_df["col"].apply(multi_to_group_item)
    long_df["trash_group"] = group_item.apply(lambda x: x[0])
    long_df["trash_item"] = group_item.apply(lambda x: x[1])

    # Drop non-item columns that exist in this workbook
    drop_items = {"Complete?", "Total items", "Total items/m2"}
    long_df = long_df[~long_df["trash_item"].isin(drop_items)].copy()

    long_df["count"] = pd.to_numeric(long_df["count_raw"], errors="coerce")

    # Site sheet (optional but strongly recommended)
    site_df = None
    if "Site" in xls.sheet_names:
        site_df = pd.read_excel(workbook_path, sheet_name="Site")
        if "Event ID" in site_df.columns:
            site_df["event_id"] = site_df["Event ID"].apply(normalize_event_id)
        else:
            site_df["event_id"] = None

        if "Date" in site_df.columns:
            site_df["date_site"] = site_df["Date"].apply(parse_date_val)

        if "Site" not in site_df.columns:
            site_df["Site"] = None

    # Build event-level view
    events_df = df[["event_id", "date", "surveyed_m2"]].drop_duplicates().copy()

    if site_df is not None and "event_id" in site_df.columns:
        site_small = site_df[["event_id", "Site"]].drop_duplicates()
        events_df = events_df.merge(site_small, on="event_id", how="left")
        long_df = long_df.merge(site_small, on="event_id", how="left")
    else:
        events_df["Site"] = None
        long_df["Site"] = None

    return events_df, long_df, site_df, meta


def run_data_quality_checks(events_df: pd.DataFrame, long_df: pd.DataFrame, site_df: pd.DataFrame | None):
    issues = []

    # 1) Event ID missing
    missing_event_id = events_df["event_id"].isna().sum()
    if missing_event_id > 0:
        issues.append({
            "name": "Missing Event ID in Data sheet",
            "count": int(missing_event_id),
            "sample": events_df[events_df["event_id"].isna()].head(50)
        })

    # 2) Event ID duplicates in Data
    dupes = events_df["event_id"][events_df["event_id"].notna()].duplicated().sum()
    if dupes > 0:
        d = events_df[events_df["event_id"].duplicated(keep=False)].sort_values("event_id").head(100)
        issues.append({
            "name": "Duplicate Event ID in Data sheet",
            "count": int(dupes),
            "sample": d
        })

    # 3) Date parse failures
    date_bad = events_df["date"].isna().sum()
    if date_bad > 0:
        issues.append({
            "name": "Date values that did not parse in Data sheet",
            "count": int(date_bad),
            "sample": events_df[events_df["date"].isna()].head(50)
        })

    # 4) Surveyed area missing or not positive
    area_missing = events_df["surveyed_m2"].isna().sum()
    if area_missing > 0:
        issues.append({
            "name": "Missing surveyed m2 in Data sheet",
            "count": int(area_missing),
            "sample": events_df[events_df["surveyed_m2"].isna()].head(50)
        })

    area_nonpos = (events_df["surveyed_m2"].notna() & (events_df["surveyed_m2"] <= 0)).sum()
    if area_nonpos > 0:
        issues.append({
            "name": "Surveyed m2 is 0 or negative in Data sheet",
            "count": int(area_nonpos),
            "sample": events_df[events_df["surveyed_m2"].notna() & (events_df["surveyed_m2"] <= 0)].head(50)
        })

    # 5) Counts negative
    neg_counts = (long_df["count"].notna() & (long_df["count"] < 0)).sum()
    if neg_counts > 0:
        issues.append({
            "name": "Negative trash counts (should be 0 or higher)",
            "count": int(neg_counts),
            "sample": long_df[long_df["count"].notna() & (long_df["count"] < 0)].head(100)
        })

    # 6) Counts that are not whole numbers
    nonint = (long_df["count"].notna() & ((long_df["count"] % 1) != 0)).sum()
    if nonint > 0:
        issues.append({
            "name": "Trash counts that are not whole numbers",
            "count": int(nonint),
            "sample": long_df[long_df["count"].notna() & ((long_df["count"] % 1) != 0)].head(100)
        })

    # 7) Site coverage checks (if Site sheet exists)
    if site_df is not None:
        if "event_id" in site_df.columns:
            data_ids = set(events_df["event_id"].dropna().tolist())
            site_ids = set(site_df["event_id"].dropna().tolist())

            missing_in_site = sorted(list(data_ids - site_ids))
            missing_in_data = sorted(list(site_ids - data_ids))

            if missing_in_site:
                issues.append({
                    "name": "Event IDs in Data sheet but missing in Site sheet",
                    "count": int(len(missing_in_site)),
                    "sample": pd.DataFrame({"event_id": missing_in_site[:100]})
                })

            if missing_in_data:
                issues.append({
                    "name": "Event IDs in Site sheet but missing in Data sheet",
                    "count": int(len(missing_in_data)),
                    "sample": pd.DataFrame({"event_id": missing_in_data[:100]})
                })

        if "Site" in site_df.columns:
            site_blank = site_df["Site"].isna().sum()
            if site_blank > 0:
                issues.append({
                    "name": "Missing Site values in Site sheet",
                    "count": int(site_blank),
                    "sample": site_df[site_df["Site"].isna()].head(100)
                })

        # Northing/Westing sometimes get read as time-like values, flag them
        for col in ["Northing", "Westing"]:
            if col in site_df.columns:
                bad = site_df[col].apply(looks_like_timedelta_text).sum()
                if bad > 0:
                    issues.append({
                        "name": f"{col} values that look like time-like values",
                        "count": int(bad),
                        "sample": site_df[site_df[col].apply(looks_like_timedelta_text)][["event_id", col]].head(100)
                    })

    return issues


def yymmdd_int(d: date) -> int:
    return int(d.strftime("%y%m%d"))


def try_append_to_master(workbook_path: str, event_id: str, d: date, surveyed_m2: float, site_name: str | None,
                         counts_rows: pd.DataFrame):
    """
    Attempts to append to Data + Site sheets in the master workbook.
    If the file is locked, this will raise an exception.
    """
    wb = load_workbook(workbook_path)
    if "Data" not in wb.sheetnames:
        raise ValueError("Master workbook is missing a sheet named 'Data'.")

    ws_data = wb["Data"]

    # Read 2-row header from Data sheet (row 1 and row 2)
    max_col = ws_data.max_column
    header_top = [ws_data.cell(row=1, column=c).value for c in range(1, max_col + 1)]
    header_sub = [ws_data.cell(row=2, column=c).value for c in range(1, max_col + 1)]

    # Build mapping col_index -> (group, item)
    col_keys = []
    for top, sub in zip(header_top, header_sub):
        top_s = "" if top is None else str(top).strip()
        sub_s = "" if sub is None else str(sub).strip()

        # Event fields are usually in the second row
        if sub_s.lower() in ["event id", "date", "surveyed m2", "surveyed m^2"]:
            col_keys.append(("__EVENT__", sub_s))
        else:
            g = top_s if (top_s and not top_s.lower().startswith("unnamed")) else "Ungrouped"
            i = sub_s if (sub_s and not sub_s.lower().startswith("unnamed")) else top_s
            col_keys.append((g, i))

    # Prep lookup from user rows
    counts_rows = counts_rows.copy()
    counts_rows["trash_group"] = counts_rows["trash_group"].astype(str)
    counts_rows["trash_item"] = counts_rows["trash_item"].astype(str)
    counts_rows["count"] = pd.to_numeric(counts_rows["count"], errors="coerce").fillna(0)

    user_map = {}
    for _, r in counts_rows.iterrows():
        g = r["trash_group"].strip()
        i = r["trash_item"].strip()
        if g == "" or i == "":
            continue
        user_map[(g, i)] = float(r["count"])

    # Compute total items (sum of provided counts)
    total_items = float(np.sum(list(user_map.values()))) if user_map else 0.0

    # Build row values aligned to columns
    row_values = []
    for (g, i) in col_keys:
        if g == "__EVENT__":
            if i.lower() == "event id":
                row_values.append(event_id)
            elif i.lower() == "date":
                row_values.append(yymmdd_int(d))
            elif i.lower() in ["surveyed m2", "surveyed m^2"]:
                row_values.append(float(surveyed_m2) if surveyed_m2 is not None else None)
            else:
                row_values.append(None)
        else:
            # Fill count if provided, else blank
            # Also try to fill "Total items" and "Total items/m2" if present
            if str(i).strip() == "Total items":
                row_values.append(total_items)
            elif str(i).strip() == "Total items/m2":
                if surveyed_m2 and surveyed_m2 > 0:
                    row_values.append(total_items / float(surveyed_m2))
                else:
                    row_values.append(None)
            else:
                row_values.append(user_map.get((g, i), None))

    ws_data.append(row_values)

    # Append to Site sheet if it exists
    if "Site" in wb.sheetnames:
        ws_site = wb["Site"]
        # Find header row (assume row 1)
        site_headers = {str(ws_site.cell(row=1, column=c).value).strip(): c for c in range(1, ws_site.max_column + 1)}
        new_row = [None] * ws_site.max_column

        if "Event ID" in site_headers:
            new_row[site_headers["Event ID"] - 1] = event_id
        if "Date" in site_headers:
            new_row[site_headers["Date"] - 1] = yymmdd_int(d)
        if "Site" in site_headers:
            new_row[site_headers["Site"] - 1] = site_name

        ws_site.append(new_row)

    wb.save(workbook_path)


def write_to_staging(staging_path: str, event_row: dict, counts_rows: pd.DataFrame):
    # Two sheets: one for event info, one for counts in long form
    with pd.ExcelWriter(staging_path, engine="openpyxl", mode="a" if os.path.exists(staging_path) else "w") as writer:
        ev = pd.DataFrame([event_row])
        ev.to_excel(writer, sheet_name="New_Events", index=False,
                    header=not ("New_Events" in writer.book.sheetnames))

        cr = counts_rows.copy()
        cr["event_id"] = event_row["event_id"]
        cr.to_excel(writer, sheet_name="New_Counts", index=False,
                    header=not ("New_Counts" in writer.book.sheetnames))


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.image(LOGO_URL, use_container_width=True)
st.sidebar.markdown("### Trash Dashboard")

candidates = find_candidate_workbooks()
uploaded = st.sidebar.file_uploader("Optional: open a different Excel file", type=["xlsx"])
manual_path = st.sidebar.text_input("Or paste a full file path", value="")

workbook_path = None
temp_uploaded_path = None

if uploaded is not None:
    # Save upload to a temp file so openpyxl can read it
    fd, temp_path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    with open(temp_path, "wb") as f:
        f.write(uploaded.getbuffer())
    workbook_path = temp_path
    temp_uploaded_path = temp_path
elif manual_path.strip() != "":
    workbook_path = manual_path.strip()
elif candidates:
    workbook_path = st.sidebar.selectbox("Workbook", candidates, index=0)
else:
    workbook_path = None

page = st.sidebar.radio(
    "Pages",
    ["Dashboard", "Figures", "Add Entry", "Data Quality Review", "Export"],
    index=0
)

# -----------------------------
# Main: Load data
# -----------------------------
if not workbook_path or not os.path.exists(workbook_path):
    st.error("No workbook found. Put 'Trash database.xlsx' in the same folder as app.py (or inside a folder named 'Data here').")
    st.stop()

mtime = get_mtime(workbook_path)

try:
    events_df, long_df, site_df, meta = load_workbook_data(workbook_path, mtime)
except Exception as e:
    st.error(f"Could not load workbook: {e}")
    st.stop()


# -----------------------------
# Pages
# -----------------------------
if page == "Dashboard":
    st.title("Trash Dashboard")

    # Filters
    c1, c2, c3, c4 = st.columns(4)

    min_date = events_df["date"].min()
    max_date = events_df["date"].max()
    if pd.isna(min_date) or pd.isna(max_date):
        min_date = None
        max_date = None

    with c1:
        if min_date and max_date:
            date_range = st.date_input("Date range", value=(min_date.date(), max_date.date()))
        else:
            date_range = st.date_input("Date range")

    with c2:
        sites = sorted([s for s in long_df["Site"].dropna().unique().tolist()])
        selected_sites = st.multiselect("Site", options=sites, default=sites)

    with c3:
        groups = sorted(long_df["trash_group"].dropna().unique().tolist())
        selected_groups = st.multiselect("Trash group", options=groups, default=groups)

    with c4:
        items = sorted(long_df["trash_item"].dropna().unique().tolist())
        selected_items = st.multiselect("Trash item", options=items, default=[])

    f = long_df.copy()

    # Apply filters
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start_d, end_d = date_range
        f = f[f["date"].notna()]
        f = f[(f["date"].dt.date >= start_d) & (f["date"].dt.date <= end_d)]

    if selected_sites:
        f = f[f["Site"].isin(selected_sites)]

    if selected_groups:
        f = f[f["trash_group"].isin(selected_groups)]

    if selected_items:
        f = f[f["trash_item"].isin(selected_items)]

    # Summary tiles
    total_events = f["event_id"].nunique()
    total_items = f["count"].fillna(0).sum()

    a, b, c = st.columns(3)
    a.metric("Events", int(total_events))
    b.metric("Total items (sum of counts)", int(total_items))
    c.metric("Rows shown", int(len(f)))

    st.divider()

    # Plots
    left, right = st.columns(2)

    with left:
        st.subheader("Totals over time")
        ts = f.dropna(subset=["date"]).groupby(pd.Grouper(key="date", freq="M"))["count"].sum().reset_index()
        if len(ts) > 0:
            fig = px.line(ts, x="date", y="count")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No rows for this filter.")

    with right:
        st.subheader("Top items")
        top = f.groupby(["trash_item"])["count"].sum().sort_values(ascending=False).head(15).reset_index()
        if len(top) > 0:
            fig = px.bar(top, x="count", y="trash_item", orientation="h")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No rows for this filter.")

    st.subheader("Filtered table")
    st.dataframe(
        f[["event_id", "date", "Site", "trash_group", "trash_item", "count", "surveyed_m2"]].sort_values(["date", "event_id"]),
        use_container_width=True,
        height=420,
    )

elif page == "Figures":
    st.title("Figures")

    figure_type = st.selectbox(
        "Choose a figure",
        [
            "Totals over time",
            "Top items",
            "Top groups",
            "Site comparison (total items)",
            "Items per m2 (by site)",
        ],
        index=0,
    )

    df = long_df.copy()
    df["count"] = df["count"].fillna(0)

    if figure_type == "Totals over time":
        ts = df.dropna(subset=["date"]).groupby(pd.Grouper(key="date", freq="M"))["count"].sum().reset_index()
        fig = px.line(ts, x="date", y="count")
        st.plotly_chart(fig, use_container_width=True)

    elif figure_type == "Top items":
        top = df.groupby("trash_item")["count"].sum().sort_values(ascending=False).head(25).reset_index()
        fig = px.bar(top, x="count", y="trash_item", orientation="h")
        st.plotly_chart(fig, use_container_width=True)

    elif figure_type == "Top groups":
        top = df.groupby("trash_group")["count"].sum().sort_values(ascending=False).reset_index()
        fig = px.bar(top, x="count", y="trash_group", orientation="h")
        st.plotly_chart(fig, use_container_width=True)

    elif figure_type == "Site comparison (total items)":
        by_site = df.groupby("Site")["count"].sum().sort_values(ascending=False).reset_index()
        fig = px.bar(by_site, x="count", y="Site", orientation="h")
        st.plotly_chart(fig, use_container_width=True)

    elif figure_type == "Items per m2 (by site)":
        # event totals then divide by surveyed_m2 at event level, then average per site
        ev = df.groupby(["event_id", "Site", "surveyed_m2"], dropna=False)["count"].sum().reset_index()
        ev["items_per_m2"] = np.where(ev["surveyed_m2"] > 0, ev["count"] / ev["surveyed_m2"], np.nan)
        agg = ev.groupby("Site")["items_per_m2"].mean().sort_values(ascending=False).reset_index()
        fig = px.bar(agg, x="items_per_m2", y="Site", orientation="h")
        st.plotly_chart(fig, use_container_width=True)

elif page == "Data Quality Review":
    st.title("Data Quality Review")

    issues = run_data_quality_checks(events_df, long_df, site_df)

    st.write("These checks are computed from the workbook that is loaded right now.")

    if not issues:
        st.success("No issues found by the checks that are turned on.")
    else:
        st.warning(f"Issues found: {len(issues)}")

        for issue in issues:
            st.subheader(f"{issue['name']} (count: {issue['count']})")
            st.dataframe(issue["sample"], use_container_width=True, height=260)

elif page == "Add Entry":
    st.title("Add Entry")

    st.write("This page tries to append to the master workbook. If the file is locked, it writes to a staging file.")

    # Build choices from existing data
    group_choices = sorted(long_df["trash_group"].dropna().unique().tolist())
    item_choices = sorted(long_df["trash_item"].dropna().unique().tolist())

    with st.form("add_entry_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            event_id = st.text_input("Event ID")
        with c2:
            entry_date = st.date_input("Date")
        with c3:
            surveyed_m2 = st.number_input("Surveyed m2", min_value=0.0, value=0.0, step=0.5)

        site_name = st.text_input("Site (optional)")

        st.markdown("#### Trash counts")
        starter = pd.DataFrame(
            [{"trash_group": (group_choices[0] if group_choices else "Ungrouped"),
              "trash_item": (item_choices[0] if item_choices else ""),
              "count": 0}]
        )

        counts_rows = st.data_editor(
            starter,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "trash_group": st.column_config.SelectboxColumn("Trash group", options=group_choices),
                "trash_item": st.column_config.SelectboxColumn("Trash item", options=item_choices),
                "count": st.column_config.NumberColumn("Count", min_value=0),
            },
        )

        block_if_duplicate = st.checkbox("Block duplicate Event ID", value=True)
        submit = st.form_submit_button("Save")

    if submit:
        event_id_norm = normalize_event_id(event_id)
        if not event_id_norm:
            st.error("Event ID is required.")
            st.stop()

        # Duplicate check against current loaded data
        already = set(events_df["event_id"].dropna().tolist())
        if block_if_duplicate and event_id_norm in already:
            st.error("That Event ID already exists in the Data sheet.")
            st.stop()

        # Basic field checks (not guesses, just validity)
        if surveyed_m2 is None or surveyed_m2 <= 0:
            st.warning("Surveyed m2 is 0 or less. That will break items per m2 math.")

        # Clean counts table
        counts_df = pd.DataFrame(counts_rows)
        if len(counts_df) == 0:
            counts_df = pd.DataFrame(columns=["trash_group", "trash_item", "count"])

        counts_df["count"] = pd.to_numeric(counts_df["count"], errors="coerce").fillna(0)
        counts_df = counts_df[(counts_df["trash_group"].notna()) & (counts_df["trash_item"].notna())]

        # Write
        try:
            try_append_to_master(
                workbook_path=workbook_path,
                event_id=event_id_norm,
                d=entry_date,
                surveyed_m2=float(surveyed_m2),
                site_name=site_name if site_name.strip() != "" else None,
                counts_rows=counts_df,
            )
            st.success("Saved to the master workbook.")
            st.cache_data.clear()
        except Exception as e:
            staging_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "staging_new_entries.xlsx")
            event_row = {
                "event_id": event_id_norm,
                "date": entry_date.isoformat(),
                "surveyed_m2": float(surveyed_m2),
                "Site": site_name if site_name.strip() != "" else None,
                "error": str(e),
            }
            try:
                write_to_staging(staging_path, event_row, counts_df)
                st.error("Could not write to the master workbook (it may be locked).")
                st.info(f"Saved to staging file instead: {staging_path}")
            except Exception as e2:
                st.error("Could not write to the master workbook, and staging write also failed.")
                st.write(str(e))
                st.write(str(e2))

elif page == "Export":
    st.title("Export")

    st.write("Download the filtered long-format table as CSV (what you are charting).")

    df = long_df.copy()
    out = df[["event_id", "date", "Site", "trash_group", "trash_item", "count", "surveyed_m2"]].copy()
    csv = out.to_csv(index=False).encode("utf-8")

    st.download_button("Download CSV", data=csv, file_name="trash_export.csv", mime="text/csv")

# Clean up temp uploaded file if needed (Streamlit reruns a lot, so keep it simple)
if temp_uploaded_path and os.path.exists(temp_uploaded_path):
    pass