from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any, Dict, List, Tuple

import numpy as np
import pandas as pd


def normalize_event_id(x: Any) -> Optional[str]:
    if pd.isna(x):
        return None
    s = str(x).strip()
    if s == "":
        return None
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def parse_date_val(val: Any) -> pd.Timestamp:
    if pd.isna(val):
        return pd.NaT
    if isinstance(val, (pd.Timestamp,)):
        return pd.to_datetime(val, errors="coerce")

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


def multi_to_group_item(col: Any) -> Tuple[str, str]:
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


def pick_first_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = set(df.columns)
    for c in candidates:
        if c in cols:
            return c
    return None


@dataclass(frozen=True)
class CleanSettings:
    input_xlsx: str
    output_xlsx: str
    overrides_csv: str


def get_clean_settings() -> CleanSettings:
    base = Path(__file__).resolve().parent.parent

    def _env_or(default: str, key: str) -> str:
        v = os.getenv(key, "").strip()
        return v if v else default

    return CleanSettings(
        input_xlsx=_env_or(str(base / "data" / "sample_trash.xlsx"), "TRASH_INPUT_XLSX"),
        output_xlsx=_env_or(str(base / "data" / "sample_trash_CLEANED.xlsx"), "TRASH_OUTPUT_XLSX"),
        overrides_csv=_env_or(str(base / "data" / "site_overrides.csv"), "TRASH_OVERRIDES_CSV"),
    )


def load_raw_long(input_xlsx: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    xls = pd.ExcelFile(input_xlsx)
    if "Data" not in xls.sheet_names:
        raise ValueError("Input workbook is missing a sheet named 'Data'")

    df_raw = pd.read_excel(input_xlsx, sheet_name="Data", header=[0, 1])

    base_targets = {
        "event id": "event_id",
        "date": "date_raw",
        "surveyed m2": "surveyed_m2_raw",
        "surveyed m^2": "surveyed_m2_raw",
    }

    base_cols: Dict[Any, str] = {}
    for col in df_raw.columns:
        sub = str(col[1]).strip().lower()
        if sub in base_targets:
            base_cols[col] = base_targets[sub]

    df = df_raw.copy()
    df.columns = [base_cols.get(c, c) for c in df_raw.columns]

    required = {"event_id", "date_raw", "surveyed_m2_raw"}
    missing = sorted(list(required - set(df.columns)))
    if missing:
        raise ValueError(f"Data sheet missing required columns: {missing}")

    df = df[df["event_id"].notna()].copy()
    df["event_id"] = df["event_id"].apply(normalize_event_id)
    df["date_plot"] = df["date_raw"].apply(parse_date_val)
    df["surveyed_m2"] = pd.to_numeric(df["surveyed_m2_raw"], errors="coerce")

    value_cols = [c for c in df.columns if isinstance(c, tuple)]
    long_df = df.melt(
        id_vars=["event_id", "date_plot", "surveyed_m2"],
        value_vars=value_cols,
        var_name="col",
        value_name="count_raw",
    )

    group_item = long_df["col"].apply(multi_to_group_item)
    long_df["trash_group"] = group_item.apply(lambda x: x[0])
    long_df["trash_item"] = group_item.apply(lambda x: x[1])

    drop_items = {"Complete?", "Total items", "Total items/m2"}
    long_df = long_df[~long_df["trash_item"].isin(drop_items)].copy()

    long_df["count_for_totals"] = pd.to_numeric(long_df["count_raw"], errors="coerce").fillna(0).astype(float)

    events_df = df[["event_id", "date_plot", "surveyed_m2"]].drop_duplicates().copy()
    return events_df, long_df


def load_site(input_xlsx: str) -> Optional[pd.DataFrame]:
    xls = pd.ExcelFile(input_xlsx)
    if "Site" not in xls.sheet_names:
        return None
    site = pd.read_excel(input_xlsx, sheet_name="Site")

    if "Event ID" in site.columns:
        site["event_id"] = site["Event ID"].apply(normalize_event_id)
    else:
        site["event_id"] = None

    if "Date" in site.columns:
        site["date_site"] = site["Date"].apply(parse_date_val)

    label_src = pick_first_col(site, ["Site", "site_label", "location_description"])
    site["site_label_plot"] = site[label_src].fillna("").astype(str).str.strip() if label_src else ""

    lat_src = pick_first_col(site, ["Latitude", "Lat", "lat", "lat_raw"])
    lon_src = pick_first_col(site, ["Longitude", "Lon", "Long", "lon", "lon_raw"])

    site["lat_plot"] = pd.to_numeric(site[lat_src], errors="coerce") if lat_src else np.nan
    site["lon_plot"] = pd.to_numeric(site[lon_src], errors="coerce") if lon_src else np.nan

    return site


def apply_overrides(site_df: Optional[pd.DataFrame], overrides_csv: str) -> Optional[pd.DataFrame]:
    if site_df is None:
        return None
    if not overrides_csv or not os.path.exists(overrides_csv):
        return site_df

    ov = pd.read_csv(overrides_csv)
    if "event_id" not in ov.columns:
        return site_df

    out = site_df.copy()
    ov["event_id"] = ov["event_id"].apply(normalize_event_id)

    if "site_label_override" in ov.columns:
        out = out.merge(ov[["event_id", "site_label_override"]], on="event_id", how="left")
        mask = out["site_label_override"].notna() & (out["site_label_override"].astype(str).str.strip() != "")
        out.loc[mask, "site_label_plot"] = out.loc[mask, "site_label_override"].astype(str).str.strip()
        out = out.drop(columns=["site_label_override"])

    for col_pair in [("lat_override", "lat_plot"), ("lon_override", "lon_plot")]:
        src, dst = col_pair
        if src in ov.columns:
            out = out.merge(ov[["event_id", src]], on="event_id", how="left")
            val = pd.to_numeric(out[src], errors="coerce")
            mask = val.notna()
            out.loc[mask, dst] = val[mask]
            out = out.drop(columns=[src])

    return out


def build_qc_report(events_df: pd.DataFrame, long_df: pd.DataFrame, site_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    rows = []
    rows.append(("events_total", int(events_df["event_id"].nunique())))
    rows.append(("rows_long_total", int(len(long_df))))
    rows.append(("dates_missing", int(events_df["date_plot"].isna().sum())))
    rows.append(("surveyed_m2_missing", int(events_df["surveyed_m2"].isna().sum())))
    rows.append(("surveyed_m2_nonpos", int((events_df["surveyed_m2"].notna() & (events_df["surveyed_m2"] <= 0)).sum())))

    if site_df is None:
        rows.append(("site_sheet_present", 0))
        rows.append(("coords_missing", -1))
    else:
        rows.append(("site_sheet_present", 1))
        rows.append(("coords_missing", int((site_df["lat_plot"].isna() | site_df["lon_plot"].isna()).sum())))

    return pd.DataFrame(rows, columns=["check", "value"])


def build_needs_fixes(events_df: pd.DataFrame, site_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    needs = []

    bad_date = events_df[events_df["date_plot"].isna()][["event_id"]].copy()
    if len(bad_date) > 0:
        bad_date["reason"] = "missing_or_bad_date"
        needs.append(bad_date)

    if site_df is not None:
        bad_site = site_df[site_df["site_label_plot"].fillna("").astype(str).str.strip().eq("")][["event_id"]].copy()
        if len(bad_site) > 0:
            bad_site["reason"] = "missing_site_label"
            needs.append(bad_site)

        bad_coords = site_df[(site_df["lat_plot"].isna()) | (site_df["lon_plot"].isna())][["event_id"]].copy()
        if len(bad_coords) > 0:
            bad_coords["reason"] = "missing_coords"
            needs.append(bad_coords)

    if not needs:
        return pd.DataFrame(columns=["event_id", "reason"])

    out = pd.concat(needs, ignore_index=True).dropna(subset=["event_id"])
    out = out.drop_duplicates(subset=["event_id", "reason"]).sort_values(["event_id", "reason"])
    return out


def write_cleaned(output_xlsx: str, events_df: pd.DataFrame, long_df: pd.DataFrame, site_df: Optional[pd.DataFrame]) -> None:
    # Attach site labels and coords to long_df if possible
    out_long = long_df.copy()
    if site_df is not None:
        add_cols = site_df[["event_id", "site_label_plot", "lat_plot", "lon_plot"]].drop_duplicates()
        out_long = out_long.merge(add_cols, on="event_id", how="left")
    else:
        out_long["site_label_plot"] = "unknown"
        out_long["lat_plot"] = np.nan
        out_long["lon_plot"] = np.nan

    # Events_clean
    out_events = events_df.copy()
    if site_df is not None:
        add_cols = site_df[["event_id", "site_label_plot", "lat_plot", "lon_plot"]].drop_duplicates()
        out_events = out_events.merge(add_cols, on="event_id", how="left")

    qc = build_qc_report(events_df, long_df, site_df)
    nf = build_needs_fixes(events_df, site_df)

    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        out_long.to_excel(writer, sheet_name="Clean_Long", index=False)
        out_events.to_excel(writer, sheet_name="Events_clean", index=False)
        qc.to_excel(writer, sheet_name="QC_Report", index=False)
        nf.to_excel(writer, sheet_name="Needs_Fixes", index=False)
        if site_df is not None:
            site_df.to_excel(writer, sheet_name="Site_clean", index=False)


def main() -> int:
    s = get_clean_settings()
    if not os.path.exists(s.input_xlsx):
        raise ValueError(f"Input workbook not found: {s.input_xlsx}")

    events_df, long_df = load_raw_long(s.input_xlsx)
    site_df = load_site(s.input_xlsx)
    site_df = apply_overrides(site_df, s.overrides_csv)

    Path(s.output_xlsx).parent.mkdir(parents=True, exist_ok=True)
    write_cleaned(s.output_xlsx, events_df, long_df, site_df)
    return 0


if __name__ == "__main__":
    rc = main()
    raise SystemExit(rc)
