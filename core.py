"""Soil Memory core logic (no Streamlit imports, so it is unit-testable).

Three responsibilities:
  1. load_series()      -> monthly NDVI + soil moisture, with explicit PROVENANCE
  2. memory_metrics()   -> quantitative definition of "soil memory"
  3. simulate_rotation()-> transparent first-order SOC scenario model

Design rule: the app must never imply data is real when it is not.
Every DataFrame returned by load_series() carries df.attrs["source"].
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

CACHE_DIR = Path(__file__).parent / "data" / "cache"

# SMAP L4 (SPL4SMGP) record begins 31 March 2015.
SMAP_FIRST_MONTH = pd.Timestamp("2015-04-01")

SOURCE_LABELS = {
    "SMAP_L4": "REAL: NASA SMAP L4 (SPL4SMGP) soil moisture + MODIS MOD13Q1 NDVI",
    "MERRA2_POWER": ("REAL: NASA POWER / MERRA-2 soil wetness (model reanalysis, "
                     "not SMAP) + MODIS MOD13Q1 NDVI"),
}
SM_UNITS = {"SMAP_L4": "m3/m3", "MERRA2_POWER": "fraction of saturation (0-1)"}
SOURCE_SYNTH = "SYNTHETIC: demo generator, NOT satellite observations"


# --------------------------------------------------------------------------
# 1. Data loading
# --------------------------------------------------------------------------
def _month_index(start_year: int, end_year: int) -> pd.DatetimeIndex:
    """Month-start index, clamped to SMAP's record and to the last full month."""
    start = max(pd.Timestamp(f"{start_year}-01-01"), SMAP_FIRST_MONTH)
    last_full = (pd.Timestamp.today().normalize().replace(day=1)
                 - pd.DateOffset(months=1))
    end = min(pd.Timestamp(f"{end_year}-12-01"), last_full)
    # "MS" (month start) works on every pandas version; "ME" needs >= 2.2.
    return pd.date_range(start, end, freq="MS")


def validate_real(df: pd.DataFrame) -> bool:
    """Reject files that are empty, out of physical range, or mostly gaps."""
    if len(df) < 24 or df[["ndvi", "sm"]].isna().mean().max() > 0.2:
        return False
    return bool(df["ndvi"].between(-0.2, 1.0).all() and df["sm"].between(0, 1).all())


def load_real_cache(region_slug: str, start_year: int, end_year: int):
    """Return a precomputed real-data frame for a preset region, or None.

    CSV columns: date, ndvi, sm, sm_source  (sm_source in SOURCE_LABELS)
    """
    path = CACHE_DIR / f"{region_slug}.csv"
    if not path.exists():
        return None
    raw = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    kind = str(raw["sm_source"].iloc[0]) if "sm_source" in raw else ""
    if kind not in SOURCE_LABELS:
        return None
    df = raw.loc[f"{start_year}-01-01":f"{end_year}-12-31", ["ndvi", "sm"]].copy()
    df = df.interpolate(limit=2)  # fill isolated cloud gaps only
    if not validate_real(df.dropna()):
        return None
    df = df.dropna()
    df.attrs.update(source=SOURCE_LABELS[kind], is_real=True, sm_unit=SM_UNITS[kind])
    return df


def synthetic_series(lat: float, lon: float, start_year: int, end_year: int):
    """Plausible-looking placeholder series. NEVER present as observations.

    Fixes vs. the original generator:
      * local Generator, no global np.random.seed() side effects
      * seed uses the SIGNED coordinates (no mirrored-location collisions)
      * soil moisture is volumetric (m3/m3) with realistic ranges
      * NDVI follows soil moisture with a 1-month lag (so memory metrics
        have something to detect; this is a property of the DEMO, not evidence)
    """
    idx = _month_index(start_year, end_year)
    rng = np.random.default_rng(zlib.crc32(f"{lat:.3f},{lon:.3f}".encode()))
    n = len(idx)
    month = idx.month.to_numpy()

    abs_lat = abs(lat)
    base_sm = 0.30 if abs_lat < 15 else 0.16 if abs_lat < 35 else 0.26 if abs_lat < 55 else 0.28
    base_ndvi = 0.65 if abs_lat < 15 else 0.32 if abs_lat < 35 else 0.55 if abs_lat < 55 else 0.40

    # wet season peaks in local winter/early spring (shifted 6 months south)
    shift = 0 if lat >= 0 else 6
    seasonal = np.cos(2 * np.pi * (month - 2 + shift) / 12)

    noise = np.zeros(n)  # AR(1): this is what gives the series "memory"
    eps = rng.normal(0, 0.018, n)
    for i in range(1, n):
        noise[i] = 0.6 * noise[i - 1] + eps[i]
    sm = np.clip(base_sm + 0.05 * seasonal + noise, 0.03, 0.50)

    z = (sm - sm.mean()) / (sm.std() + 1e-9)
    z_lag = np.r_[z[0], z[:-1]]
    ndvi = np.clip(base_ndvi + 0.10 * z_lag + 0.03 * seasonal
                   + rng.normal(0, 0.015, n), 0.05, 0.95)

    df = pd.DataFrame({"ndvi": ndvi, "sm": sm}, index=idx)
    df.index.name = "date"
    df.attrs.update(source=SOURCE_SYNTH, is_real=False, sm_unit="m3/m3")
    return df


def load_series(lat, lon, start_year, end_year, region_slug=None):
    """Real cached data if available for this region, else labeled synthetic."""
    if region_slug:
        real = load_real_cache(region_slug, start_year, end_year)
        if real is not None:
            return real
    return synthetic_series(lat, lon, start_year, end_year)


# --------------------------------------------------------------------------
# 2. Quantifying "soil memory"
# --------------------------------------------------------------------------
@dataclass
class MemoryMetrics:
    r1: float                 # lag-1 autocorrelation of soil-moisture anomalies
    tau_months: float         # e-folding persistence time  tau = -1 / ln(r1)
    best_lag_months: int      # lag at which NDVI anomaly best tracks past moisture
    best_lag_corr: float
    ndvi_trend_per_year: float  # deseasonalised NDVI slope (greening / browning)


def monthly_anomalies(s: pd.Series) -> pd.Series:
    """Remove the mean seasonal cycle (per calendar month)."""
    return s - s.groupby(s.index.month).transform("mean")


def memory_metrics(df: pd.DataFrame) -> MemoryMetrics:
    """Define soil memory as how long a moisture anomaly persists, and how
    strongly vegetation carries it forward.

    tau = -dt / ln(r1) is the standard e-folding persistence time of an AR(1)
    process (dt = 1 month). Larger tau = a drought or wet spell lingers longer
    = the field has "longer memory".
    """
    if len(df) < 24:
        raise ValueError("Need at least 24 months to estimate memory.")
    sm_a = monthly_anomalies(df["sm"])
    nd_a = monthly_anomalies(df["ndvi"])

    r1 = float(sm_a.autocorr(1))
    tau = float(-1.0 / np.log(r1)) if 0.0 < r1 < 1.0 else float("nan")

    corrs = {lag: float(nd_a.corr(sm_a.shift(lag))) for lag in range(0, 4)}
    best_lag = max(corrs, key=lambda k: -9 if np.isnan(corrs[k]) else corrs[k])

    years = (nd_a.index - nd_a.index[0]).days.to_numpy() / 365.25
    slope = float(np.polyfit(years, nd_a.to_numpy(), 1)[0])

    return MemoryMetrics(r1, tau, best_lag, corrs[best_lag], slope)


# --------------------------------------------------------------------------
# 3. Rotation scenarios (illustrative one-pool SOC model)
# --------------------------------------------------------------------------
# ILLUSTRATIVE residue-carbon inputs in t C / ha / yr. Calibrate with local
# agronomy data before drawing conclusions. These are assumptions, not results.
CROP_INPUT_TC_HA = {
    "Wheat": 2.4,
    "Barley": 2.0,
    "Legume (faba / chickpea)": 2.0,
    "Maize": 4.0,
    "Wheat + cover crop": 3.4,
    "Bare fallow": 0.5,
}
HUMIFICATION = 0.25      # fraction of input carbon retained as SOC
K_DECOMP = 0.02          # 1/yr base decomposition rate
SM_OPTIMUM = {"m3/m3": 0.25, "fraction of saturation (0-1)": 0.50}  # f(SM) = 1 here


def simulate_rotation(rotation, years: int, soc0_tc_ha: float, mean_sm: float,
                      sm_unit: str = "m3/m3"):
    """SOC_{y+1} = SOC_y + h * I(crop_y) - k * f(SM) * SOC_y

    f(SM) scales decomposition by observed mean soil moisture (clipped).
    Returns a Series of SOC (t C/ha), index 0..years.
    """
    if not rotation:
        raise ValueError("Rotation must contain at least one crop.")
    f_sm = float(np.clip(mean_sm / SM_OPTIMUM[sm_unit], 0.5, 1.3))
    soc = [soc0_tc_ha]
    for y in range(years):
        crop = rotation[y % len(rotation)]
        inp = CROP_INPUT_TC_HA[crop]
        soc.append(soc[-1] + HUMIFICATION * inp - K_DECOMP * f_sm * soc[-1])
    return pd.Series(soc, index=range(years + 1), name="SOC (t C/ha)")
