"""Tests parsers/validation against example payloads shaped like the NASA APIs.
These check OUR code; they cannot prove the live APIs still return this shape."""
import importlib.util, sys, tempfile
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("fetch", ROOT / "scripts" / "fetch_real_data.py")
fetch = importlib.util.module_from_spec(spec); spec.loader.exec_module(fetch)
import core


def test_power_parser_drops_annual_and_fill():
    js = {"properties": {"parameter": {"GWETTOP": {
        "201501": 0.31, "201502": -999.0, "201503": 0.28, "201513": 0.30}}}}
    s = fetch.parse_power_monthly(js)
    assert list(s.index) == [pd.Timestamp("2015-01-01"), pd.Timestamp("2015-03-01")]
    assert s.iloc[0] == 0.31


def test_modis_parser_scales_and_drops_fill():
    js = {"scale": "0.0001", "subset": [
        {"calendar_date": "2020-01-01", "data": [4500]},
        {"calendar_date": "2020-01-17", "data": [-3000]},   # fill
        {"calendar_date": "2020-02-02", "data": [5200]}]}
    s = fetch.parse_modis_subset(js)
    assert len(s) == 2 and abs(s.iloc[0] - 0.45) < 1e-9


def test_end_to_end_build_with_stubbed_network(monkeypatch_dir=None):
    idx = pd.date_range("2016-01-01", "2020-12-01", freq="MS")
    fetch.START, fetch.END = pd.Timestamp("2016-01-01"), pd.Timestamp("2020-12-01")
    fetch.OUT = Path(tempfile.mkdtemp())
    fetch.fetch_power_sm = lambda la, lo: pd.Series(0.3, index=idx)
    fetch.fetch_modis_ndvi = lambda la, lo: pd.Series(0.5, index=idx)
    df = fetch.build("t", 1.0, 2.0, "open")
    assert (fetch.OUT / "t.csv").exists() and df["sm_source"].iloc[0] == "MERRA2_POWER"
    core.CACHE_DIR = fetch.OUT
    back = core.load_real_cache("t", 2016, 2020)
    assert back is not None and back.attrs["is_real"]


def test_build_refuses_bad_units():
    idx = pd.date_range("2016-01-01", "2020-12-01", freq="MS")
    fetch.START, fetch.END = idx[0], idx[-1]
    fetch.fetch_power_sm = lambda la, lo: pd.Series(40.0, index=idx)   # percent -> invalid
    fetch.fetch_modis_ndvi = lambda la, lo: pd.Series(0.5, index=idx)
    try:
        fetch.build("bad", 1.0, 2.0, "open"); raise AssertionError("should refuse")
    except ValueError:
        pass


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"): f(); print("ok ", n)
