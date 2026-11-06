"""Download REAL NASA data for the preset regions and save to data/cache/*.csv

Two modes (same CSV format, the app labels the source honestly):

  python scripts/fetch_real_data_v2.py --source open   # NO account, NO keys
      NDVI : MODIS MOD13Q1 via ORNL DAAC MODIS web service  (NASA)
      Soil : NASA POWER monthly GWETTOP surface soil wetness (MERRA-2 reanalysis,
             a NASA model product at ~50 km, NOT SMAP)

  python scripts/fetch_real_data_v2.py --source gee    # needs Earth Engine login
      NDVI : MODIS MOD13Q1
      Soil : SMAP L4 SPL4SMGP sm_surface (true SMAP, 9 km)
      one-time setup: pip install earthengine-api ; earthengine authenticate

Optional: --only doukkala   (fetch a single region first as a smoke test)

STATUS: the parsing and validation logic is unit-tested against example payloads
(tests/test_fetch_parsing.py). The live HTTP calls could NOT be run where this was
written (no internet), so the first run is the real test. Every failure prints the
raw server reply so it can be fixed quickly.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import core  # noqa: E402

OUT = ROOT / "data" / "cache"
REGIONS = {  # slug: (lat, lon). Keep in sync with app.py PRESETS
    "doukkala": (32.6167, -8.4833), "souss_massa": (30.4202, -9.5982),
    "iowa": (42.0329, -93.5815), "central_valley": (36.5, -119.8),
    "pampas": (-34.6037, -58.3816), "cerrado": (-12.6819, -51.4969),
    "beauce": (48.3, 1.5), "chernozem": (49.8397, 24.0297),
    "punjab": (30.901, 75.8573), "wheatbelt": (-31.9505, 115.8605),
}
START = pd.Timestamp("2015-04-01")
END = pd.Timestamp.today().normalize().replace(day=1) - pd.DateOffset(months=1)


# ------------------------------------------------------------------ HTTP
def get_json(url: str, retries: int = 3):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/json", "User-Agent": "soil-memory/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError):
                body = e.read().decode(errors="replace")[:300]
                last = f"HTTP {e.code}: {body}"
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"request failed: {url}\n  -> {last}")


# ------------------------------------------------------------------ parsers (tested)
def parse_power_monthly(js: dict, par: str = "GWETTOP") -> pd.Series:
    """NASA POWER monthly point JSON -> monthly Series (fraction 0-1)."""
    vals = js["properties"]["parameter"][par]
    rows = {}
    for key, v in vals.items():
        if len(key) != 6 or key.endswith("13"):  # 'YYYY13' = annual mean
            continue
        if v is None or float(v) <= -900:        # POWER fill value is -999
            continue
        rows[pd.Timestamp(year=int(key[:4]), month=int(key[4:]), day=1)] = float(v)
    return pd.Series(rows, name="sm", dtype=float).sort_index()


def parse_modis_subset(js: dict) -> pd.Series:
    """ORNL DAAC MODIS subset JSON -> per-composite NDVI Series (scaled)."""
    scale = float(js.get("scale", 0.0001))
    out = {}
    for item in js["subset"]:
        raw = float(item["data"][0])
        if raw <= -2000:                          # fill value -3000 / invalid
            continue
        out[pd.Timestamp(item["calendar_date"])] = raw * scale
    return pd.Series(out, name="ndvi", dtype=float).sort_index()


# ------------------------------------------------------------------ open sources
def fetch_power_sm(lat, lon) -> pd.Series:
    q = urllib.parse.urlencode(dict(
        parameters="GWETTOP", community="AG", longitude=lon, latitude=lat,
        start=START.year, end=END.year, format="JSON"))
    return parse_power_monthly(get_json(f"https://power.larc.nasa.gov/api/temporal/monthly/point?{q}"))


def fetch_modis_ndvi(lat, lon) -> pd.Series:
    base = "https://modis.ornl.gov/rst/api/v1/MOD13Q1"
    dates = get_json(f"{base}/dates?latitude={lat}&longitude={lon}")["dates"]
    dates = [d for d in dates if START <= pd.Timestamp(d["calendar_date"]) <= END]
    parts = []
    for i in range(0, len(dates), 10):          # service limits dates per request
        chunk = dates[i:i + 10]
        q = urllib.parse.urlencode(dict(
            latitude=lat, longitude=lon, band="250m_16_days_NDVI",
            startDate=chunk[0]["modis_date"], endDate=chunk[-1]["modis_date"],
            kmAboveBelow=0, kmLeftRight=0))
        parts.append(parse_modis_subset(get_json(f"{base}/subset?{q}")))
        time.sleep(0.5)
    return pd.concat(parts).resample("MS").mean()


# ------------------------------------------------------------------ gee source
def fetch_gee(lat, lon):
    import ee  # lazy: only needed for --source gee
    ee.Initialize()
    pt = ee.Geometry.Point([lon, lat])
    months = pd.date_range(START, END, freq="MS")

    def monthly(coll_id, band, scale_factor, radius):
        coll = ee.ImageCollection(coll_id).select(band)
        vals = []
        for m in months:
            s = ee.Date(m.strftime("%Y-%m-%d"))
            img = coll.filterDate(s, s.advance(1, "month")).mean()
            vals.append(img.reduceRegion(ee.Reducer.mean(), pt.buffer(radius), radius).get(band))
        got = ee.List(vals).getInfo()
        return pd.Series([None if v is None else v * scale_factor for v in got],
                         index=months, dtype=float)

    ndvi = monthly("MODIS/061/MOD13Q1", "NDVI", 0.0001, 5000)
    sm = monthly("NASA/SMAP/SPL4SMGP/007", "sm_surface", 1.0, 9000)
    return ndvi, sm


# ------------------------------------------------------------------ main
def build(slug, lat, lon, source):
    if source == "open":
        sm, ndvi, tag = fetch_power_sm(lat, lon), fetch_modis_ndvi(lat, lon), "MERRA2_POWER"
    else:
        ndvi, sm = fetch_gee(lat, lon)
        tag = "SMAP_L4"
    df = pd.concat([ndvi.rename("ndvi"), sm.rename("sm")], axis=1).dropna()
    df.index.name = "date"
    df = df.loc[START:END]
    if not core.validate_real(df):
        raise ValueError(
            f"validation failed (rows={len(df)}, ndvi {df.ndvi.min():.2f}..{df.ndvi.max():.2f}, "
            f"sm {df.sm.min():.2f}..{df.sm.max():.2f}); NOT saved")
    df["sm_source"] = tag
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / f"{slug}.csv")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["open", "gee"], default="open")
    ap.add_argument("--only", help="single region slug, e.g. doukkala")
    args = ap.parse_args()
    todo = {k: v for k, v in REGIONS.items() if not args.only or k == args.only}
    failed = []
    for slug, (lat, lon) in todo.items():
        try:
            df = build(slug, lat, lon, args.source)
            print(f"OK   {slug:15s} {len(df):3d} months | NDVI {df.ndvi.min():.2f}-{df.ndvi.max():.2f}"
                  f" | soil {df.sm.min():.2f}-{df.sm.max():.2f}")
        except Exception as e:  # keep going; report at the end
            failed.append(slug)
            print(f"FAIL {slug:15s} {e}")
    print(f"\n{len(todo) - len(failed)}/{len(todo)} regions saved to {OUT}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
