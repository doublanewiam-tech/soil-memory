"""Run with:  python -m pytest -q   (or just: python tests/test_core.py)"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core  # noqa: E402


def test_synthetic_is_labeled_and_deterministic():
    a = core.synthetic_series(32.6167, -8.4833, 2018, 2024)
    b = core.synthetic_series(32.6167, -8.4833, 2018, 2024)
    assert a.attrs["source"] == core.SOURCE_SYNTH and a.attrs["is_real"] is False
    pd.testing.assert_frame_equal(a, b)


def test_mirrored_coordinates_do_not_collide():
    a = core.synthetic_series(32.6, -8.5, 2018, 2024)
    b = core.synthetic_series(32.6, 8.5, 2018, 2024)
    assert not np.allclose(a["sm"], b["sm"])


def test_physical_ranges():
    for lat, lon in [(32.6, -8.5), (42.0, -93.6), (-12.7, -51.5), (70.0, 20.0)]:
        df = core.synthetic_series(lat, lon, 2016, 2024)
        assert df["sm"].between(0.03, 0.50).all()      # volumetric, m3/m3
        assert df["ndvi"].between(0.05, 0.95).all()


def test_no_months_before_smap_or_in_future():
    df = core.synthetic_series(10, 10, 2010, 2030)
    assert df.index.min() >= core.SMAP_FIRST_MONTH
    assert df.index.max() < pd.Timestamp.today().normalize().replace(day=1)


def test_tau_recovers_known_ar1():
    rng = np.random.default_rng(0)
    phi, n = 0.7, 4000
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + rng.normal()
    idx = pd.date_range("2000-01-01", periods=n, freq="MS")
    df = pd.DataFrame({"sm": x, "ndvi": x}, index=idx)
    m = core.memory_metrics(df)
    expected = -1 / np.log(phi)
    assert abs(m.tau_months - expected) < 0.4


def test_demo_lag_is_detected():
    df = core.synthetic_series(42.0, -93.6, 2016, 2025)
    m = core.memory_metrics(df)
    assert m.best_lag_months == 1 and m.best_lag_corr > 0.5


def test_rotation_ordering_and_validation():
    legume = core.simulate_rotation(["Maize"], 20, 30, 0.25).iloc[-1]
    fallow = core.simulate_rotation(["Bare fallow"], 20, 30, 0.25).iloc[-1]
    assert legume > fallow
    try:
        core.simulate_rotation([], 5, 30, 0.2)
        raise AssertionError("empty rotation should raise")
    except ValueError:
        pass


def test_short_series_rejected():
    df = core.synthetic_series(10, 10, 2024, 2025).iloc[:10]
    try:
        core.memory_metrics(df)
        raise AssertionError("short series should raise")
    except ValueError:
        pass


def test_real_cache_roundtrip_and_validation(tmp_path=None):
    import tempfile
    d = Path(tempfile.mkdtemp())
    core.CACHE_DIR = d
    idx = pd.date_range("2016-01-01", periods=60, freq="MS")
    good = pd.DataFrame({"date": idx, "ndvi": 0.4, "sm": 0.2, "sm_source": "SMAP_L4"})
    good.to_csv(d / "ok.csv", index=False)
    df = core.load_real_cache("ok", 2016, 2020)
    assert df is not None and df.attrs["is_real"] and "SMAP" in df.attrs["source"]
    bad = good.assign(sm=55.0)                      # percent, not fraction -> reject
    bad.to_csv(d / "bad.csv", index=False)
    assert core.load_real_cache("bad", 2016, 2020) is None
    nosrc = good.drop(columns="sm_source")
    nosrc.to_csv(d / "nosrc.csv", index=False)
    assert core.load_real_cache("nosrc", 2016, 2020) is None
    assert core.load_real_cache("missing", 2016, 2020) is None


def test_power_unit_rotation_runs():
    r = core.simulate_rotation(["Wheat"], 10, 30, 0.4, "fraction of saturation (0-1)")
    assert r.iloc[-1] > 0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
