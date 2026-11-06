import datetime as dt

import pandas as pd
import streamlit as st

import core

st.set_page_config(page_title="Soil Memory", page_icon="🌱", layout="wide")
st.title("🌱 Soil Memory")
st.caption("Reading what the soil remembers: NASA SMAP + MODIS, turned into a "
           "rotation decision tool.")

PRESETS = {
    "Doukkala Plain (Morocco)": (32.6167, -8.4833, "doukkala"),
    "Souss-Massa (Morocco)": (30.4202, -9.5982, "souss_massa"),
    "Iowa Corn Belt (USA)": (42.0329, -93.5815, "iowa"),
    "Central Valley, California (USA)": (36.5, -119.8, "central_valley"),
    "Argentine Pampas": (-34.6037, -58.3816, "pampas"),
    "Cerrado Grain Belt (Brazil)": (-12.6819, -51.4969, "cerrado"),
    "Beauce (France)": (48.3, 1.5, "beauce"),
    "Chernozem Belt (Ukraine)": (49.8397, 24.0297, "chernozem"),
    "Punjab (India)": (30.901, 75.8573, "punjab"),
    "Wheatbelt (Australia)": (-31.9505, 115.8605, "wheatbelt"),
    "Custom coordinates": None,
}


@st.cache_data(show_spinner=False)
def get_series(lat, lon, y0, y1, slug):
    return core.load_series(lat, lon, y0, y1, slug)


# ---------------- sidebar ----------------
st.sidebar.header("Field selection")
choice = st.sidebar.selectbox("Region", list(PRESETS))
if PRESETS[choice] is None:
    lat = st.sidebar.number_input("Latitude", -90.0, 90.0, 32.6167, 0.01)
    lon = st.sidebar.number_input("Longitude", -180.0, 180.0, -8.4833, 0.01)
    slug = None
else:
    lat, lon, slug = PRESETS[choice]

this_year = dt.date.today().year
y0, y1 = st.sidebar.slider("Baseline years (SMAP starts Apr 2015)",
                           2015, this_year, (2018, this_year - 1))

try:
    df = get_series(lat, lon, y0, y1, slug)
    metrics = core.memory_metrics(df)
except ValueError as e:
    st.error(f"Not enough data for this selection: {e}")
    st.stop()

is_real = df.attrs["is_real"]
unit = df.attrs["sm_unit"]
(st.success if is_real else st.warning)(f"**Data source:** {df.attrs['source']}")
if not is_real:
    st.caption("Numbers below illustrate the method. They are not measurements "
               "of this field. See README → 'Real vs simulated'.")

hemi_ns, hemi_ew = ("N" if lat >= 0 else "S"), ("E" if lon >= 0 else "W")
st.sidebar.info(f"📍 {abs(lat):.4f}°{hemi_ns}, {abs(lon):.4f}°{hemi_ew}")

tab1, tab2, tab3, tab4 = st.tabs(
    ["Trajectory", "Soil memory", "Rotation lab", "Method & limits"])

# ---------------- tab 1 ----------------
with tab1:
    c1, c2 = st.columns(2)
    c1.markdown("**NDVI (MODIS)**, unitless")
    c1.line_chart(df["ndvi"])
    c2.markdown(f"**Surface soil moisture / wetness**, {unit}")
    c2.line_chart(df["sm"])
    st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=6)
    st.download_button("Download series (CSV)", df.to_csv().encode(),
                       file_name="soil_memory_series.csv", mime="text/csv")

# ---------------- tab 2 ----------------
with tab2:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Moisture persistence τ",
              "n/a" if pd.isna(metrics.tau_months) else f"{metrics.tau_months:.1f} mo",
              help="e-folding time of soil-moisture anomalies: τ = −1/ln(r₁)")
    m2.metric("Lag-1 autocorrelation r₁", f"{metrics.r1:.2f}")
    m3.metric("Vegetation response lag", f"{metrics.best_lag_months} mo",
              help=f"corr = {metrics.best_lag_corr:.2f}")
    m4.metric("NDVI trend", f"{metrics.ndvi_trend_per_year:+.4f} /yr",
              help="Deseasonalised slope: positive = greening, negative = browning")
    anom = pd.DataFrame({"NDVI anomaly": core.monthly_anomalies(df["ndvi"]),
                         "Soil-moisture anomaly": core.monthly_anomalies(df["sm"])})
    st.line_chart(anom)
    st.caption("Soil memory = how long a moisture anomaly persists (τ) and how "
               "strongly vegetation carries it forward (lag and correlation).")

# ---------------- tab 3 ----------------
with tab3:
    st.markdown("Compare two rotations on the same field. **Scenario model: "
                "illustrative inputs, not a forecast.**")
    crops = list(core.CROP_INPUT_TC_HA)
    a, b = st.columns(2)
    rot_a = a.multiselect("Rotation A (cycled in order)", crops, ["Wheat"])
    rot_b = b.multiselect("Rotation B", crops,
                          ["Wheat", "Legume (faba / chickpea)", "Wheat + cover crop"])
    horizon = st.slider("Horizon (years)", 5, 30, 15)
    soc0 = st.number_input("Current topsoil SOC stock (t C/ha), use a lab value",
                           5.0, 150.0, 30.0)
    if rot_a and rot_b:
        out = pd.DataFrame({
            "Rotation A": core.simulate_rotation(rot_a, horizon, soc0, df["sm"].mean(), unit),
            "Rotation B": core.simulate_rotation(rot_b, horizon, soc0, df["sm"].mean(), unit),
        })
        st.line_chart(out)
        d = out.iloc[-1]["Rotation B"] - out.iloc[-1]["Rotation A"]
        st.metric(f"B vs A after {horizon} yr", f"{d:+.1f} t C/ha")
    else:
        st.info("Pick at least one crop for each rotation.")

# ---------------- tab 4 ----------------
with tab4:
    st.markdown(
        """
**Data:** SMAP L4 `SPL4SMGP` (9 km, model-assimilated surface soil moisture) and
MODIS `MOD13Q1` NDVI (250 m, 16-day), aggregated to monthly.
**Scale gap:** one SMAP cell covers ~1,300 MODIS pixels, so soil moisture is a
*regional* signal, not a per-field measurement.
**SOC:** NDVI and soil moisture do not measure soil carbon. The rotation tab uses
a one-pool balance model seeded by *your* measured SOC.
**Not validated** against in-situ SOC yet. See README roadmap.
"""
    )
