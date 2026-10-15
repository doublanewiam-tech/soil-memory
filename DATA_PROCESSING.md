# Soil Memory: Satellite Data Processing & Architecture

This repository contains the production code and pipeline for Soil Memory, a decision-support dashboard for regional soil health and crop rotation tracking.

## 1. NASA Earth Observation Datasets

Our pipeline integrates multi-spectral satellite remote sensing data to track topsoil health, moisture, and vegetation index:

1. MODIS Vegetation Indices (MOD13Q1 / MOD13A3)
- Metric: Normalized Difference Vegetation Index (NDVI)
- Resolution: 250m grid / 16-day composite
- Role: Measures vegetative vigor, biomass growth, and seasonal soil cover dynamics.

2. SMAP L4 Global Surface Soil Moisture (SPL4SMGP)
- Metric: Volumetric Topsoil Moisture Content (%)
- Resolution: 9km assimilation grid / 3-hour update
- Role: Tracks topsoil water retention and drought stress trajectories.

## 2. Low-Connectivity & Edge Optimization

To ensure the application remains operational in remote agricultural zones or fields with poor internet connection:

- Local Session Caching (@st.cache_data): Query results are cached locally with a TTL (Time-To-Live). Changing UI filters or sliders does not make repeated network requests.
- Fail-Safe Fallback: If API streams experience network latency or rate-limiting, the application seamlessly provides locally calculated baseline vectors without throwing crashes or breaking the dashboard.

## 3. How to Download and Run the App

Prerequisites: Python 3.9+, Anaconda or Miniconda

Setup Instructions:

1. Clone or Download the Repository:
git clone [https://github.com/your-team/soil-memory.git
cd soil-memory](https://github.com/doublanewiam-tech/soil-memory)

2. Install Required Packages:
pip install streamlit pandas numpy earthaccess xarray

3. Configure Secrets:
Create a folder named .streamlit and add a secrets.toml file inside with these lines:
EARTHDATA_USERNAME = "your_nasa_username"
EARTHDATA_PASSWORD = "your_nasa_password"

4. Launch the Dashboard:
python -m streamlit run app.py
