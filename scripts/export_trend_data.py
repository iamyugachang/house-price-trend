#!/usr/bin/env python3
"""Export market_grid asking series -> static JSON for the GH Pages trend site.

Series key:  <district>|<size_bucket>|<rooms>|<window_months>
Point row:   [run_at_ms, n_pool, median_total_wan, median_unit_wan_per_ping,
               p25_unit_wan_per_ping, p75_unit_wan_per_ping]

Rules:
- source_type = 'asking' only (lvr table has no data since ~May)
- rooms 1..5 (0 = missing/other, excluded)
- n_pool >= 5 (unstable cells dropped)
- skips runs/points with NULL medians
"""
from __future__ import annotations

import json
import site
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path.home() / "workspace" / "tw-house-daily"
sys.path.insert(0, str(PROJECT / "src"))
venv_site = PROJECT / ".venv" / "lib" / "python3.11" / "site-packages"
if venv_site.exists():
    site.addsitedir(str(venv_site))

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

from tw_house_daily.db import dsn  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
REGION_FILE = {"台北市": "trend-taipei.json", "新北市": "trend-newtaipei.json"}

SQL = """
SELECT r.run_at AS run_at,
       g.region, g.district, g.size_bucket, g.rooms, g.window_months,
       g.n_pool,
       CAST(g.median_total_wan AS float8)         AS median_total_wan,
       CAST(g.median_unit_wan_per_ping AS float8) AS median_unit_wan_per_ping,
       CAST(g.p25_unit_wan_per_ping AS float8)    AS p25_unit,
       CAST(g.p75_unit_wan_per_ping AS float8)    AS p75_unit
FROM market_grid g
JOIN market_snapshot_runs r USING (run_id)
WHERE g.source_type = 'asking'
  AND g.rooms BETWEEN 1 AND 5
  AND g.n_pool >= 5
  AND g.median_unit_wan_per_ping IS NOT NULL
ORDER BY r.run_at, g.region, g.district
"""


def main() -> int:
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        rows = conn.execute(SQL).fetchall()

    series: dict[str, dict[str, list]] = {
        "台北市": defaultdict(list), "新北市": defaultdict(list)}
    district_meta: dict[str, dict] = {
        "台北市": defaultdict(lambda: {"sizes": set(), "rooms": set(), "series": 0}),
        "新北市": defaultdict(lambda: {"sizes": set(), "rooms": set(), "series": 0}),
    }
    first_ts = last_ts = None
    runs_seen: set[int] = set()

    for r in rows:
        ts = int(r["run_at"].timestamp() * 1000)
        first_ts = ts if first_ts is None else min(first_ts, ts)
        last_ts = ts if last_ts is None else max(last_ts, ts)
        runs_seen.add(ts)
        region = r["region"]
        key = f"{r['district']}|{r['size_bucket']}|{r['rooms']}|{r['window_months']}"
        series[region][key].append([
            ts, r["n_pool"], r["median_total_wan"], r["median_unit_wan_per_ping"],
            r["p25_unit"], r["p75_unit"],
        ])
        dm = district_meta[region][r["district"]]
        dm["sizes"].add(r["size_bucket"])
        dm["rooms"].add(r["rooms"])
        dm["series"] += 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    regions_out = []
    for region, fname in REGION_FILE.items():
        reg_series = series[region]
        # compact: list of [key, points]
        payload = [[k, pts] for k, pts in reg_series.items()]
        path = OUT_DIR / fname
        path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        districts = [
            {"name": d,
             "sizes": sorted(v["sizes"], key=lambda s: {"<25": 0, "25-35": 1,
                                                        "35-50": 2, "50+": 3}.get(s, 9)),
             "rooms": sorted(v["rooms"]),
             "series": v["series"]}
            for d, v in sorted(district_meta[region].items())
        ]
        regions_out.append({
            "id": "taipei" if region == "台北市" else "newtaipei",
            "name": region, "file": fname, "districts": districts,
            "series_count": len(reg_series),
        })

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "asking (平台刊登價); lvr/實價登錄 無資料",
        "run_count": len(runs_seen),
        "first_run_at": datetime.fromtimestamp(first_ts / 1000, tz=timezone.utc).isoformat(),
        "last_run_at": datetime.fromtimestamp(last_ts / 1000, tz=timezone.utc).isoformat(),
        "windows_months": [1, 3, 6, 12],
        "regions": regions_out,
    }
    (OUT_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    for region, fname in REGION_FILE.items():
        sz = (OUT_DIR / fname).stat().st_size / 1e6
        print(f"{fname}: {len(series[region])} series, {sz:.1f} MB")
    print(f"meta.json: {len(regions_out)} regions, "
          f"runs={len(runs_seen)} span={first_ts}..{last_ts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
