from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd


@dataclass
class ItemSpec:
    group: str
    item: str


def _two_row_headers(base_cols: List[Tuple[str, str]], items: List[ItemSpec]) -> List[Tuple[str, str]]:
    cols: List[Tuple[str, str]] = []
    cols.extend(base_cols)
    for it in items:
        cols.append((it.group, it.item))
    cols.append(("Summary", "Total items"))
    cols.append(("Summary", "Total items/m2"))
    cols.append(("QA", "Complete?"))
    return cols


def create_sample_workbook(path: str, n_events: int = 12, seed: int = 7) -> str:
    """
    Creates a fake raw workbook that matches the app's expected format:
    - Sheet: Data with 2-row headers
    - Sheet: Site with Event ID, Date, Site, Latitude, Longitude, Northing, Westing
    """
    rng = np.random.default_rng(seed)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    base_cols = [
        ("", "Event ID"),
        ("", "Date"),
        ("", "Surveyed m2"),
    ]

    items = [
        ItemSpec("Plastic", "Bottle"),
        ItemSpec("Plastic", "Bag"),
        ItemSpec("Metal", "Can"),
        ItemSpec("Glass", "Bottle"),
        ItemSpec("Paper", "Cup"),
        ItemSpec("Other", "Foam"),
    ]

    cols = _two_row_headers(base_cols, items)

    start = date(2025, 1, 1)
    event_ids = list(range(1001, 1001 + n_events))
    dates = [start + timedelta(days=int(i * 14)) for i in range(n_events)]
    surveyed = rng.uniform(10, 80, size=n_events).round(1)

    data_rows = []
    for eid, d, area in zip(event_ids, dates, surveyed):
        counts = rng.integers(0, 25, size=len(items)).astype(int)
        total_items = float(counts.sum())
        total_per_m2 = float(total_items / area) if area > 0 else np.nan

        row_map = {
            ("", "Event ID"): eid,
            ("", "Date"): int(d.strftime("%y%m%d")),
            ("", "Surveyed m2"): float(area),
            ("Summary", "Total items"): total_items,
            ("Summary", "Total items/m2"): total_per_m2,
            ("QA", "Complete?"): "Y",
        }
        for it, c in zip(items, counts):
            row_map[(it.group, it.item)] = float(c)

        data_rows.append([row_map.get(c, None) for c in cols])

    df_data = pd.DataFrame(data_rows, columns=pd.MultiIndex.from_tuples(cols))

    # Site sheet
    sites = [f"SITE_{i:02d}" for i in range(1, n_events + 1)]
    lat0, lon0 = 31.55, -110.95
    lats = lat0 + rng.normal(0, 0.15, size=n_events)
    lons = lon0 + rng.normal(0, 0.20, size=n_events)

    df_site = pd.DataFrame(
        {
            "Event ID": event_ids,
            "Date": [int(d.strftime("%y%m%d")) for d in dates],
            "Site": sites,
            "Latitude": lats.round(6),
            "Longitude": lons.round(6),
            "Northing": (rng.uniform(100000, 200000, size=n_events)).round(2),
            "Westing": (rng.uniform(300000, 400000, size=n_events)).round(2),
        }
    )

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df_data.to_excel(writer, sheet_name="Data", index=False)
        df_site.to_excel(writer, sheet_name="Site", index=False)

    return str(out_path)


if __name__ == "__main__":
    here = Path(__file__).resolve().parent.parent
    target = here / "data" / "sample_trash.xlsx"
    created = create_sample_workbook(str(target))
    print(created)
