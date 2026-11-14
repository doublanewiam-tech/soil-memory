# 🌱 Soil Memory

**Satellite-driven soil health and crop-rotation planner for Moroccan farmers, in Arabic and English.**
NASA Space Apps Challenge 2026 · Team SoilSat

[How it works](#how-it-works) · [Limitations](#limitations) · [Run locally](#run-locally)

---

## The problem

Soil degradation is slow and invisible. A farmer sees this year's yield, but not that vegetation is gradually declining, that soil is drying out, or that repeating the same crop is draining organic matter and nitrogen. By the time it is visible, it is expensive to reverse.

Satellite data exists, but it is built for scientists, not for a farmer with a phone and a few minutes.

## What Soil Memory does

A farmer taps their field on a satellite map and gets two things in plain language:

1. **Is my land getting better or worse?** Two traffic lights (vegetation and soil moisture) computed from years of NASA satellite data, with the result read aloud.
2. **Which crop rotation is better for my soil?** Two three-crop rotation plans are compared side by side over 6 years, with warnings for crops that are unsuitable for the region, repeated plant families (disease risk) and irrigation pressure.

| Tab | Question it answers |
|---|---|
| **Current status** | Has vegetation (NDVI) improved or declined in the last 12 months compared with earlier years? Is soil moisture above or below usual? |
| **Crop rotation test** | How do Plan A and Plan B compare for soil organic matter, soil nitrogen, irrigation pressure and disease risk in this region? |

### Built for the field

- **Arabic first.** Full Arabic and English UI, with right-to-left layout for Arabic.
- **Voice output.** A "Listen to the result" button reads the verdict aloud, for farmers who prefer listening to reading.
- **Traffic lights, not charts.** 🟢 🟡 🔴 results up front. Charts and numbers are in a "Details for specialists" section.
- **Tap the map.** Click anywhere on satellite imagery. The app finds the nearest data point and warns when it is more than 50 km away.
- **Local crop list.** 33 crops (cereals, vegetables, legumes, forage, trees, vines). Each is marked 🟢 / 🟡 / 🔴 for suitability in the selected region, with the reason (irrigation, cold, water availability, etc.).
- **Orchards handled correctly.** Tree crops are permanent, so they replace the whole rotation instead of being rotated.

## Real vs simulated

| Component | Status |
|---|---|
| NDVI (vegetation) | ✅ NASA MODIS, stored in `regions.csv` |
| Soil moisture | ✅ NASA SMAP L4 (surface layer), stored in `regions.csv` |
| Current-status traffic lights | ✅ Computed from the satellite series (recent 12 months vs earlier record) |
| Region suitability table | 🟡 Provided by the team; general estimate, not site-specific |
| Rotation model (organic matter, nitrogen, disease, irrigation) | 🟠 Rule-based **scenario model**. Crop effects are illustrative assumptions pending agronomist review |
| Validation against field measurements | 🔴 Not done. See roadmap |

**What satellite data drives in the rotation tab:** the region's measured soil moisture (relative to the average of all regions) scales the irrigation-pressure score. Organic-matter and nitrogen indices come from the crop assumptions table, which is shown in the app and labelled as such.

## How it works

```
 NASA MODIS (NDVI) + NASA SMAP L4 (soil moisture)
                    │   precomputed, one row per region and month
                    ▼
               regions.csv
                    │
        ┌───────────┴─────────────────┐
        ▼                             ▼
  Current status tab           Rotation test tab
  - recent 12 mo vs earlier    - 3-crop plan repeated over 6 years
  - NDVI and moisture lights   - OM and N indices (start = 100)
  - spoken summary             - irrigation pressure (uses satellite moisture)
                               - disease and suitability warnings
        └───────────┬─────────────────┘
                    ▼
        app.py (Streamlit + Folium)
```

Computation is a few hundred rows of pandas, so the app is fast on modest hardware.

### Current status

- Splits the selected period into the **most recent 12 months** and everything earlier.
- **Vegetation** light: change in mean NDVI. Green if above +0.02, red if below −0.02, otherwise yellow.
- **Moisture** light: change in mean soil moisture. Green if above +2 percentage points, red if below −2, otherwise yellow.
- Needs at least 24 months selected to show a trend.
- Thresholds are assumptions for this prototype and will be tuned.

### Rotation model

Each plan is three crops, one per year, repeating for 6 years. Soil organic matter (OM) and nitrogen (N) are tracked as **relative indices starting at 100** (not real percentages).

- Each crop has a yearly OM effect and N effect (for example, alfalfa +3.0 OM / +6 N, potato −2.0 OM / −3 N).
- **Legume credit:** a non-legume crop after a legume gets +2 N.
- **Monoculture penalty:** the same crop two years in a row gets −0.5 OM and −1 N.
- **Disease risk:** counts consecutive years with the same plant family. Tree crops are excluded.
- **Irrigation pressure:** mean crop water need (0 low to 2 high) multiplied by a regional factor from satellite soil moisture (clamped between 0.8 and 1.5). Drier regions raise the score.
- **Verdict:** compares the combined OM + N change between plans. A difference under 2 index points is reported as "similar".

### Regions

Doukkala, Tadla, Souss, El Haouz, El Gharb. Each region is a single data point with one monthly NASA time series.

## Limitations

We would rather state these than have you find them.

- **Scale gap.** One SMAP cell is about 9 km wide. Soil moisture is a regional signal, not a per-field measurement. Results describe the nearest data point, not the exact field.
- **Surface layer only.** SMAP surface moisture does not describe root-zone moisture.
- **Rotation outputs are scenarios, not forecasts.** The OM and N effects per crop are illustrative assumptions based on general crop-science principles. They have not yet been reviewed by an agronomist or calibrated against long-term trial data.
- **Indices, not carbon percentages.** The model does not estimate real soil organic carbon, yield or profit.
- **Suitability is general.** The regional suitability table is a coarse estimate. "Possible" does not mean suitable for intensive irrigation. Farmers should consult a local advisor.
- **Thresholds are untuned.** The traffic-light cutoffs have not been validated against ground truth.
- **Connectivity.** Data ships with the app, but the satellite basemap tiles and text-to-speech (gTTS) need an internet connection. If audio fails, the app shows a message and keeps working.
- **Five regions only.**

## Roadmap

1. Agronomist review and calibration of the crop assumptions against published long-term rotation trials; add uncertainty ranges.
2. Validate the soil-moisture and NDVI trends against in-situ stations (e.g. ISMN) and local ground observations.
3. Draw-your-own-field polygon, with MODIS NDVI sampled at 250 m for the actual field.
4. Add root-zone moisture (SMAP L4) and NASA vegetation productivity products as drivers.
5. More Moroccan regions, then North Africa.
6. French UI; offline audio; downloadable PDF report for agricultural extension agents.

## Run locally

```bash
git clone https://github.com/doublanewiam-tech/soil-memory.git
cd soil-memory
pip install -r requirements.txt   # streamlit, pandas, folium, streamlit-folium, gTTS
streamlit run app.py
```

The app reads `regions.csv` from the repository root. Required columns: `Region`, `Date`, `Lat`, `Lon`, `NDVI (MODIS)`, `Soil Moisture % (SMAP)`.

## Data credits and license

- NASA MODIS vegetation indices (NDVI)
- NASA SMAP L4 soil moisture (NSIDC DAAC)
- Basemap: Esri World Imagery
- Code: MIT License, see [LICENSE](LICENSE). Copyright (c) 2026 SoilSat.

## Team

**SoilSat**: Nidal and Wiam
