import io
import math
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="Soil Memory", page_icon="🌱", layout="wide")

SAT = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
LABELS = "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"


# ---------- Crop assumptions (ILLUSTRATIVE, to be reviewed by an agronomist) ----------
# om / n = yearly change of the organic matter / nitrogen index (index points)
# water = 0 low, 1 medium, 2 high water demand
def mk(group, om, n, water, ar, en, perennial=False):
    return dict(group=group, om=om, n=n, water=water, ar=ar, en=en, perennial=perennial)


CROPS = {
    # Cereals
    "wheat": mk("grass", 0.0, -3.0, 1, "🌾 القمح الطري", "🌾 Soft wheat"),
    "durum": mk("grass", 0.0, -3.0, 1, "🌾 القمح الصلب", "🌾 Durum wheat"),
    "barley": mk("grass", 0.0, -2.5, 0, "🌾 الشعير", "🌾 Barley"),
    "rice": mk("grass", 0.5, -3.0, 2, "🌾 الأرز", "🌾 Rice"),
    "maize": mk("grass", 0.5, -4.0, 2, "🌽 الذرة", "🌽 Maize"),
    # Vegetables
    "tomato": mk("solanaceae", -1.0, -3.0, 2, "🍅 الطماطم", "🍅 Tomato"),
    "pepper": mk("solanaceae", -1.0, -3.0, 2, "🌶️ الفلفل", "🌶️ Pepper"),
    "potato": mk("solanaceae", -2.0, -3.0, 2, "🥔 البطاطس", "🥔 Potato"),
    "onion": mk("allium", -1.5, -2.0, 1, "🧅 البصل", "🧅 Onion"),
    "carrot": mk("carrot", -1.5, -2.0, 1, "🥕 الجزر", "🥕 Carrot"),
    "pumpkin": mk("cucurbit", -0.5, -2.0, 1, "🎃 القرع الأحمر", "🎃 Red pumpkin"),
    "zucchini": mk("cucurbit", -0.5, -2.0, 1, "🥒 القرع الأخضر ", "🥒 Zucchini"),
    "watermelon": mk("cucurbit", -1.0, -2.0, 1, "🍉 البطيخ الأحمر ", "🍉 Watermelon"),
    "melon": mk("cucurbit", -1.0, -2.0, 1, "🍈 البطيخ الأصفر)", "🍈 Melon"),
    # Legumes
    "lentil": mk("legume", 0.5, 4.0, 0, "🫘 العدس", "🫘 Lentil"),
    "faba": mk("legume", 1.0, 5.0, 1, "🫘 الفول", "🫘 Faba bean"),
    "chickpea": mk("legume", 0.5, 4.0, 0, "🫘 الحمص", "🫘 Chickpea"),
    "peas": mk("legume", 0.5, 4.0, 1, "🫛 البازلاء", "🫛 Peas"),
    "alfalfa": mk("legume", 3.0, 6.0, 2, "🌿 البرسيم الحجازي (الفصة)", "🌿 Alfalfa"),
    # Industrial and forage crops
    "sugarbeet": mk("beet", -1.0, -2.0, 2, "🌱 الشمندر السكري", "🌱 Sugar beet"),
    "sugarcane": mk("grass", 0.5, -3.0, 2, "🌱 قصب السكر", "🌱 Sugarcane"),
    "forage_maize": mk("grass", -0.5, -4.0, 2, "🌽 الذرة العلفية", "🌽 Forage maize"),
    "sunflower": mk("sunflower", 0.0, -2.0, 1, "🌻 دوار الشمس", "🌻 Sunflower"),
    # Tree crops (permanent, not rotated)
    "olive": mk("olive", 0.8, 0.0, 0, "🫒 الزيتون (شجرة دائمة)", "🫒 Olive (permanent tree)", True),
    "lemon": mk("citrus", 0.8, -1.0, 2, "🍋 الليمون (شجرة دائمة)", "🍋 Lemon (permanent tree)", True),
    "mandarin": mk("citrus", 0.8, -1.0, 2, "🍊 المندرين (شجرة دائمة)", "🍊 Mandarin (permanent tree)", True),
    "orange": mk("citrus", 0.8, -1.0, 2, "🍊 البرتقال (شجرة دائمة)", "🍊 Orange (permanent tree)", True),
    "apple": mk("rosaceae", 0.8, -1.0, 2, "🍎 التفاح (شجرة دائمة)", "🍎 Apple (permanent tree)", True),
    "peach": mk("rosaceae", 0.6, -1.0, 2, "🍑 الخوخ (شجرة دائمة)", "🍑 Peach (permanent tree)", True),
    "almond": mk("rosaceae", 0.6, -0.5, 1, "🌰 اللوز (شجرة دائمة)", "🌰 Almond (permanent tree)", True),
    "pomegranate": mk("pomegranate", 0.6, -0.5, 1, "🔴 الرمان (شجرة دائمة)", "🔴 Pomegranate (permanent tree)", True),
    "date": mk("date", 0.5, 0.0, 1, "🌴 النخيل (التمر)", "🌴 Date palm", True),
    "grape": mk("grape", 0.5, -0.5, 1, "🍇 العنب (كرمة دائمة)", "🍇 Grapevine (permanent)", True),

}
GROUPS = {
    "grass": ("عائلة القمح والذرة (النجيليات)", "Wheat and maize family (grasses)"),
    "legume": ("عائلة العدس والفول (البقوليات)", "Lentil and bean family (legumes)"),
    "solanaceae": ("عائلة الطماطم والبطاطس", "Tomato and potato family"),
    "allium": ("عائلة البصل والثوم", "Onion and garlic family"),
    "carrot": ("عائلة الجزر", "Carrot family"),
    "cucurbit": ("عائلة القرع والبطيخ", "Squash and melon family"),
    "beet": ("عائلة الشمندر", "Beet family"),
    "sunflower": ("عائلة دوار الشمس", "Sunflower family"),
    "olive": ("شجرة الزيتون", "Olive tree"),
    "citrus": ("أشجار الحمضيات", "Citrus trees"),
    "rosaceae": ("أشجار التفاح والخوخ واللوز", "Apple, peach and almond trees"),
    "pomegranate": ("شجرة الرمان", "Pomegranate tree"),
    "date": ("نخيل التمر", "Date palm"),
    "grape": ("الكرمة (العنب)", "Grapevine"),
}
WATER_LEVEL = {0: ("منخفض", "Low"), 1: ("متوسط", "Medium"), 2: ("مرتفع", "High")}

# ---------- Regional suitability (provided by the team; lemon and orange copy mandarin) ----------
COND = {
    "ok": ("يمكن", "Possible"),
    "irr": ("مشروط بالري", "Needs irrigation"),
    "irr_ok": ("يمكن مع الري", "Possible with irrigation"),
    "water": ("مشروط بالماء", "Depends on water availability"),
    "water_strict": ("مشروط بشدة بالماء", "Strongly depends on water availability"),
    "water_ok": ("يمكن، مع مراعاة قيود الماء", "Possible, mind the water limits"),
    "rain": ("مشروط بالأمطار", "Depends on rainfall"),
    "season": ("مشروط بالموسم", "Depends on the season"),
    "site": ("مشروط بالموقع", "Depends on location"),
    "site_cold": ("مشروط بالموقع والبرودة", "Depends on location and cold"),
    "good_zones": ("يمكن في المناطق المناسبة", "Possible in suitable areas"),
    "alt_cold": ("مشروط بالارتفاع والبرودة", "Depends on altitude and cold"),
    "cold": ("مشروط بالبرودة", "Depends on cold"),
    "site_heat": ("مشروط بالموقع والحرارة", "Depends on location and heat"),
    "cond": ("مشروط", "Conditional"),
    "variety_site": ("مشروط بالصنف والموقع", "Depends on variety and location"),
    "irr_heat": ("مشروط بالري والحرارة", "Needs irrigation and heat"),
    "no": ("غير ملائم غالبًا", "Mostly unsuitable"),
}
ALL_OK = ("ok",) * 5
CITRUS = ("irr", "irr", "ok", "irr", "ok")
PULSE = ("ok", "ok", "rain", "ok", "ok")
# order: Doukkala, Tadla, Souss, El Haouz, El Gharb
SUIT = {
    "wheat": ALL_OK, "durum": ALL_OK, "barley": ALL_OK,
    "rice": ("irr", "irr", "no", "no", "irr_ok"),
    "maize": ("irr", "irr_ok", "irr", "irr", "ok"),
    "tomato": ALL_OK, "pepper": ALL_OK, "potato": ALL_OK, "onion": ALL_OK,
    "carrot": ALL_OK, "pumpkin": ALL_OK, "zucchini": ALL_OK,
    "watermelon": ("water", "water", "water", "water", "water_ok"),
    "melon": ALL_OK,
    "lentil": PULSE, "faba": PULSE, "chickpea": PULSE,
    "peas": ("ok", "ok", "season", "ok", "ok"),
    "alfalfa": ("irr", "irr_ok", "water_strict", "water_strict", "irr_ok"),
    "sugarbeet": ("irr_ok", "irr_ok", "water", "irr_ok", "irr_ok"),
    "sugarcane": ("no", "no", "no", "no", "irr_heat"),
    "forage_maize": ("irr", "irr_ok", "water", "water", "irr_ok"),
    "sunflower": ALL_OK, "olive": ALL_OK,
    "mandarin": CITRUS, "lemon": CITRUS, "orange": CITRUS,
    "apple": ("site_cold", "good_zones", "alt_cold", "alt_cold", "cold"),
    "peach": ("ok", "ok", "variety_site", "ok", "ok"),
    "almond": ALL_OK, "pomegranate": ALL_OK,
    "date": ("site_heat", "cond", "site", "site", "no"),
    "grape": ALL_OK,
}
REG_IDX = {
    "Doukkala (Morocco)": 0,
    "Tadla (Morocco)": 1,
    "Souss (Morocco)": 2,
    "El Haouz (Morocco)": 3,
    "El Gharb (Morocco)": 4,
}


def level_icon(code):
    if code == "ok":
        return "🟢"
    if code == "no":
        return "🔴"
    return "🟡"


TEXT = {
    "ar": {
        "title": "🌱 ذاكرة التربة",
        "subtitle": "متابعة صحة التربة بالأقمار الصناعية",
        "field": "اختيار الحقل",
        "region": "المنطقة",
        "years": "الفترة (بالسنوات)",
        "source": "البيانات من أقمار ناسا: MODIS للنباتات وSMAP لرطوبة التربة.",
        "map": "اختر حقلك على الخريطة (صورة الأقمار الصناعية)",
        "map_hint": "اضغط على موقع حقلك في الخريطة",
        "nearest": "أقرب منطقة",
        "distance": "تبعد",
        "km": "كم",
        "far_warn": "حقلك بعيد عن أقرب نقطة بيانات، لذلك النتيجة تقريبية.",
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
        "caption": "نموذج أوّلي: عتبات الألوان افتراضية، ورطوبة SMAP تخص الطبقة السطحية فقط، والنتيجة خاصة بأقرب نقطة بيانات وليست بالحقل بالضبط.",
        "summary_for": "نتيجة منطقة",
        "tab_now": "📊 الوضع الحالي",
        "tab_sim": "🔄 تجربة التناوب الزراعي",
        "sim_title": "جرّب خطتين للتناوب الزراعي وقارن بينهما",
        "sim_intro": "اختر ثلاثة محاصيل لكل خطة (سنة بعد سنة). تتكرر الخطة لمدة ٦ سنوات.",
        "plan_a": "الخطة أ",
        "plan_b": "الخطة ب",
        "year_n": "السنة {}",
        "show_all": "إظهار المحاصيل غير الملائمة لهذه المنطقة",
        "suit_note": "الإمكانية الزراعية تقدير عام حسب المنطقة. كلمة «يمكن» لا تعني أن المحصول يناسب الري المكثف، فبعض المحاصيل (كالبطيخ والفصة وبعض الأشجار) تستهلك ماءً كثيرًا. راجع مرشدًا فلاحيًا قبل القرار.",
        "om_chart": "مؤشر المادة العضوية في التربة (١٠٠ = اليوم)",
        "n_chart": "مؤشر النيتروجين في التربة (١٠٠ = اليوم)",
        "irr": "ضغط الري (٠ منخفض، ٢ مرتفع)",
        "disease": "تحذير: تكرار نفس العائلة النباتية في سنتين متتاليتين يرفع خطر الأمراض والآفات. عدد المرات:",
        "no_disease": "لا يوجد تكرار لنفس العائلة النباتية. هذا جيد لتقليل الأمراض.",
        "verdict_title": "النتيجة",
        "verdicts": {
            "better": "الخطة ب أفضل للتربة من الخطة أ",
            "same": "الخطتان متقاربتان في أثرهما على التربة",
            "worse": "الخطة أ أفضل للتربة من الخطة ب",
        },
        "assump_title": "افتراضات المحاصيل (للمختصين)",
        "assump_note": "هذه الأرقام تقديرية مبنية على مبادئ عامة في علم المحاصيل، وليست قياسات. يجب أن يراجعها مهندس زراعي. المؤشرات نسبية وليست نسبة الكربون الحقيقية. لا يشمل النموذج المردود ولا الربح.",
        "col_crop": "المحصول",
        "col_group": "العائلة",
        "col_om": "أثر المادة العضوية سنويًا",
        "col_n": "أثر النيتروجين سنويًا",
        "col_water": "الحاجة للماء",
        "sim_caption": "تقدير يعتمد على افتراضات، وليس قياسًا فعليًا. بيانات الأقمار الصناعية للمنطقة تؤثر فقط في ضغط الري.",
        "orchard_note": "الأشجار المثمرة تبقى في الحقل سنوات طويلة ولا تدخل في التناوب. لذلك تفترض الخطة زراعة {} كل سنة.",
        "dry_note": "المنطقة أكثر جفافًا من المتوسط، لذلك يزداد ضغط الري.",
    },
    "en": {
        "title": "🌱 Soil Memory",
        "subtitle": "Satellite-driven soil health tracker",
        "field": "Field selection",
        "region": "Region",
        "years": "Period (years)",
        "source": "Data: NASA MODIS (vegetation) and NASA SMAP L4 (soil moisture).",
        "map": "Select your field on the map (satellite view)",
        "map_hint": "Tap your field's location on the map",
        "nearest": "Nearest region",
        "distance": "distance",
        "km": "km",
        "far_warn": "Your field is far from the nearest data point, so the result is approximate.",
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
        "caption": "Prototype: color thresholds are assumptions, SMAP moisture covers the surface layer only, and the result is for the nearest data point, not the exact field.",
        "summary_for": "Result for",
        "tab_now": "📊 Current status",
        "tab_sim": "🔄 Crop rotation test",
        "sim_title": "Try two crop rotation plans and compare them",
        "sim_intro": "Pick three crops for each plan (year by year). The plan repeats over 6 years.",
        "plan_a": "Plan A",
        "plan_b": "Plan B",
        "year_n": "Year {}",
        "show_all": "Show crops that are unsuitable for this region",
        "suit_note": "Regional suitability is a general estimate. \"Possible\" does not mean a crop suits intensive irrigation: some crops (watermelon, alfalfa, some trees) use a lot of water. Consult a farm advisor before deciding.",
        "om_chart": "Soil organic matter index (100 = today)",
        "n_chart": "Soil nitrogen index (100 = today)",
        "irr": "Irrigation pressure (0 low, 2 high)",
        "disease": "Warning: the same plant family in two consecutive years raises disease and pest risk. Times:",
        "no_disease": "No repeated plant family in a row. Good for reducing diseases.",
        "verdict_title": "Result",
        "verdicts": {
            "better": "Plan B is better for the soil than Plan A",
            "same": "Both plans have a similar effect on the soil",
            "worse": "Plan A is better for the soil than Plan B",
        },
        "assump_title": "Crop assumptions (for specialists)",
        "assump_note": "These numbers are estimates based on general crop science principles, not measurements. An agronomist should review them. The indices are relative, not real carbon percentages. The model does not include yield or profit.",
        "col_crop": "Crop",
        "col_group": "Family",
        "col_om": "Organic matter effect per year",
        "col_n": "Nitrogen effect per year",
        "col_water": "Water need",
        "sim_caption": "An estimate based on assumptions, not a measurement. The region's satellite data only affects irrigation pressure.",
        "orchard_note": "Tree crops stay in the field for many years and are not rotated, so this plan uses {} every year.",
        "dry_note": "This region is drier than average, so irrigation pressure is higher.",
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


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(a))


def simulate(plan, horizon=6):
    om, n = 100.0, 100.0
    rows = [{"Year": 0, "om": om, "n": n}]
    for y in range(horizon):
        cur, prev = plan[y % 3], plan[(y - 1) % 3]
        c, p = CROPS[cur], CROPS[prev]
        d_om, d_n = c["om"], c["n"]
        if p["group"] == "legume" and c["group"] != "legume":
            d_n += 2.0  # nitrogen credit after a legume
        if cur == prev and cur != "fallow" and not c["perennial"]:
            d_om -= 0.5  # same crop twice in a row
            d_n -= 1.0
        om += d_om
        n += d_n
        rows.append({"Year": y + 1, "om": om, "n": n})
    return pd.DataFrame(rows).set_index("Year")


def disease_count(plan):
    count = 0
    for i in range(3):
        a, b = CROPS[plan[i]], CROPS[plan[(i + 1) % 3]]
        if a["perennial"] or b["perennial"]:
            continue
        if a["group"] == b["group"] and a["group"] != "fallow":
            count += 1
    return count


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
li = 0 if lang == "ar" else 1

if lang == "ar":
    st.markdown(
        """<style>
        .block-container, [data-testid="stSidebar"] {direction: rtl; text-align: right;}
        </style>""",
        unsafe_allow_html=True,
    )

st.title(T["title"])
st.subheader(T["subtitle"])

# ---------- Data and region ----------
all_data = load_data()
points = all_data.groupby("Region")[["Lat", "Lon"]].first()
options = sorted(all_data["Region"].unique())


def region_label(name):
    return REGION_AR.get(name, name) if lang == "ar" else name


if st.session_state.get("region_name") not in options:
    st.session_state.region_name = options[0]

st.sidebar.header(T["field"])
region = st.sidebar.selectbox(
    T["region"],
    options,
    index=options.index(st.session_state.region_name),
    format_func=region_label,
)
st.session_state.region_name = region

data = all_data[all_data["Region"] == region].set_index("Date")
lat, lon = data["Lat"].iloc[0], data["Lon"].iloc[0]

y_min, y_max = int(data.index.year.min()), int(data.index.year.max())
years = st.sidebar.slider(T["years"], y_min, y_max, (y_min, y_max))
df = data[(data.index.year >= years[0]) & (data.index.year <= years[1])]

# ---------- Satellite map with click ----------
st.markdown(f"### {T['map']}")
st.caption(T["map_hint"])

m = folium.Map(location=[32.0, -7.0], zoom_start=6, tiles=None)
folium.TileLayer(tiles=SAT, attr="Esri, Maxar, Earthstar Geographics", name="Satellite").add_to(m)
folium.TileLayer(tiles=LABELS, attr="Esri", name="Labels", overlay=True).add_to(m)

for name, row in points.iterrows():
    folium.Marker(
        [row["Lat"], row["Lon"]],
        tooltip=region_label(name),
        icon=folium.Icon(color="green" if name == region else "blue"),
    ).add_to(m)
folium.Circle([lat, lon], radius=5000, color="yellow", weight=2).add_to(m)

last = st.session_state.get("last_click")
if last:
    folium.Marker(
        [last["lat"], last["lng"]], icon=folium.Icon(color="red", icon="home")
    ).add_to(m)

out = st_folium(m, height=450, use_container_width=True, key="map", returned_objects=["last_clicked"])

new = out.get("last_clicked") if out else None
if new and new != st.session_state.get("last_click"):
    st.session_state.last_click = new
    dists = {
        n: haversine(new["lat"], new["lng"], r["Lat"], r["Lon"])
        for n, r in points.iterrows()
    }
    nearest = min(dists, key=dists.get)
    st.session_state.click_region = nearest
    st.session_state.click_km = dists[nearest]
    st.session_state.region_name = nearest
    st.rerun()

if st.session_state.get("click_region") == region and "click_km" in st.session_state:
    km = st.session_state.click_km
    st.info(f"📍 {T['nearest']}: {region_label(region)} ({T['distance']} {km:.0f} {T['km']})")
    if km > 50:
        st.warning(T["far_warn"])

st.success(T["source"])

tab_now, tab_sim = st.tabs([T["tab_now"], T["tab_sim"]])

# =====================  TAB 1: CURRENT STATUS  =====================
with tab_now:
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
            (c1, T["veg"], s_veg, T["veg_msgs"][s_veg]),
            (c2, T["moist"], s_moist, T["moist_msgs"][s_moist]),
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
        if st.button(T["listen"], key="listen_now"):
            try:
                st.audio(make_audio(summary, lang), format="audio/mp3")
            except Exception:
                st.warning(T["audio_fail"])
    else:
        st.info(T["need_more"])

    with st.expander(T["details"]):
        st.markdown(f"**{T['ndvi_chart']}**")
        st.line_chart(df[["NDVI (MODIS)"]])
        st.markdown(f"**{T['moist_chart']}**")
        st.line_chart(df[["Soil Moisture % (SMAP)"]])
        m1, m2 = st.columns(2)
        m1.metric(T["avg_ndvi"], f"{df['NDVI (MODIS)'].mean():.2f}")
        m2.metric(T["avg_moist"], f"{df['Soil Moisture % (SMAP)'].mean():.1f} %")
        st.info(f"📍 {T['location']}: {lat:.4f}, {lon:.4f}")

# =====================  TAB 2: ROTATION SIMULATOR  =====================
with tab_sim:
    st.markdown(f"### {T['sim_title']}")
    st.write(T["sim_intro"])

    reg_idx = REG_IDX.get(region)

    def suit(k):
        if k == "fallow" or reg_idx is None or k not in SUIT:
            return "ok"
        return SUIT[k][reg_idx]

    show_all = st.checkbox(T["show_all"], key="show_all")
    crop_keys = [k for k in CROPS if show_all or suit(k) != "no"]

    def crop_label(k):
        return f"{level_icon(suit(k))} {CROPS[k][lang]}"

    defaults = {
        "a": ["wheat", "wheat", "wheat"],
        "b": ["wheat", "faba", "sunflower"],
    }
    plans = {}
    colA, colB = st.columns(2)
    for col, pid, title in [(colA, "a", T["plan_a"]), (colB, "b", T["plan_b"])]:
        with col:
            st.markdown(f"#### {title}")
            picks = []
            for i in range(3):
                picks.append(
                    st.selectbox(
                        T["year_n"].format(i + 1),
                        crop_keys,
                        index=crop_keys.index(defaults[pid][i]),
                        format_func=crop_label,
                        key=f"{pid}{i}_{region}_{int(show_all)}",
                    )
                )
            plans[pid] = picks

    # Suitability warnings for the chosen crops
    for pid, title in [("a", T["plan_a"]), ("b", T["plan_b"])]:
        for c in dict.fromkeys(plans[pid]):
            code = suit(c)
            if code != "ok":
                msg = f"{level_icon(code)} {title} - {CROPS[c][lang]}: {COND[code][li]}"
                if code == "no":
                    st.error(msg)
                else:
                    st.warning(msg)
    st.caption(T["suit_note"])

    # Tree crops are permanent: they replace the whole rotation
    for pid, title in [("a", T["plan_a"]), ("b", T["plan_b"])]:
        tree = next((c for c in plans[pid] if CROPS[c]["perennial"]), None)
        if tree:
            st.info(f"{title}: {T['orchard_note'].format(CROPS[tree][lang])}")
            plans[pid] = [tree] * 3

    sim_a, sim_b = simulate(plans["a"]), simulate(plans["b"])

    st.markdown(f"**{T['om_chart']}**")
    st.line_chart(pd.DataFrame({T["plan_a"]: sim_a["om"], T["plan_b"]: sim_b["om"]}))
    st.markdown(f"**{T['n_chart']}**")
    st.line_chart(pd.DataFrame({T["plan_a"]: sim_a["n"], T["plan_b"]: sim_b["n"]}))

    # Irrigation pressure uses the region's REAL satellite moisture
    all_mean = all_data["Soil Moisture % (SMAP)"].mean()
    region_mean = data["Soil Moisture % (SMAP)"].mean()
    mult = min(1.5, max(0.8, all_mean / region_mean))

    def irrigation(plan):
        return sum(CROPS[c]["water"] for c in plan) / 3 * mult

    i1, i2 = st.columns(2)
    i1.metric(f"{T['plan_a']} - {T['irr']}", f"{irrigation(plans['a']):.2f}")
    i2.metric(f"{T['plan_b']} - {T['irr']}", f"{irrigation(plans['b']):.2f}")
    if mult > 1.05:
        st.caption(T["dry_note"])

    for pid, title in [("a", T["plan_a"]), ("b", T["plan_b"])]:
        cnt = disease_count(plans[pid])
        if cnt > 0:
            st.warning(f"{title}: {T['disease']} {cnt}")
        else:
            st.success(f"{title}: {T['no_disease']}")

    score_a = (sim_a["om"].iloc[-1] - 100) + (sim_a["n"].iloc[-1] - 100)
    score_b = (sim_b["om"].iloc[-1] - 100) + (sim_b["n"].iloc[-1] - 100)
    verdict_key = light(score_b - score_a, 2.0)
    st.markdown(f"### {T['verdict_title']}")
    st.markdown(
        f"<div style='font-size:60px;line-height:1.1'>{LIGHT[verdict_key]}</div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"**{T['verdicts'][verdict_key]}**")

    if st.button(T["listen"], key="listen_sim"):
        try:
            st.audio(make_audio(T["verdicts"][verdict_key], lang), format="audio/mp3")
        except Exception:
            st.warning(T["audio_fail"])

    with st.expander(T["assump_title"]):
        st.write(T["assump_note"])
        table = pd.DataFrame(
            [
                {
                    T["col_crop"]: CROPS[k][lang],
                    T["col_group"]: GROUPS[CROPS[k]["group"]][li],
                    T["col_om"]: CROPS[k]["om"],
                    T["col_n"]: CROPS[k]["n"],
                    T["col_water"]: WATER_LEVEL[CROPS[k]["water"]][li],
                }
                for k in CROPS
            ]
        )
        st.dataframe(table, hide_index=True, use_container_width=True)

    st.caption(T["sim_caption"])

st.caption(T["caption"])
