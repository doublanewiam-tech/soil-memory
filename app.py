import streamlit as st
import pandas as pd

st.set_page_config(page_title="Soil Memory", page_icon="🌱", layout="wide")

st.title("🌱 Soil Memory Profile")
st.subheader("Satellite-driven soil health tracker")


@st.cache_data
def load_data():
    df = pd.read_csv("doukkala.csv", parse_dates=["Date"])
    return df.dropna().set_index("Date")


data = load_data()

st.sidebar.header("Field Selection")
st.sidebar.write("Region: **Doukkala Plain (Morocco)**")
st.sidebar.caption("Real data for this region. More regions coming soon.")

min_year = int(data.index.year.min())
max_year = int(data.index.year.max())
years = st.sidebar.slider(
    "Historical Baseline (Years)", min_year, max_year, (min_year, max_year)
)

df = data[(data.index.year >= years[0]) & (data.index.year <= years[1])]

st.success("Data source: NASA MODIS MOD13Q1 (NDVI) and NASA SMAP L4 (soil moisture), via Google Earth Engine.")

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown("### Vegetation (NDVI, MODIS)")
    st.line_chart(df[["NDVI (MODIS)"]])
    st.markdown("### Surface soil moisture (%, SMAP)")
    st.line_chart(df[["Soil Moisture % (SMAP)"]])

with col2:
    st.markdown("### Field Metrics")
    yearly = df.groupby(df.index.year).mean()
    st.metric("Average NDVI", f"{df['NDVI (MODIS)'].mean():.2f}")
    st.metric("Average soil moisture", f"{df['Soil Moisture % (SMAP)'].mean():.1f} %")
    if len(yearly) > 1:
        change = yearly["NDVI (MODIS)"].iloc[-1] - yearly["NDVI (MODIS)"].iloc[0]
        st.metric("NDVI change (first to last year)", f"{change:+.2f}")
    st.info("📍 Location: 32.6167°N, -8.4833°E (5 km around this point)")

st.markdown("### Field Geographic Location")
st.map(pd.DataFrame({"lat": [32.6167], "lon": [-8.4833]}), zoom=8)

st.caption(
    "Prototype: rotation scenarios are not available yet. "
    "Soil moisture is surface moisture (top ~5 cm), not carbon."
)
