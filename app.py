import io
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Soil Memory", page_icon="🌱", layout="wide")

TEXT = {
    "ar": {
        "title": "🌱 ذاكرة التربة",
        "subtitle": "متابعة صحة التربة بالأقمار الصناعية",
        "field": "اختيار الحقل",
        "region": "المنطقة",
        "years": "الفترة (بالسنوات)",
        "source": "البيانات من أقمار ناسا: MODIS للنباتات وSMAP لرطوبة التربة.",
        "veg": "النباتات",
        "moist": "رطوبة التربة",
        "veg_msgs": {
            "better": "النباتات في تحسّن",
            "same": "النباتات مستقرة",
            "worse": "النباتات في تراجع",
        },
        "moist_msgs": {
            "better": "رطوبة التربة أعلى من المعتاد",
            "same": "رطوبة التربة عادية",
            "worse": "رطوبة التربة أقل من المعتاد، خطر الجفاف",
        },
        "listen": "🔊 استمع إلى النتيجة",
        "audio_fail": "تعذّر تشغيل الصوت الآن. تحقّق من الاتصال بالإنترنت.",
        "need_more": "الفترة المختارة قصيرة. اختر سنتين على الأقل لرؤية الاتجاه.",
        "details": "تفاصيل للمختصين",
        "ndvi_chart": "النباتات (NDVI، قمر MODIS)",
        "moist_chart": "رطوبة سطح التربة (٪، قمر SMAP)",
        "avg_ndvi": "متوسط NDVI",
        "avg_moist": "متوسط رطوبة التربة",
        "location": "الموقع",
        "map": "موقع الحقل على الخريطة",
        "caption": "نموذج أوّلي: عتبات الألوان افتراضية، ورطوبة SMAP تخص الطبقة السطحية فقط. سيناريوهات التناوب الزراعي قادمة.",
        "summary_for": "نتيجة منطقة",
    },
    "en": {
        "title": "🌱 Soil Memory",
        "subtitle": "Satellite-driven soil health tracker",
        "field": "Field selection",
        "region": "Region",
        "years": "Period (years)",
        "source": "Data: NASA MODIS (vegetation) and NASA SMAP L4 (soil moisture).",
        "veg": "Vegetation",
        "moist": "Soil moisture",
        "veg_msgs": {
            "better": "Vegetation is improving",
            "same": "Vegetation is stable",
            "worse": "Vegetation is declining",
        },
        "moist_msgs": {
            "better": "Soil moisture is above usual",
            "same": "Soil moisture is normal",
            "worse": "Soil moisture is below usual, drought risk",
        },
        "listen": "🔊 Listen to the result",
        "audio_fail": "Audio is not available right now. Check your internet connection.",
        "need_more": "The selected period is short. Choose at least 2 years to see a trend.",
        "details": "Details for specialists",
        "ndvi_chart": "Vegetation (NDVI, MODIS)",
        "moist_chart": "Surface soil moisture (%, SMAP)",
        "avg_ndvi": "Average NDVI",
        "avg_moist": "Average soil moisture",
        "location": "Location",
        "map": "Field location on the map",
        "caption": "Prototype: color thresholds are assumptions, and SMAP moisture covers the surface layer only. Crop rotation scenarios are coming.",
        "summary_for": "Result for",
    },
}

REGION_AR = {
    "El Gharb (Morocco)": "الغرب",
    "Tadla (Morocco)": "تادلة",
    "Doukkala (Morocco)": "دكالة",
    "El Haouz (Morocco)": "الحوز",
    "Souss (Morocco)": "سوس",
}

LIGHT = {"better": "🟢", "same": "🟡", "worse": "🔴"}


def light(delta, threshold):
    if delta > threshold:
        return "better"
    if delta < -threshold:
        return "worse"
    return "same"


@st.cache_data
def load_data():
    return pd.read_csv("regions.csv", parse_dates=["Date"]).dropna()


@st.cache_data
def make_audio(text, lang_code):
    from gtts import gTTS

    buf = io.BytesIO()
    gTTS(text=text, lang=lang_code).write_to_fp(buf)
    return buf.getvalue()


# ---------- Language ----------
choice = st.sidebar.radio("اللغة / Language", ["العربية", "English"])
lang = "ar" if choice == "العربية" else "en"
T = TEXT[lang]

if lang == "ar":
    st.markdown(
        """<style>
        .block-container, [data-testid="stSidebar"] {direction: rtl; text-align: right;}
        </style>""",
        unsafe_allow_html=True,
    )

st.title(T["title"])
st.subheader(T["subtitle"])

# ---------- Data ----------
all_data = load_data()
st.sidebar.header(T["field"])


def region_label(name):
    return REGION_AR.get(name, name) if lang == "ar" else name


region = st.sidebar.selectbox(
    T["region"], sorted(all_data["Region"].unique()), format_func=region_label
)
data = all_data[all_data["Region"] == region].set_index("Date")
lat, lon = data["Lat"].iloc[0], data["Lon"].iloc[0]

y_min, y_max = int(data.index.year.min()), int(data.index.year.max())
years = st.sidebar.slider(T["years"], y_min, y_max, (y_min, y_max))
df = data[(data.index.year >= years[0]) & (data.index.year <= years[1])]

st.success(T["source"])

# ---------- Traffic lights ----------
if len(df) >= 24:
    recent, earlier = df.iloc[-12:], df.iloc[:-12]
    d_veg = recent["NDVI (MODIS)"].mean() - earlier["NDVI (MODIS)"].mean()
    d_moist = (
        recent["Soil Moisture % (SMAP)"].mean()
        - earlier["Soil Moisture % (SMAP)"].mean()
    )
    s_veg = light(d_veg, 0.02)
    s_moist = light(d_moist, 2.0)

    c1, c2 = st.columns(2)
    for col, label, status, msg in [
        (c1, T["veg"], s_veg, T["veg_msgs"][light(d_veg, 0.02)]),
        (c2, T["moist"], s_moist, T["moist_msgs"][light(d_moist, 2.0)]),
    ]:
        with col:
            st.markdown(f"#### {label}")
            st.markdown(
                f"<div style='font-size:72px;line-height:1.1'>{LIGHT[status]}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(f"**{msg}**")

    summary = (
        f"{T['summary_for']} {region_label(region)}. "
        f"{T['veg_msgs'][s_veg]}. {T['moist_msgs'][s_moist]}."
    )
    if st.button(T["listen"]):
        try:
            st.audio(make_audio(summary, lang), format="audio/mp3")
        except Exception:
            st.warning(T["audio_fail"])
else:
    st.info(T["need_more"])

# ---------- Details ----------
with st.expander(T["details"]):
    st.markdown(f"**{T['ndvi_chart']}**")
    st.line_chart(df[["NDVI (MODIS)"]])
    st.markdown(f"**{T['moist_chart']}**")
    st.line_chart(df[["Soil Moisture % (SMAP)"]])
    m1, m2 = st.columns(2)
    m1.metric(T["avg_ndvi"], f"{df['NDVI (MODIS)'].mean():.2f}")
    m2.metric(T["avg_moist"], f"{df['Soil Moisture % (SMAP)'].mean():.1f} %")
    st.info(f"📍 {T['location']}: {lat:.4f}, {lon:.4f}")

st.markdown(f"### {T['map']}")
st.map(pd.DataFrame({"lat": [lat], "lon": [lon]}), zoom=8)
st.caption(T["caption"])
