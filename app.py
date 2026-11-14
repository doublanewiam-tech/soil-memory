import streamlit as st
import pandas as pd

st.set_page_config(page_title="Soil Memory", page_icon="🌱", layout="wide")
st.title("🌱 Soil Memory Profile")
st.subheader("Satellite-driven soil health tracker")


@st.cache_data
def load_data():
    return pd.read_csv("regions.csv", parse_dates=["Date"]).dropna()


all_data = load_data()

st.sidebar.header("Field Selection")
region = st.sidebar.selectbox("Region", sorted(all_data["Region"].unique()))
data = all_data[all_data["Region"] == region].set_index("Date")
lat, lon = data["Lat"].iloc[0], data["Lon"].iloc[0]

years = st.sidebar.slider(
    "Historical Baseline (Years)",
    int(data.index.year.min()), int(data.index.year.max()),
    (int(data.index.year.min()), int(data.index.year.max())),
)
df = data[(data.index.year >= years[0]) & (data.index.year <= years[1])]

st.success("Data: NASA MODIS (NDVI) and NASA SMAP L4 (soil moisture), via Google Earth Engine.")

col1, col2 = st.columns([2, 1])
with col1:
    st.markdown("### Vegetation (NDVI, MODIS)")
    st.line_chart(df[["NDVI (MODIS)"]])
    st.markdown("### Surface soil moisture (%, SMAP)")
    st.line_chart(df[["Soil Moisture % (SMAP)"]])
with col2:
    st.markdown("### Field Metrics")
    yearly = df.groupby(df.index.year)[["NDVI (MODIS)"]].mean()
    st.metric("Average NDVI", f"{df['NDVI (MODIS)'].mean():.2f}")
    st.metric("Average soil moisture", f"{df['Soil Moisture % (SMAP)'].mean():.1f} %")
    if len(yearly) > 1:
        change = yearly["NDVI (MODIS)"].iloc[-1] - yearly["NDVI (MODIS)"].iloc[0]
        st.metric("NDVI change (first to last year)", f"{change:+.2f}")
    st.info(f"📍 {lat:.4f}°, {lon:.4f}° (5 km around this point)")

st.markdown("### Field Geographic Location")
st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=8)
st.caption("Prototype: rotation scenarios are not available yet.")
