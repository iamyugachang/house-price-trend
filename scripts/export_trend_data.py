#!/usr/bin/env python3
"""Export housing data for the GH Pages trend/stats site.

Datasets:
1) market trend series: market_grid asking + lvr cells, keyed per region/source
   district|size|rooms|window -> [run_at_ms, n, med_total, med_unit, p25, p75]
   files: trend-{region}.json (asking) + trend-lvr-{region}.json (成交)
2) fine-grained "行情水準" pool (asking only): 雙北 residential listings seen
   within last 13 months w/ Houseflow-grade metadata.
   -> docs/data/listings-{region}.csv.gz (see column doc in README / meta)
"""
from __future__ import annotations

import gzip
import io
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
REGION_IDS = {"台北市": "taipei", "新北市": "newtaipei"}
REGION_LIST = {"台北市": "listings-taipei.csv.gz", "新北市": "listings-newtaipei.csv.gz"}
SRC_MAP = {"591": 0, "sinyi": 1, "yungching": 2, "hbhousing": 3}
TYPE_MAP = {"unknown_residential": 0, "apartment": 1, "walkup": 2,
            "mid_rise": 3, "high_rise": 4, "townhouse": 5}

TREND_SQL = """
SELECT g.source_type AS src, r.run_at AS run_at,
       g.region, g.district, g.size_bucket, g.rooms, g.window_months,
       g.n_pool,
       CAST(g.median_total_wan AS float8)         AS median_total_wan,
       CAST(g.median_unit_wan_per_ping AS float8) AS median_unit_wan_per_ping,
       CAST(g.p25_unit_wan_per_ping AS float8)    AS p25_unit,
       CAST(g.p75_unit_wan_per_ping AS float8)    AS p75_unit
FROM market_grid g
JOIN market_snapshot_runs r USING (run_id)
WHERE g.source_type IN ('asking', 'lvr')
  AND g.rooms BETWEEN 1 AND 5
  AND g.n_pool >= 5
  AND g.median_unit_wan_per_ping IS NOT NULL
ORDER BY r.run_at, g.region, g.district
"""

LIST_SQL = """
SELECT source,
       region, district, building_type_norm,
       has_elevator, has_parking, has_rooftop_addition,
       CAST(age_years AS float8) AS age_years,
       CASE WHEN main_ping IS NOT NULL AND accessory_ping IS NOT NULL
            THEN CAST(main_ping + accessory_ping AS float8) END AS main_acc,
       CAST(size_ping AS float8) AS size_ping,
       rooms, nearest_mrt_dist_m,
       CAST(price_wan AS float8) AS price_wan,
       CAST(unit_wan_per_ping AS float8) AS unit_wan,
       EXTRACT(EPOCH FROM last_seen_at)::bigint / 86400 AS last_d,
       CASE WHEN is_active THEN 1 ELSE 0 END AS act
FROM listings
WHERE region = %s
  AND (is_active OR last_seen_at >= now() - interval '13 months')
  AND (usage_type = '住宅' OR usage_type IS NULL)
  AND district IS NOT NULL
  AND price_wan BETWEEN 300 AND 20000
  AND unit_wan_per_ping IS NOT NULL
"""


def fnum(v, nd=1):
    if v is None:
        return ""
    return f"{v:.{nd}f}"


def main() -> int:
    with psycopg.connect(dsn(), row_factory=dict_row) as conn:
        # --- part 1: trend series per (region, source) ---
        rows = conn.execute(TREND_SQL).fetchall()
        series: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for r in rows:
            if r["region"] not in REGION_IDS:
                continue  # site currently serves 雙北 only
            ts = int(r["run_at"].timestamp() * 1000)
            key = f"{r['district']}|{r['size_bucket']}|{r['rooms']}|{r['window_months']}"
            series[r["region"]][r["src"]][key].append(
                [ts, r["n_pool"], r["median_total_wan"], r["median_unit_wan_per_ping"],
                 r["p25_unit"], r["p75_unit"]])

        regions_out = []
        for region, rid in REGION_IDS.items():
            files = {}
            for src in ("asking", "lvr"):
                fname = f"trend-{rid}.json" if src == "asking" else f"trend-lvr-{rid}.json"
                payload = [[k, pts] for k, pts in series[region][src].items()]
                (OUT_DIR / fname).write_text(
                    json.dumps(payload, separators=(",", ":")), encoding="utf-8")
                files[src] = fname
                print(f"{fname}: {len(payload)} series")
            regions_out.append({"id": rid, "name": region, "files": files})

        # --- part 2: fine listings pool (asking) per region ---
        fine_meta = {}
        for region, fname in REGION_LIST.items():
            rows = conn.execute(LIST_SQL, [region]).fetchall()
            buf = io.StringIO()
            for r in rows:
                t = SRC_MAP.get(r["source"], 0)
                b = TYPE_MAP.get(r["building_type_norm"], 0)
                e = -1 if r["has_elevator"] is None else int(r["has_elevator"])
                p = -1 if r["has_parking"] is None else int(r["has_parking"])
                roof = -1 if r["has_rooftop_addition"] is None else int(r["has_rooftop_addition"])
                buf.write(
                    f"{t},{r['district']},{b},{e},{p},{roof},{fnum(r['age_years'],1)},"
                    f"{fnum(r['main_acc'],1)},{fnum(r['size_ping'],1)},"
                    f"{'' if r['rooms'] is None else int(r['rooms'])},"
                    f"{'' if r['nearest_mrt_dist_m'] is None else int(r['nearest_mrt_dist_m'])},"
                    f"{fnum(r['price_wan'],0)},{fnum(r['unit_wan'],1)},"
                    f"{int(r['last_d'])},{r['act']}\n")
            raw = buf.getvalue().encode("utf-8")
            path = OUT_DIR / fname
            with gzip.open(path, "wb", compresslevel=6) as fz:
                fz.write(raw)
            fine_meta[REGION_IDS[region]] = {
                "file": fname, "rows": len(rows),
                "max_last_d": max(int(r["last_d"]) for r in rows),
            }
            print(f"{fname}: {len(rows)} rows, {path.stat().st_size/1e6:.1f} MB gz")

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "trend": {
            "source": "asking=平台刊登價 market_grid；lvr=內政部實價登錄成交(季公布,揭露至 2026-06)。"
                      "lvr 近1/3月窗通常無資料屬正常滯後。",
            "regions": regions_out,
        },
        "fine": {
            "source": "asking 現況刊登池；欄位: src,district,type,elev,park,roof,age,m_acc,size,rooms,"
                      "mrt,price,unit,last_d,act（type/elev/park/roof=-1 或空=未知）",
            "src_names": ["591", "sinyi", "yungching", "hbhousing"],
            "type_names": ["未分類/unknown", "公寓", "華廈", "大樓(11-19F)",
                           "電梯大樓(20F+)", "透天"],
            "regions": fine_meta,
        },
    }
    (OUT_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("meta.json updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
