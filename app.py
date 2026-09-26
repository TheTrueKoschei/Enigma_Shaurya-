"""Symbiosis Finder - Streamlit interface.

Discovers exchanges where one plant's by-product can replace another's raw
material, scores how practical each one is, and prices it. Every figure on
screen is computed in engine.py; this module only arranges and draws them.
"""

from __future__ import annotations

import io
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import engine
import explain
import kb

st.set_page_config(
    page_title="Symbiosis Finder",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------
# Chart colours.
#
# Marks use the validated dark-surface palette: every pair clears the
# colourblind-separation and normal-vision floors against #0b0e14. The
# supplier/receiver pair and the loss-making line were checked together, since
# they overlap on the map. Loss also carries a dashed line, a legend entry and
# a "Loss" column in the table, so the distinction is never colour alone.
# ----------------------------------------------------------------------
SUPPLIER_COLOUR = "#199e70"      # aqua
RECEIVER_COLOUR = "#c98500"      # yellow
LOSS_COLOUR = "#d03b3b"          # status: critical

# Sequential blue, low to high. On a dark surface the darkest step recedes into
# the background, so near-zero states read as empty rather than as data.
BLUE_SEQUENTIAL = [
    [0.00, "#0d366b"], [0.20, "#184f95"], [0.40, "#256abf"],
    [0.60, "#3987e5"], [0.80, "#5598e7"], [1.00, "#86b6ef"],
]

GEOJSON_PATH = "data/india_states.geojson"

# Industrial locations offered in the "my plant" dropdown, so a user never has
# to look up coordinates. Real cities, real coordinates.
INDUSTRIAL_LOCATIONS = {
    "Ahmedabad, Gujarat": ("Gujarat", 23.0225, 72.5714),
    "Bengaluru, Karnataka": ("Karnataka", 12.9716, 77.5946),
    "Bhopal, Madhya Pradesh": ("Madhya Pradesh", 23.2599, 77.4126),
    "Bhubaneswar, Odisha": ("Odisha", 20.2961, 85.8245),
    "Chennai, Tamil Nadu": ("Tamil Nadu", 13.0827, 80.2707),
    "Coimbatore, Tamil Nadu": ("Tamil Nadu", 11.0168, 76.9558),
    "Delhi": ("Delhi", 28.6139, 77.2090),
    "Durgapur, West Bengal": ("West Bengal", 23.5204, 87.3119),
    "Guwahati, Assam": ("Assam", 26.1445, 91.7362),
    "Hyderabad, Telangana": ("Telangana", 17.3850, 78.4867),
    "Indore, Madhya Pradesh": ("Madhya Pradesh", 22.7196, 75.8577),
    "Jabalpur, Madhya Pradesh": ("Madhya Pradesh", 23.1815, 79.9864),
    "Jaipur, Rajasthan": ("Rajasthan", 26.9124, 75.7873),
    "Jamshedpur, Jharkhand": ("Jharkhand", 22.8046, 86.2029),
    "Kanpur, Uttar Pradesh": ("Uttar Pradesh", 26.4499, 80.3319),
    "Kochi, Kerala": ("Kerala", 9.9312, 76.2673),
    "Kolkata, West Bengal": ("West Bengal", 22.5726, 88.3639),
    "Lucknow, Uttar Pradesh": ("Uttar Pradesh", 26.8467, 80.9462),
    "Ludhiana, Punjab": ("Punjab", 30.9010, 75.8573),
    "Mangaluru, Karnataka": ("Karnataka", 12.9141, 74.8560),
    "Mumbai, Maharashtra": ("Maharashtra", 19.0760, 72.8777),
    "Nagpur, Maharashtra": ("Maharashtra", 21.1458, 79.0882),
    "Nashik, Maharashtra": ("Maharashtra", 19.9975, 73.7898),
    "Patna, Bihar": ("Bihar", 25.5941, 85.1376),
    "Pune, Maharashtra": ("Maharashtra", 18.5204, 73.8567),
    "Raipur, Chhattisgarh": ("Chhattisgarh", 21.2514, 81.6296),
    "Rajkot, Gujarat": ("Gujarat", 22.3039, 70.8022),
    "Ranchi, Jharkhand": ("Jharkhand", 23.3441, 85.3096),
    "Rourkela, Odisha": ("Odisha", 22.2604, 84.8536),
    "Salem, Tamil Nadu": ("Tamil Nadu", 11.6643, 78.1460),
    "Surat, Gujarat": ("Gujarat", 21.1702, 72.8311),
    "Tirupur, Tamil Nadu": ("Tamil Nadu", 11.1085, 77.3411),
    "Vadodara, Gujarat": ("Gujarat", 22.3072, 73.1812),
    "Varanasi, Uttar Pradesh": ("Uttar Pradesh", 25.3176, 82.9739),
    "Visakhapatnam, Andhra Pradesh": ("Andhra Pradesh", 17.6868, 83.2185),
}

STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

:root {
  --bg:        #0b0e14;
  --surface:   #131824;
  --surface-2: #1a2030;
  --line:      rgba(255,255,255,0.07);
  --line-2:    rgba(255,255,255,0.13);
  --text:      #e9edf5;
  --muted:     #8d95a9;
  --accent:    #2bd99b;
  --accent-dk: #199e70;
  --blue:      #5598e7;
  --amber:     #e0a020;
  --red:       #ef5a5a;
  --sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --display: 'Space Grotesk', 'Inter', -apple-system, sans-serif;
}

html, body, [class*="css"], .stApp { font-family: var(--sans); }
.stApp { background:
    radial-gradient(1100px 520px at 12% -8%, rgba(43,217,155,0.075), transparent 62%),
    radial-gradient(900px 460px at 92% -4%, rgba(85,152,231,0.065), transparent 58%),
    var(--bg); }
.block-container { padding-top: 1.6rem; padding-bottom: 4rem; max-width: 1560px; }

/* ---------- animations ---------- */
@keyframes riseIn { from { opacity:0; transform: translateY(14px); } to { opacity:1; transform:none; } }
@keyframes fadeIn { from { opacity:0; } to { opacity:1; } }
@keyframes sweep  { 0% { background-position: -420px 0; } 100% { background-position: 420px 0; } }
@keyframes softPulse { 0%,100% { box-shadow: 0 0 0 0 rgba(43,217,155,0.32); }
                       50%     { box-shadow: 0 0 0 7px rgba(43,217,155,0); } }
@keyframes growBar { from { width: 0; } }

.rise { animation: riseIn .5s cubic-bezier(.22,.9,.3,1) both; }

/* ---------- hero ---------- */
.hero { padding: .5rem 0 1.15rem; animation: riseIn .55s cubic-bezier(.22,.9,.3,1) both; }
.hero h1 { font-family: var(--display); font-size: 2.5rem; font-weight: 700;
  letter-spacing: -.035em; margin: 0 0 .3rem; line-height: 1.04;
  background: linear-gradient(97deg, #ffffff 8%, var(--accent) 52%, var(--blue) 96%);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent; }
.hero .tag { display:inline-block; font-size:.66rem; font-weight:700; letter-spacing:.16em;
  text-transform: uppercase; color: var(--accent); border:1px solid rgba(43,217,155,.32);
  background: rgba(43,217,155,.075); padding:.26rem .6rem; border-radius: 999px;
  margin-bottom:.7rem; }
.hero p { color: var(--muted); font-size: .95rem; max-width: 74ch; margin:0; line-height:1.6; }

/* ---------- KPI tiles ---------- */
.kpis { display:grid; grid-template-columns: repeat(6, 1fr); gap: .7rem; margin: .5rem 0 .7rem; }
@media (max-width: 1200px){ .kpis { grid-template-columns: repeat(2, 1fr); } }
.kpi { position:relative; overflow:hidden; background: linear-gradient(160deg, var(--surface) 0%, rgba(19,24,36,.55) 100%);
  border:1px solid var(--line); border-radius: 14px; padding: .95rem 1.05rem 1rem;
  animation: riseIn .55s cubic-bezier(.22,.9,.3,1) both;
  transition: transform .22s cubic-bezier(.22,.9,.3,1), border-color .22s, box-shadow .22s; }
.kpi:nth-child(1){animation-delay:.03s}.kpi:nth-child(2){animation-delay:.09s}
.kpi:nth-child(3){animation-delay:.15s}.kpi:nth-child(4){animation-delay:.21s}
.kpi:nth-child(5){animation-delay:.27s}.kpi:nth-child(6){animation-delay:.33s}
.kpi:hover { transform: translateY(-3px); border-color: var(--line-2);
  box-shadow: 0 12px 30px -16px rgba(0,0,0,.85); }
.kpi::after { content:""; position:absolute; inset:0 0 auto 0; height:2px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  opacity:.5; background-size: 420px 100%; animation: sweep 5.5s linear infinite; }
.kpi .lab { font-size:.67rem; letter-spacing:.13em; text-transform:uppercase;
  color: var(--muted); font-weight:600; margin-bottom:.42rem; }
.kpi .val { font-family: var(--display); font-size:1.46rem; font-weight:650;
  letter-spacing:-.025em; line-height:1.1; color: var(--text); }
.kpi .sub { font-size:.72rem; color: var(--muted); margin-top:.32rem; }
.kpi .sub.bad { color: var(--red); }

/* ---------- tabs ---------- */
.stTabs [data-baseweb="tab-list"] { gap:.22rem; border-bottom:1px solid var(--line);
  background: transparent; margin-bottom:1.1rem; }
.stTabs [data-baseweb="tab"] { height:auto; padding:.62rem 1.05rem; border-radius:9px 9px 0 0;
  font-weight:600; font-size:.88rem; color: var(--muted); background: transparent;
  transition: color .18s, background .18s; }
.stTabs [data-baseweb="tab"]:hover { color: var(--text); background: rgba(255,255,255,.035); }
.stTabs [aria-selected="true"] { color: var(--accent) !important;
  background: linear-gradient(180deg, rgba(43,217,155,.10), transparent); }
.stTabs [data-baseweb="tab-highlight"] { background: var(--accent); height:2px; }
.stTabs [data-baseweb="tab-panel"] { animation: fadeIn .32s ease both; }

/* ---------- cards ---------- */
.card { background: var(--surface); border:1px solid var(--line); border-radius:14px;
  padding:1.1rem 1.25rem; margin-bottom:.85rem; animation: riseIn .45s cubic-bezier(.22,.9,.3,1) both; }
.card.pad0 { padding:.9rem 1.1rem; }
.sect { font-family: var(--display); font-size:1.06rem; font-weight:600; letter-spacing:-.01em;
  margin:.2rem 0 .55rem; color: var(--text); }
.sub { color: var(--muted); font-size:.85rem; line-height:1.6; margin:0 0 .9rem; }

/* ---------- match rows ---------- */
.mrow { display:flex; align-items:center; gap:.9rem; padding:.72rem .95rem;
  border:1px solid var(--line); border-radius:11px; background: var(--surface);
  margin-bottom:.5rem; animation: riseIn .4s cubic-bezier(.22,.9,.3,1) both;
  transition: transform .2s, border-color .2s, background .2s; }
.mrow:hover { transform: translateX(3px); border-color: var(--line-2); background: var(--surface-2); }
.mrow.best { border-color: rgba(43,217,155,.45);
  background: linear-gradient(100deg, rgba(43,217,155,.09), var(--surface) 55%);
  animation: riseIn .4s cubic-bezier(.22,.9,.3,1) both, softPulse 2.6s ease-out 2; }
.mrow .num { font-family: var(--display); font-size:1rem; font-weight:700; color: var(--muted);
  min-width:2ch; text-align:right; }
.mrow .body { flex:1; min-width:0; }
.mrow .t1 { font-weight:600; font-size:.93rem; color: var(--text);
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.mrow .t2 { font-size:.78rem; color: var(--muted); margin-top:.18rem; }
.mrow .fig { text-align:right; min-width:120px; }
.mrow .fig .n { font-family: var(--display); font-weight:650; font-size:.95rem; }
.mrow .fig .n.pos { color: var(--accent); } .mrow .fig .n.neg { color: var(--red); }
.mrow .fig .k { font-size:.7rem; color: var(--muted); letter-spacing:.05em; text-transform:uppercase; }

.pill { display:inline-block; font-family: var(--display); font-weight:700; font-size:.82rem;
  padding:.24rem .56rem; border-radius:7px; min-width:52px; text-align:center; }
.pill.s1 { color:#0b0e14; background: var(--accent); }
.pill.s2 { color:#0b0e14; background: var(--blue); }
.pill.s3 { color:#0b0e14; background: var(--amber); }
.pill.s4 { color:#fff;    background: #5a6275; }
.chip { display:inline-block; font-size:.66rem; font-weight:700; letter-spacing:.08em;
  text-transform:uppercase; padding:.18rem .44rem; border-radius:5px; margin-left:.4rem; }
.chip.loss { color: var(--red); background: rgba(239,90,90,.13); border:1px solid rgba(239,90,90,.32); }
.chip.best { color: var(--accent); background: rgba(43,217,155,.13); border:1px solid rgba(43,217,155,.32); }
.chip.far  { color: var(--amber); background: rgba(224,160,32,.12); border:1px solid rgba(224,160,32,.3); }

.srow { padding:.5rem .1rem .55rem; border-bottom:1px solid var(--line);
  animation: riseIn .4s cubic-bezier(.22,.9,.3,1) both; }
.srow .sname { font-size:.83rem; font-weight:600; color: var(--text);
  display:inline-block; }
.srow .sval { font-family: var(--display); font-size:.83rem; font-weight:650;
  color: var(--muted); float:right; }
.bar { height:5px; border-radius:99px; background: rgba(255,255,255,.07); overflow:hidden; margin-top:.4rem; }
.bar > i { display:block; height:100%; border-radius:99px; animation: growBar .75s cubic-bezier(.22,.9,.3,1) both; }

/* ---------- narrative ---------- */
.headline { font-size:1rem; line-height:1.58; font-weight:550; padding:.85rem 1.05rem;
  border-left:3px solid var(--accent); background: rgba(43,217,155,.07);
  border-radius:0 8px 8px 0; margin-bottom:1rem; animation: riseIn .4s ease both; }
.headline.loss { border-left-color: var(--red); background: rgba(239,90,90,.07); }
.sec-title { font-size:.7rem; text-transform:uppercase; letter-spacing:.11em; color: var(--muted);
  font-weight:700; margin:.9rem 0 .22rem; }
.sec-body { font-size:.92rem; line-height:1.66; color: var(--text); opacity:.93; margin:0; }
.caveat { font-size:.79rem; color: var(--muted); line-height:1.55; }

/* ---------- widgets ---------- */
.stButton > button { border-radius:10px; font-weight:650; border:1px solid var(--line-2);
  transition: transform .16s, box-shadow .16s, filter .16s; }
.stButton > button:hover { transform: translateY(-1px); filter: brightness(1.07); }
.stButton > button[kind="primary"] { background: linear-gradient(97deg, var(--accent-dk), var(--accent));
  color:#06231a; border:none; box-shadow: 0 6px 18px -8px rgba(43,217,155,.7); }
[data-testid="stMetricValue"] { font-family: var(--display); font-size:1.4rem; font-weight:650; }
[data-testid="stMetricLabel"] { font-size:.7rem; text-transform:uppercase; letter-spacing:.1em;
  color: var(--muted); }
div[data-testid="stDataFrame"] { font-variant-numeric: tabular-nums; }
section[data-testid="stSidebar"] { background: #0d111a; border-right:1px solid var(--line); }
section[data-testid="stSidebar"] h3 { font-family: var(--display); font-size:.78rem;
  text-transform:uppercase; letter-spacing:.12em; color: var(--muted); margin-bottom:.4rem; }
hr { border-color: var(--line); }
</style>
"""
st.markdown(STYLES, unsafe_allow_html=True)


# ======================================================================
# Cached data access
# ======================================================================

@st.cache_data(show_spinner=False)
def read_registry(csv_text: str):
    try:
        raw = pd.read_csv(io.StringIO(csv_text))
    except Exception as exc:                     # malformed file, never a crash
        return pd.DataFrame(columns=engine.REQUIRED_COLUMNS), [
            f"The file could not be read as CSV: {exc}"
        ]
    return engine.validate(raw)


@st.cache_data(show_spinner=False)
def run_engine(csv_text: str, min_score: float):
    clean, problems = read_registry(csv_text)
    matches = engine.find_matches(clean, min_score)
    gaps = engine.unmatched_outputs(clean, matches)
    summary = engine.network_summary(matches)
    return clean, problems, matches, gaps, summary


@st.cache_data(show_spinner=False)
def run_extras(csv_text: str, min_score: float):
    """The optimisation pass and the chain search, cached alongside the matches."""
    _, _, matches, _, _ = run_engine(csv_text, min_score)
    optimised, report = engine.optimise_network(matches)
    chains = engine.find_chains(matches)
    return optimised, report, chains


@st.cache_data(show_spinner=False)
def sample_registry_text() -> str:
    with open("sample_facilities.csv", encoding="utf-8") as fh:
        return fh.read()


@st.cache_data(show_spinner=False)
def india_geojson():
    """State boundaries, simplified and vendored - nothing is fetched at runtime."""
    try:
        with open(GEOJSON_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


@st.cache_data(show_spinner=False)
def my_matches(csv_text: str, min_score: float, profile: tuple):
    """Rank partners for a facility the user described. Cached on the profile."""
    clean, _ = read_registry(csv_text)
    (sector, state, lat, lon, material, out_tpa, in_tpa, season, authorised) = profile
    mine = engine.build_facility(
        engine.MY_FACILITY_NAME, sector, state, lat, lon,
        output_material=material if out_tpa > 0 else "",
        output_tpa=out_tpa, input_need_tpa=in_tpa,
        availability=season, authorised_hazardous=authorised,
    )
    return engine.matches_for_facility(clean, mine, min_score)


@st.cache_data(show_spinner=False)
def kb_table() -> pd.DataFrame:
    return pd.DataFrame([{
        "material": e["material"],
        "application": e["application"],
        "replaces": e["replaces"],
        "accepting sectors": ", ".join(e["accepting_sectors"]),
        "ratio": e["substitution_ratio"],
        "max share": e["max_share"],
        "max km": e["max_km"],
        "processing": e["processing"],
        "CO2 t/t": e["co2_saved_t"],
        "virgin value Rs/t": e["virgin_value"],
        "disposal Rs/t": e.get("disposal_cost", engine.DISPOSAL_COST_DEFAULT),
        "hazard": e["hazard"],
        "note": e["note"],
    } for e in kb.SUBSTITUTIONS])


# ======================================================================
# Small render helpers
# ======================================================================

def _hex_to_rgb(value: str):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def ramp_colour(t: float, alpha: float = 1.0) -> str:
    """Interpolate the sequential blue ramp at t in 0-1, as an rgba() string.

    Done in Python rather than handed to Plotly because the states are drawn as
    ordinary filled shapes - see the map section for why.
    """
    if t != t:                                   # NaN
        t = 0.0
    t = max(0.0, min(1.0, float(t)))
    stops = BLUE_SEQUENTIAL
    for i in range(len(stops) - 1):
        lo, hi = stops[i], stops[i + 1]
        if t <= hi[0] or i == len(stops) - 2:
            span = hi[0] - lo[0]
            f = 0.0 if span == 0 else max(0.0, min(1.0, (t - lo[0]) / span))
            c1, c2 = _hex_to_rgb(lo[1]), _hex_to_rgb(hi[1])
            r, g, b = (round(a + (b2 - a) * f) for a, b2 in zip(c1, c2))
            return f"rgba({r},{g},{b},{alpha})"
    return stops[-1][1]


def score_class(score: float) -> str:
    if score >= 85:
        return "s1"
    if score >= 70:
        return "s2"
    if score >= 55:
        return "s3"
    return "s4"


def score_colour(score: float) -> str:
    return {"s1": "#2bd99b", "s2": "#5598e7", "s3": "#e0a020", "s4": "#5a6275"}[
        score_class(score)
    ]


def kpi_tile(label: str, value: str, sub: str = "", bad: bool = False) -> str:
    sub_html = f'<div class="sub{" bad" if bad else ""}">{sub}</div>' if sub else ""
    return (f'<div class="kpi"><div class="lab">{label}</div>'
            f'<div class="val">{value}</div>{sub_html}</div>')


def match_row_html(row, position: int, best: bool = False, show_partner: bool = True) -> str:
    """One ranked result, as a card with a score pill and a score bar."""
    score = float(row["score"])
    net = float(row["net_value"])
    if show_partner and "partner" in row.index:
        # Spell the direction out. An arrow alone is ambiguous here: in receiver mode
        # the material flows from the partner to the user, not the other way round.
        verb = "Send" if row["role"] == "supplier" else "Take"
        preposition = "to" if row["role"] == "supplier" else "from"
        title = (f'{verb} <b>{row["material"]}</b> {preposition} '
                 f'{row["partner"]}')
        line2 = (f'{row["application"]} &middot; {row["partner_sector"]}, '
                 f'{row["partner_state"]} &middot; {row["road_km"]:,.0f} km')
    else:
        title = f'{row["supplier"]} &rarr; {row["receiver"]}'
        line2 = (f'{row["material"]} &middot; {row["application"]} &middot; '
                 f'{row["road_km"]:,.0f} km')
    chips = ""
    if best:
        chips += '<span class="chip best">Best</span>'
    if net < 0:
        chips += '<span class="chip loss">Loss</span>'
    if bool(row["beyond_max_km"]):
        chips += '<span class="chip far">Past limit</span>'
    return (
        f'<div class="mrow{" best" if best else ""}" style="animation-delay:{position * 0.035:.2f}s">'
        f'<div class="num">{position + 1}</div>'
        f'<div class="pill {score_class(score)}">{score:.0f}</div>'
        f'<div class="body"><div class="t1">{title}{chips}</div>'
        f'<div class="t2">{line2}</div>'
        f'<div class="bar"><i style="width:{min(100.0, score):.0f}%;'
        f'background:{score_colour(score)}"></i></div></div>'
        f'<div class="fig"><div class="n {"neg" if net < 0 else "pos"}">{engine.inr(net)}</div>'
        f'<div class="k">net / yr</div></div>'
        f'<div class="fig"><div class="n">{engine.tonnes(row["matched_tpa"])}</div>'
        f'<div class="k">per year</div></div></div>'
    )


def render_narrative(row):
    story = explain.explain(row)
    loss = float(row["net_value"]) < 0
    st.markdown(
        f'<div class="headline{" loss" if loss else ""}">{story["headline"]}</div>',
        unsafe_allow_html=True,
    )
    if bool(row["beyond_max_km"]):
        st.warning(
            f"This haul of {row['road_km']:,.0f} km is past the {row['max_km']:,.0f} km "
            f"economic limit for {row['material']}. It is admitted by the distance gate "
            "but scores zero on proximity.",
            icon=None,
        )
    for title in explain.SECTION_ORDER:
        st.markdown(f'<p class="sec-title">{title}</p>', unsafe_allow_html=True)
        st.markdown(f'<p class="sec-body">{story["sections"][title]}</p>',
                    unsafe_allow_html=True)


def render_audit(row):
    """The arithmetic behind the score and the valuation, assuming a judge opens it."""
    st.markdown("**Score: five factors, weighted**")
    audit = pd.DataFrame([
        {"factor": "Quantity", "raw": row["f_quantity"], "weight": engine.W_QUANTITY,
         "points": row["c_quantity"],
         "how it was computed":
             f"matched {row['matched_tpa']:,.0f} t / ceiling {row['ceiling_tpa']:,.0f} t "
             f"(need {row['receiver_need_tpa']:,.0f} t x max share {row['max_share']:.2f})"},
        {"factor": "Proximity", "raw": row["f_proximity"], "weight": engine.W_PROXIMITY,
         "points": row["c_proximity"],
         "how it was computed":
             f"max(0, 1 - ({row['road_km']:,.0f} km / {row['max_km']:,.0f} km) "
             f"^ {engine.PROXIMITY_EXPONENT})"},
        {"factor": "Timing", "raw": row["f_timing"], "weight": engine.W_TIMING,
         "points": row["c_timing"],
         "how it was computed":
             f"months both active / 12; supplier {row['supplier_availability']}, "
             f"receiver {row['receiver_availability']}"},
        {"factor": "Processing", "raw": row["f_processing"], "weight": engine.W_PROCESSING,
         "points": row["c_processing"],
         "how it was computed":
             f"'{row['processing']}' processing maps to "
             f"{engine.PROCESSING_FACTOR[row['processing']]:.2f}"},
        {"factor": "Compliance", "raw": row["f_compliance"], "weight": engine.W_COMPLIANCE,
         "points": row["c_compliance"],
         "how it was computed":
             f"hazard '{row['hazard']}', receiver authorised {bool(row['receiver_authorised'])}"},
    ])
    st.dataframe(
        audit, hide_index=True, width="stretch",
        column_config={
            "factor": st.column_config.TextColumn("Factor", width="small"),
            "raw": st.column_config.ProgressColumn("Raw value (0-1)", min_value=0,
                                                   max_value=1, format="%.3f"),
            "weight": st.column_config.NumberColumn("Weight", format="%.2f", width="small"),
            "points": st.column_config.NumberColumn("Points", format="%.2f", width="small"),
            "how it was computed": st.column_config.TextColumn("How it was computed",
                                                               width="large"),
        },
    )
    st.markdown(
        f"Total: **{row['score']:.2f}** of 100 (sum of points; weights sum to "
        f"{sum(engine.WEIGHTS.values()):.2f})."
    )

    st.markdown("**Valuation, line by line, per year**")
    money = pd.DataFrame([
        {"line": "Virgin material displaced", "amount": row["material_value"],
         "how it was computed":
             f"{row['matched_tpa']:,.0f} t x ratio {row['substitution_ratio']:.2f} "
             f"x Rs {row['virgin_value']:,.0f}/t"},
        {"line": "Disposal avoided", "amount": row["disposal_saved"],
         "how it was computed": f"{row['matched_tpa']:,.0f} t x Rs {row['disposal_rate']:,.0f}/t"},
        {"line": "Transport", "amount": -row["transport_cost"],
         "how it was computed":
             f"{row['matched_tpa']:,.0f} t x {row['road_km']:,.0f} km x "
             f"Rs {row['freight_rate']:,.1f}/t-km ({row['transport_mode']})"
             + (f" + {row['matched_tpa']:,.0f} t x Rs {row['terminal_rate']:,.0f}/t "
                "terminal handling and road legs"
                if float(row["terminal_rate"]) > 0 else "")},
        {"line": "Processing", "amount": -row["processing_cost"],
         "how it was computed":
             f"{row['matched_tpa']:,.0f} t x Rs {row['processing_rate']:,.0f}/t "
             f"('{row['processing']}')"},
        {"line": "Net", "amount": row["net_value"],
         "how it was computed": "sum of the four lines above"},
    ])
    st.dataframe(
        money, hide_index=True, width="stretch",
        column_config={
            "line": st.column_config.TextColumn("Line", width="medium"),
            "amount": st.column_config.NumberColumn("Rs/yr", format="%.0f"),
            "how it was computed": st.column_config.TextColumn("How it was computed",
                                                               width="large"),
        },
    )

    st.markdown("**Tonnage and allocation**")
    st.dataframe(
        pd.DataFrame([
            {"quantity": "Supplier output", "t/yr": row["supplier_output_tpa"]},
            {"quantity": "Receiver input need", "t/yr": row["receiver_need_tpa"]},
            {"quantity": f"Ceiling at max share {row['max_share']:.2f}", "t/yr": row["ceiling_tpa"]},
            {"quantity": "Matched in this pairing", "t/yr": row["matched_tpa"]},
            {"quantity": "Allocated once other matches are served", "t/yr": row["allocated_tpa"]},
        ]),
        hide_index=True, width="stretch",
        column_config={
            "quantity": st.column_config.TextColumn("Quantity", width="large"),
            "t/yr": st.column_config.NumberColumn("t/yr", format="%.0f"),
        },
    )
    st.markdown(
        f'<p class="caveat">This pairing places {row["supplier_share"] * 100:.0f}% of the '
        f'supplier\'s output of {row["material"]}. The quantity factor measures how much of '
        'the <em>receiver\'s</em> ceiling is filled, so a very large supplier can score 1.00 '
        'while still placing a small fraction of its output - that is what this line '
        f'exposes.</p><p class="caveat">Knowledge base note: {row["note"]}</p>',
        unsafe_allow_html=True,
    )


# ======================================================================
# Sidebar
# ======================================================================

with st.sidebar:
    st.markdown("### Registry")
    source = st.radio("Source", ["Sample registry", "Upload a CSV"],
                      label_visibility="collapsed")

    csv_text = sample_registry_text()
    if source == "Upload a CSV":
        uploaded = st.file_uploader("Facility registry (CSV)", type=["csv"])
        if uploaded is not None:
            csv_text = uploaded.getvalue().decode("utf-8", errors="replace")
        else:
            st.info("No file yet - showing the sample registry.")

    st.download_button("Download CSV template", data=engine.template_csv(),
                       file_name="registry_template.csv", mime="text/csv",
                       width="stretch")

    st.markdown("### Threshold")
    min_score = st.slider(
        "Minimum score", 0, 90, int(engine.MIN_SCORE_DEFAULT), 1,
        help="Exchanges scoring below this are not listed. The engine's own floor is 35 - "
             "lowering this shows weaker pairings, not new ones.",
    )

    st.markdown(
        '<p class="caveat">Sample capacities are representative of plants of this type, '
        'not audited figures. Rupee values are the size of the prize across both parties, '
        'not either one\'s margin.</p>',
        unsafe_allow_html=True,
    )

facilities, problems, matches, gaps, summary = run_engine(csv_text, float(min_score))

# ======================================================================
# Hero and KPI strip
# ======================================================================

st.markdown(
    '<div class="hero"><span class="tag">ENIGMA 5.0 &middot; Sustainability &middot; PS 5</span>'
    '<h1>Symbiosis Finder</h1>'
    f'<p>Every exchange where one plant\'s by-product can replace another\'s virgin raw '
    f'material - searched across {len(facilities)} facilities and '
    f'{len(kb.SUBSTITUTIONS)} documented substitutions, scored on how practical it actually '
    f'is, and priced. Every number is computed in Python and auditable to its inputs.</p></div>',
    unsafe_allow_html=True,
)

if problems:
    with st.expander(f"Data quality: {len(problems)} note(s) on this registry", expanded=False):
        for p in problems:
            st.warning(p, icon=None)

if facilities.empty:
    st.error("No usable facilities in this registry. Check the columns against the template.")
    st.stop()

optimised, opt_report, chains = run_extras(csv_text, float(min_score))
impact = engine.circularity(matches, facilities)
unmatched_tonnes = float(gaps["output_tpa"].sum()) if len(gaps) else 0.0
st.markdown(
    '<div class="kpis">'
    + kpi_tile("Viable exchanges", f"{summary['exchanges']:,}",
               f"{summary['suppliers']} suppliers &middot; {summary['receivers']} receivers")
    + kpi_tile("Tonnes diverted", engine.tonnes(summary["tonnes_diverted"]), "per year")
    + kpi_tile("CO2 avoided", engine.tonnes(summary["co2_avoided_t"]), "per year")
    + kpi_tile("Value unlocked", engine.inr(summary["value_unlocked"]),
               f"{summary['loss_making']} run at a loss", bad=summary["loss_making"] > 0)
    + kpi_tile("Still unmatched", engine.tonnes(unmatched_tonnes),
               f"{len(gaps)} streams with nowhere to go")
    + kpi_tile("Circularity", f"{impact['circularity_pct']:.1f}%",
               f"of {engine.tonnes(impact['total_byproduct_t'])} produced")
    + "</div>",
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="caveat">Tonnes diverted and value unlocked deduplicate by supplier and '
    'material. A feasible allocation across several receivers, which never promises the same '
    f'tonne twice, places {engine.tonnes(summary["allocated_tonnes"])} for '
    f'{engine.inr(summary["allocated_value"])} - see Method.</p>',
    unsafe_allow_html=True,
)

(tab_mine, tab_network, tab_matches, tab_chains,
 tab_gaps, tab_method) = st.tabs(
    ["Find my matches", "Exchange network", "Ranked matches", "Chains & impact",
     "Gap analysis", "Method"]
)

# ======================================================================
# 1. Find my matches
# ======================================================================

with tab_mine:
    st.markdown('<div class="sect">Describe your plant</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">Pick what you make or what you need, say roughly how much and '
        'where you are, and every facility in the registry is ranked as a partner - scored '
        'by the same five factors as everything else in this tool, so the numbers are '
        'comparable.</p>',
        unsafe_allow_html=True,
    )

    role = st.radio(
        "What are you looking for?",
        ["I have a by-product to place", "I need raw material"],
        horizontal=True, key="role",
    )
    is_supplier = role.startswith("I have")

    c1, c2, c3 = st.columns(3)

    registry_sectors = sorted({str(s) for s in facilities["sector"].unique()})
    sector_options = sorted(set(registry_sectors) | set(kb.sectors()))
    with c1:
        if is_supplier:
            all_materials = kb.materials()
            material = st.selectbox(
                "By-product you produce", all_materials,
                index=all_materials.index("fly ash") if "fly ash" in all_materials else 0,
                key="my_material")
            takers = engine.sectors_for_material(material)
            sector = st.selectbox(
                "Your sector", sector_options,
                index=(sector_options.index("thermal power")
                       if "thermal power" in sector_options else 0),
                key="my_sector_sup",
                help="Used for the registry only - what you offer is decided by the "
                     "by-product, not by your sector.",
            )
            st.markdown(
                f'<p class="caveat">Sectors that can take {material}: '
                f'{", ".join(takers) if takers else "none recorded"}.</p>',
                unsafe_allow_html=True,
            )
        else:
            sector = st.selectbox(
                "Your sector", sector_options,
                index=sector_options.index("cement") if "cement" in sector_options else 0,
                key="my_sector_rec",
            )
            takeable = engine.materials_for_sector(sector)
            if takeable:
                material = st.selectbox(
                    "By-product you could accept", ["Anything I can use"] + takeable,
                    key="my_material_rec",
                    help="The engine tests every by-product your sector can accept. Pick one "
                         "to narrow the ranking to it.",
                )
            else:
                material = "Anything I can use"
                st.warning(
                    f"The knowledge base records no by-product that a '{sector}' plant can "
                    "accept, so there is nothing to rank. Try another sector.", icon=None,
                )

    with c2:
        location = st.selectbox("Nearest industrial centre", list(INDUSTRIAL_LOCATIONS),
                                index=list(INDUSTRIAL_LOCATIONS).index("Nagpur, Maharashtra"),
                                key="my_location")
        my_state, my_lat, my_lon = INDUSTRIAL_LOCATIONS[location]
        precise = st.toggle("Enter exact coordinates", value=False, key="my_precise")
        if precise:
            lc1, lc2 = st.columns(2)
            my_lat = lc1.number_input("Latitude", 6.0, 37.0, float(my_lat), 0.01, format="%.4f")
            my_lon = lc2.number_input("Longitude", 67.0, 98.0, float(my_lon), 0.01, format="%.4f")

    with c3:
        quantity = st.number_input(
            "Tonnes per year you produce" if is_supplier else "Tonnes per year of input you draw",
            min_value=100, max_value=10_000_000,
            value=250_000 if is_supplier else 1_200_000, step=10_000,
        )
        season_label = st.selectbox("When you operate", list(engine.SEASON_PRESETS),
                                    key="my_season")
        authorised = st.toggle(
            "Authorised to handle hazardous waste", value=False, key="my_auth",
            help="Regulated streams score 0.75 on compliance with authorisation and 0.25 "
                 "without it.",
        )

    go_ranking = st.button("Rank my options", type="primary", key="run_mine")

    if go_ranking or st.session_state.get("mine_ran"):
        st.session_state["mine_ran"] = True
        profile = (
            sector, my_state, float(my_lat), float(my_lon),
            material if is_supplier else "",
            float(quantity) if is_supplier else 0.0,
            0.0 if is_supplier else float(quantity),
            engine.SEASON_PRESETS[season_label], bool(authorised),
        )
        mine = my_matches(csv_text, float(min_score), profile)

        if not is_supplier and material != "Anything I can use" and len(mine):
            mine = mine[mine["material"].str.lower() == material.lower()].reset_index(drop=True)
            if len(mine):
                mine["rank"] = range(1, len(mine) + 1)

        st.markdown("---")
        if mine.empty:
            st.info(
                "No partner in this registry clears the gates for that description. That is a "
                "real answer, not a failure: try a larger tonnage, a more central location, a "
                "different by-product, or lower the minimum score in the sidebar. If the "
                "by-product is bulky and low-value, distance is almost certainly the binding "
                "constraint."
            )
        else:
            best = mine.iloc[0]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Viable partners", f"{len(mine):,}")
            k2.metric("Best score", f"{best['score']:.1f}")
            k3.metric("Best net value", engine.inr(best["net_value"]) + " / yr")
            k4.metric("Best CO2 avoided", engine.tonnes(best["co2_avoided_t"]) + " / yr")

            st.markdown(
                f'<div class="sect">Ranked partners &mdash; {len(mine)} viable</div>'
                '<p class="sub">Ranked by the same engine score used everywhere else: '
                'quantity 0.30, proximity 0.28, processing 0.16, timing 0.14, compliance '
                '0.12.</p>',
                unsafe_allow_html=True,
            )
            shown = mine.head(12)
            st.markdown(
                "".join(match_row_html(shown.iloc[i], i, best=(i == 0))
                        for i in range(len(shown))),
                unsafe_allow_html=True,
            )
            if len(mine) > len(shown):
                st.markdown(
                    f'<p class="caveat">{len(mine) - len(shown)} further partner(s) not '
                    'shown; all are in the download below.</p>',
                    unsafe_allow_html=True,
                )

            d1, d2 = st.columns([2, 1])
            labels = [f"{r.rank}. {r.material} - {r.partner}"
                      for r in mine.itertuples(index=False)]
            picked = d1.selectbox("Inspect a partner", labels, index=0, key="mine_pick")
            d2.download_button(
                "Download my ranked list", data=mine.to_csv(index=False).encode("utf-8"),
                file_name="my_symbiosis_matches.csv", mime="text/csv", width="stretch",
            )
            chosen = mine.iloc[labels.index(picked)]
            render_narrative(chosen)
            with st.expander("Audit this score and valuation", expanded=False):
                render_audit(chosen)
    else:
        st.markdown(
            '<p class="caveat">Fill in the fields above and press <strong>Rank my options'
            '</strong>.</p>',
            unsafe_allow_html=True,
        )

# ======================================================================
# 2. Exchange network
# ======================================================================

with tab_network:
    if matches.empty:
        st.info("No exchanges clear the current threshold, so there is no network to draw.")
    else:
        f1, f2, f3, f4 = st.columns([1.5, 1.7, 1.7, 1.2])
        metric_label = f1.selectbox(
            "Colour states by",
            ["Exchanges involved", "Tonnes supplied", "Tonnes received", "Facilities"],
            key="map_metric",
        )
        states = sorted(set(matches["supplier_state"]) | set(matches["receiver_state"]))
        pick_states = f2.multiselect("Filter states", states, default=[],
                                     placeholder="All states")
        materials = sorted(matches["material"].unique())
        pick_materials = f3.multiselect("Filter materials", materials, default=[],
                                        placeholder="All materials")
        show_n = f4.slider("Flows to draw", 5, max(6, min(200, len(matches))),
                           min(60, len(matches)), 5)

        view = matches
        if pick_states:
            view = view[view["supplier_state"].isin(pick_states)
                        | view["receiver_state"].isin(pick_states)]
        if pick_materials:
            view = view[view["material"].isin(pick_materials)]
        view = view.head(show_n)

        activity = engine.state_activity(view, facilities)
        metric_field = {
            "Exchanges involved": "exchanges",
            "Tonnes supplied": "tonnes_supplied",
            "Tonnes received": "tonnes_received",
            "Facilities": "facilities",
        }[metric_label]
        by_state = {r.state: r for r in activity.itertuples(index=False)}
        vmax = float(activity[metric_field].max()) if len(activity) else 0.0
        vmax = vmax if vmax > 0 else 1.0

        fig = go.Figure()

        # The states are drawn as ordinary filled shapes on a plain x/y plot rather
        # than on a Plotly geo subplot. A geo subplot always pulls its own topojson
        # from Plotly's CDN - even with the basemap switched off - and this app is
        # meant to run with no internet at all. Longitude is x, latitude is y, the
        # aspect ratio is anchored below, and the boundaries come from the GeoJSON
        # bundled in data/.
        geo = india_geojson()
        if geo is not None:
            for feature in geo["features"]:
                state = feature["properties"]["state"]
                stats = by_state.get(state)
                value = float(getattr(stats, metric_field)) if stats else 0.0
                xs, ys = [], []
                for polygon in feature["geometry"]["coordinates"]:
                    for ring in polygon:
                        xs.extend([p[0] for p in ring] + [None])
                        ys.extend([p[1] for p in ring] + [None])
                if stats:
                    detail = (f"<b>{state}</b><br>{stats.exchanges} exchange(s)"
                              f"<br>{engine.tonnes(stats.tonnes_supplied)} supplied"
                              f"<br>{engine.tonnes(stats.tonnes_received)} received"
                              f"<br>{stats.facilities} facility/facilities")
                else:
                    detail = f"<b>{state}</b><br>no facility in this registry"
                fig.add_trace(go.Scatter(
                    x=xs, y=ys, mode="lines", fill="toself",
                    fillcolor=ramp_colour(value / vmax, 0.92),
                    line=dict(color="rgba(255,255,255,0.20)", width=0.6),
                    hoveron="fills", hoverinfo="text", text=detail,
                    name="", showlegend=False,
                ))

            # A dummy trace carrying the colour scale, so the fills get a legible key.
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode="markers", showlegend=False, hoverinfo="skip",
                marker=dict(
                    colorscale=BLUE_SEQUENTIAL, cmin=0, cmax=vmax, color=[0],
                    showscale=True, opacity=0,
                    colorbar=dict(
                        title=dict(text=metric_label, font=dict(size=10, color="#8d95a9"),
                                   side="top"),
                        orientation="h", thickness=9, len=0.46, x=0.5, xanchor="center",
                        y=-0.02, yanchor="bottom", outlinewidth=0, xpad=0, ypad=0,
                        tickfont=dict(size=9, color="#8d95a9"),
                    ),
                ),
            ))

        # Flow lines. Viable and loss-making differ in colour AND dash pattern, and
        # both carry a legend entry, so the distinction never rests on colour alone.
        seen_legend = set()
        for row in view.itertuples(index=False):
            loss = row.net_value < 0
            strength = float(row.score) / 100.0
            key = "loss" if loss else "viable"
            fig.add_trace(go.Scatter(
                x=[row.supplier_lon, row.receiver_lon],
                y=[row.supplier_lat, row.receiver_lat],
                mode="lines",
                line=dict(width=1.0 + 3.2 * strength,
                          color=LOSS_COLOUR if loss else SUPPLIER_COLOUR,
                          dash="dot" if loss else "solid"),
                opacity=0.32 + 0.55 * strength,
                hoverinfo="text",
                text=(f"{row.material}: {row.supplier} to {row.receiver}"
                      f"<br>Score {row.score:.1f}"
                      f"<br>{engine.tonnes(row.matched_tpa)}/yr over {row.road_km:,.0f} km"
                      f"<br>Net {engine.inr(row.net_value)}/yr"),
                name="Loss-making exchange" if loss else "Viable exchange",
                legendgroup=key, showlegend=key not in seen_legend,
            ))
            seen_legend.add(key)

        sup = view.drop_duplicates("supplier")
        rec = view.drop_duplicates("receiver")
        fig.add_trace(go.Scatter(
            x=sup["supplier_lon"], y=sup["supplier_lat"], mode="markers", name="Supplier",
            marker=dict(size=10, color=SUPPLIER_COLOUR, opacity=0.96,
                        line=dict(width=1.2, color="#0b0e14")),
            hoverinfo="text",
            text=[f"<b>{n}</b><br>{s}<br>offers {m}"
                  for n, s, m in zip(sup["supplier"], sup["supplier_sector"], sup["material"])],
        ))
        fig.add_trace(go.Scatter(
            x=rec["receiver_lon"], y=rec["receiver_lat"], mode="markers", name="Receiver",
            marker=dict(size=10, color=RECEIVER_COLOUR, opacity=0.96, symbol="square",
                        line=dict(width=1.2, color="#0b0e14")),
            hoverinfo="text",
            text=[f"<b>{n}</b><br>{s}" for n, s in zip(rec["receiver"], rec["receiver_sector"])],
        ))

        fig.update_xaxes(
            range=[engine.INDIA_BOUNDS["lon_min"], engine.INDIA_BOUNDS["lon_max"]],
            visible=False, constrain="domain",
        )
        fig.update_yaxes(
            range=[engine.INDIA_BOUNDS["lat_min"], engine.INDIA_BOUNDS["lat_max"]],
            visible=False,
            # A degree of latitude is ~111 km; a degree of longitude ~103 km at 22 N.
            # Anchoring the aspect keeps the country's shape and the distances honest.
            scaleanchor="x", scaleratio=1.08, constrain="domain",
        )
        fig.update_layout(
            height=640, margin=dict(l=0, r=0, t=6, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e9edf5", size=12, family="Inter, sans-serif"),
            legend=dict(orientation="v", yanchor="top", y=0.99, x=0.005,
                        bgcolor="rgba(11,14,20,0.80)", bordercolor="rgba(255,255,255,0.08)",
                        borderwidth=1, font=dict(size=11)),
            hoverlabel=dict(bgcolor="#131824", bordercolor="rgba(255,255,255,0.14)",
                            font=dict(color="#e9edf5", size=12)),
            dragmode="pan",
        )
        map_col, side_col = st.columns([2.45, 1], gap="medium")
        with map_col:
            st.plotly_chart(fig, width="stretch",
                            config={"displaylogo": False, "scrollZoom": True})

        with side_col:
            ranked_states = (
                activity[activity[metric_field] > 0]
                .sort_values([metric_field, "state"], ascending=[False, True],
                             kind="mergesort")
                .head(9)
            )
            st.markdown(f'<div class="sect">Top states by {metric_label.lower()}</div>',
                        unsafe_allow_html=True)
            if ranked_states.empty:
                st.markdown('<p class="caveat">No state has any activity under these '
                            'filters.</p>', unsafe_allow_html=True)
            else:
                top_value = float(ranked_states[metric_field].max()) or 1.0
                rows_html = []
                for i, r in enumerate(ranked_states.itertuples(index=False)):
                    value = float(getattr(r, metric_field))
                    shown = (f"{value:,.0f}" if metric_field in ("exchanges", "facilities")
                             else engine.tonnes(value))
                    rows_html.append(
                        f'<div class="srow" style="animation-delay:{i * 0.04:.2f}s">'
                        f'<div class="sname">{r.state}</div>'
                        f'<div class="sval">{shown}</div>'
                        f'<div class="bar" style="margin-top:.3rem"><i style="width:'
                        f'{100.0 * value / top_value:.0f}%;background:'
                        f'{ramp_colour(value / top_value)}"></i></div></div>'
                    )
                st.markdown("".join(rows_html), unsafe_allow_html=True)

            st.markdown(
                f'<p class="caveat" style="margin-top:.9rem">'
                f'<strong>{len(view)}</strong> flow(s) drawn. Thickness and opacity scale '
                'with score; dotted red lines lose money. Hover any state for its totals, '
                'drag to pan, scroll to zoom.</p>'
                '<p class="caveat">Lines are straight-line links, not routed roads - scoring '
                f'uses straight-line distance inflated {engine.ROAD_CIRCUITY_FACTOR:.2f}x. '
                'State boundaries are bundled with the app, so nothing is fetched from the '
                'internet to draw this map.</p>',
                unsafe_allow_html=True,
            )


# ======================================================================
# 3. Ranked matches
# ======================================================================

with tab_matches:
    if matches.empty:
        st.info("No exchanges clear the current threshold.")
    else:
        left, right = st.columns([1.05, 1])

        with left:
            st.markdown('<div class="sect">Ranked exchanges</div>', unsafe_allow_html=True)
            table = matches[["rank", "score", "supplier", "material", "receiver",
                             "matched_tpa", "road_km", "transport_mode",
                             "net_value"]].copy()
            table["at a loss"] = matches["net_value"] < 0
            st.dataframe(
                table, hide_index=True, height=560, width="stretch",
                column_config={
                    "rank": st.column_config.NumberColumn("#", width="small"),
                    "score": st.column_config.ProgressColumn("Score", min_value=0,
                                                             max_value=100, format="%.1f",
                                                             width="medium"),
                    "supplier": st.column_config.TextColumn("Supplier"),
                    "material": st.column_config.TextColumn("By-product"),
                    "receiver": st.column_config.TextColumn("Receiver"),
                    "matched_tpa": st.column_config.NumberColumn("t/yr", format="%.0f"),
                    "road_km": st.column_config.NumberColumn("km", format="%.0f"),
                    "transport_mode": st.column_config.TextColumn("Mode", width="small"),
                    "net_value": st.column_config.NumberColumn("Net Rs/yr", format="%.0f"),
                    "at a loss": st.column_config.CheckboxColumn("Loss", width="small"),
                },
            )
            st.download_button("Download all matches as CSV",
                               data=matches.to_csv(index=False).encode("utf-8"),
                               file_name="symbiosis_matches.csv", mime="text/csv",
                               width="stretch")

        with right:
            labels = [f"{r.rank}. {r.material} - {r.supplier} to {r.receiver}"
                      for r in matches.itertuples(index=False)]
            chosen = st.selectbox("Exchange", labels, index=0, key="match_pick")
            row = matches.iloc[labels.index(chosen)]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Score", f"{row['score']:.1f}")
            m2.metric("Tonnes/yr", engine.tonnes(row["matched_tpa"]))
            m3.metric("Net value/yr", engine.inr(row["net_value"]))
            m4.metric("CO2 avoided/yr", engine.tonnes(row["co2_avoided_t"]))

            render_narrative(row)

        st.markdown("---")
        with st.expander("Audit this score and valuation", expanded=False):
            render_audit(row)

# ======================================================================
# 4. Chains and impact
# ======================================================================

with tab_chains:
    st.markdown('<div class="sect">What the network is worth, and how to run it</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">Pairwise scoring says which exchanges are practical. It does not '
        'say how to run them all together, and it cannot see an arrangement that only '
        'makes sense through a third plant. These two passes do.</p>',
        unsafe_allow_html=True,
    )

    basis = st.radio(
        "Allocation basis",
        ["Optimised (linear programming)", "Greedy (best score first)"],
        horizontal=True, key="impact_basis",
        help="Greedy walks the matches best score first and gives each whatever is left. "
             "The optimiser solves the whole allocation at once to maximise net value, "
             "subject to the same supply, intake and ceiling limits.",
    )
    use_optimised = basis.startswith("Optimised")
    column = "optimised_tpa" if use_optimised else "allocated_tpa"
    frame = optimised if use_optimised else matches
    stats = engine.circularity(frame, facilities, tonnes_column=column)

    st.markdown(
        '<div class="kpis" style="grid-template-columns:repeat(5,1fr)">'
        + kpi_tile("Circularity", f"{stats['circularity_pct']:.1f}%",
                   f"of {engine.tonnes(stats['total_byproduct_t'])} of by-product produced")
        + kpi_tile("Landfill diverted", engine.tonnes(stats["landfill_diverted_t"]),
                   "kept out of disposal per year")
        + kpi_tile("Virgin material avoided", engine.tonnes(stats["virgin_avoided_t"]),
                   "not quarried, mined or grown")
        + kpi_tile("CO2 avoided", engine.tonnes(stats["co2_avoided_t"]), "per year")
        + kpi_tile("Net value", engine.inr(stats["net_value"]), "per year, both parties")
        + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="caveat">Circularity is the share of by-product tonnage in this registry '
        'that actually finds a home. The denominator is every tonne offered, including the '
        'streams with no viable receiver, so it is deliberately hard to move. Virgin '
        'material avoided applies each substitution ratio to the tonnage placed - it is the '
        'quarrying, mining and growing that does not have to happen.</p>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sect">Optimiser against greedy</div>', unsafe_allow_html=True)
    greedy_value = float(matches["allocated_net_value"].sum()) if len(matches) else 0.0
    o1, o2, o3 = st.columns(3)
    o1.metric("Greedy allocation", engine.inr(greedy_value) + " / yr")
    o2.metric("Optimised allocation", engine.inr(opt_report["objective"]) + " / yr",
              delta=engine.inr(opt_report["improvement"]) + " better")
    o3.metric("Exchanges left at zero", f"{opt_report['dropped']:,}",
              help="The optimiser is free to use none of an exchange. Anything that loses "
                   "money is dropped on its own, without a rule telling it to.")
    st.markdown(
        f'<p class="caveat">Solver: {opt_report["solver"]}. {opt_report["status"]} '
        'The objective is total net value per year subject to every supplier\'s output, '
        'every receiver\'s intake, and each receiver\'s ceiling for a given material. '
        'Both plans are feasible; neither is a plan anyone has agreed to.</p>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown(f'<div class="sect">Multi-hop chains &mdash; {len(chains)} found</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">A chain is one plant receiving a by-product and placing its own, '
        'so the exchanges only make sense read together. A pair-at-a-time search cannot see '
        'them, and they are what an industrial park is actually built around. Each hop must '
        'move a different material - otherwise it is a stream being passed along, not a '
        'plant transforming it - and no facility appears twice. Ranked by the weakest link, '
        'because a chain is only as real as its worst exchange.</p>',
        unsafe_allow_html=True,
    )

    if chains.empty:
        st.info(
            "No chains at this threshold. Chains need a plant that both receives a "
            "by-product and supplies one of its own; lower the minimum score in the sidebar "
            "to admit weaker links."
        )
    else:
        st.dataframe(
            chains[["hops", "weakest_score", "mean_score", "path", "materials",
                    "total_net_value", "total_co2_t"]],
            hide_index=True, width="stretch", height=330,
            column_config={
                "hops": st.column_config.NumberColumn("Hops", width="small"),
                "weakest_score": st.column_config.ProgressColumn(
                    "Weakest link", min_value=0, max_value=100, format="%.1f"),
                "mean_score": st.column_config.NumberColumn("Mean score", format="%.1f",
                                                            width="small"),
                "path": st.column_config.TextColumn("Chain", width="large"),
                "materials": st.column_config.TextColumn("Materials", width="medium"),
                "total_net_value": st.column_config.NumberColumn("Net Rs/yr", format="%.0f"),
                "total_co2_t": st.column_config.NumberColumn("CO2 t/yr", format="%.0f"),
            },
        )

        chain_labels = [f"{i + 1}. {r.path}" for i, r in enumerate(chains.itertuples(index=False))]
        picked_chain = st.selectbox("Walk a chain", chain_labels, index=0, key="chain_pick")
        chain = chains.iloc[chain_labels.index(picked_chain)]

        steps_html = []
        for i, step in enumerate(str(chain["steps"]).split(" | ")):
            steps_html.append(
                f'<div class="mrow" style="animation-delay:{i * 0.06:.2f}s">'
                f'<div class="num">{i + 1}</div>'
                f'<div class="body"><div class="t1">{step}</div></div></div>'
            )
        st.markdown("".join(steps_html), unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.metric("Weakest link", f"{chain['weakest_score']:.1f}")
        c2.metric("Chain net value", engine.inr(chain["total_net_value"]) + " / yr")
        c3.metric("Chain CO2 avoided", engine.tonnes(chain["total_co2_t"]) + " / yr")
        st.markdown(
            '<p class="caveat">Chain totals add the individual exchanges, which overstates '
            'them if the hops compete for the same tonnage - read the optimised allocation '
            'above for what the network can actually run at once.</p>',
            unsafe_allow_html=True,
        )

# ======================================================================
# 5. Gap analysis
# ======================================================================

with tab_gaps:
    st.markdown('<div class="sect">By-products with no viable receiver</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">These are not errors. Each is a stream someone is paying to dispose '
        'of, with no receiver in this registry that clears the gates - which is exactly where '
        'a new processing or aggregation facility would pay for itself.</p>',
        unsafe_allow_html=True,
    )

    if gaps.empty:
        st.success("Every by-product in this registry found at least one viable receiver.")
    else:
        st.markdown(
            '<div class="kpis" style="grid-template-columns:repeat(3,1fr)">'
            + kpi_tile("Unplaced streams", f"{len(gaps):,}")
            + kpi_tile("Tonnes with nowhere to go", engine.tonnes(gaps["output_tpa"].sum()),
                       "per year")
            + kpi_tile("Disposal cost carried", engine.inr(gaps["disposal_cost"].sum()),
                       "per year", bad=True)
            + "</div>",
            unsafe_allow_html=True,
        )

        top = gaps.head(10).iloc[::-1]
        bar = go.Figure(go.Bar(
            x=top["output_tpa"], y=[f"{m} - {s}" for m, s in zip(top["material"], top["supplier"])],
            orientation="h",
            marker=dict(color=top["output_tpa"], colorscale=BLUE_SEQUENTIAL,
                        line=dict(width=0)),
            hoverinfo="text",
            text=[f"<b>{m}</b><br>{s}<br>{engine.tonnes(t)}/yr unplaced"
                  f"<br>{engine.inr(d)}/yr disposal"
                  for m, s, t, d in zip(top["material"], top["supplier"],
                                        top["output_tpa"], top["disposal_cost"])],
            hovertemplate="%{text}<extra></extra>",
        ))
        bar.update_layout(
            height=330, margin=dict(l=0, r=10, t=6, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#e9edf5", size=11, family="Inter, sans-serif"),
            xaxis=dict(title="tonnes per year with nowhere to go", gridcolor="rgba(255,255,255,.06)",
                       zeroline=False),
            yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            hoverlabel=dict(bgcolor="#131824", bordercolor="rgba(255,255,255,0.14)"),
            showlegend=False,
        )
        st.plotly_chart(bar, width="stretch", config={"displaylogo": False})

        st.dataframe(
            gaps[["supplier", "sector", "state", "material", "output_tpa", "disposal_cost",
                  "recorded_uses", "candidate_sectors"]],
            hide_index=True, width="stretch", height=300,
            column_config={
                "supplier": st.column_config.TextColumn("Facility"),
                "sector": st.column_config.TextColumn("Sector", width="small"),
                "state": st.column_config.TextColumn("State", width="small"),
                "material": st.column_config.TextColumn("By-product"),
                "output_tpa": st.column_config.NumberColumn("t/yr", format="%.0f"),
                "disposal_cost": st.column_config.NumberColumn("Disposal Rs/yr", format="%.0f"),
                "recorded_uses": st.column_config.NumberColumn("Known uses", width="small"),
                "candidate_sectors": st.column_config.TextColumn("Sectors that could take it",
                                                                 width="large"),
            },
        )

        gap_labels = [f"{r.material} - {r.supplier} ({r.output_tpa:,.0f} t/yr)"
                      for r in gaps.itertuples(index=False)]
        picked = st.selectbox("Examine a stream", gap_labels, index=0, key="gap_pick")
        gap = gaps.iloc[gap_labels.index(picked)]
        st.markdown(f'<div class="headline loss">{explain.explain_gap(gap)}</div>',
                    unsafe_allow_html=True)

        # --- analogue discovery -------------------------------------------------
        st.markdown('<div class="sect">What this stream resembles</div>',
                    unsafe_allow_html=True)
        st.markdown(
            '<p class="sub">The substitution table can only match a stream it has heard '
            'of. This compares the by-product\'s measured properties against every '
            'material the knowledge base does know and reports the closest, with the '
            'properties that drive the resemblance and the one that does not. It is a lead '
            'to test, never a scored match - nothing here touches the score or the '
            'valuation.</p>',
            unsafe_allow_html=True,
        )
        similar = engine.analogues(gap["material"], top_n=5)
        if similar.empty:
            st.info(
                f"No property profile is recorded for {gap['material']}, so there is "
                "nothing to compare it against. Adding one to kb.MATERIAL_PROFILES is a "
                "laboratory question, not a code change."
            )
        else:
            st.dataframe(
                similar, hide_index=True, width="stretch",
                column_config={
                    "material": st.column_config.TextColumn("Closest known material",
                                                            width="medium"),
                    "similarity": st.column_config.ProgressColumn(
                        "Resemblance", min_value=0, max_value=1, format="%.3f"),
                    "recorded_uses": st.column_config.NumberColumn("Known uses",
                                                                   width="small"),
                    "accepting_sectors": st.column_config.TextColumn(
                        "Sectors that take the analogue", width="medium"),
                    "shared_properties": st.column_config.TextColumn(
                        "What lines up", width="medium"),
                    "biggest_difference": st.column_config.TextColumn(
                        "What does not", width="small"),
                },
            )
            best = similar.iloc[0]
            st.markdown(
                f'<p class="caveat">Closest analogue: <strong>{best["material"]}</strong> at '
                f'{best["similarity"]:.0%} resemblance, agreeing on {best["shared_properties"]}, '
                f'differing most on {best["biggest_difference"]}. It is accepted by '
                f'{best["accepting_sectors"]}. The next step is a laboratory analysis of the '
                'real material against that sector\'s specification - resemblance on paper '
                'is a reason to test, not a reason to sign.</p>',
                unsafe_allow_html=True,
            )

        uses = kb.uses_for(gap["material"])
        st.markdown('<div class="sect">Every recorded use for this stream</div>',
                    unsafe_allow_html=True)
        if not uses:
            st.info("The knowledge base records no use for this material. Adding one is a "
                    "research task, not a code change - see kb.py.")
        else:
            st.dataframe(
                pd.DataFrame([{
                    "application": u["application"], "replaces": u["replaces"],
                    "accepting sectors": ", ".join(u["accepting_sectors"]),
                    "max share": u["max_share"], "max km": u["max_km"],
                    "processing": u["processing"], "hazard": u["hazard"], "note": u["note"],
                } for u in uses]),
                hide_index=True, width="stretch",
                column_config={
                    "application": st.column_config.TextColumn("Application", width="medium"),
                    "max share": st.column_config.NumberColumn("Max share", format="%.2f",
                                                               width="small"),
                    "max km": st.column_config.NumberColumn("Max km", format="%.0f",
                                                            width="small"),
                    "note": st.column_config.TextColumn("Practical catch", width="large"),
                },
            )

# ======================================================================
# 6. Method
# ======================================================================

with tab_method:
    st.markdown('<div class="sect">How a match is scored</div>', unsafe_allow_html=True)
    st.markdown(
        "A match is one combination of supplier, by-product, receiver and application. The "
        "score is 100 times the weighted sum of five factors, each normalised to 0-1. The "
        "same function scores the sample registry, an uploaded registry and a plant you "
        "describe yourself."
    )
    st.dataframe(
        pd.DataFrame([
            {"factor": "Quantity", "weight": engine.W_QUANTITY,
             "formula": "matched_t / ceiling, where ceiling = receiver need x max_share and "
                        "matched_t = min(supplier output, ceiling)"},
            {"factor": "Proximity", "weight": engine.W_PROXIMITY,
             "formula": f"max(0, 1 - (road_km / max_km) ^ {engine.PROXIMITY_EXPONENT})"},
            {"factor": "Processing", "weight": engine.W_PROCESSING,
             "formula": "none 1.00, simple 0.85, moderate 0.55, complex 0.25"},
            {"factor": "Timing", "weight": engine.W_TIMING,
             "formula": "months in which both sides are active, divided by 12"},
            {"factor": "Compliance", "weight": engine.W_COMPLIANCE,
             "formula": f"unregulated {engine.COMPLIANCE_UNREGULATED:.2f}; regulated and "
                        f"receiver authorised {engine.COMPLIANCE_REGULATED_AUTHORISED:.2f}; "
                        f"regulated and not {engine.COMPLIANCE_REGULATED_UNAUTHORISED:.2f}"},
        ]),
        hide_index=True, width="stretch",
        column_config={
            "factor": st.column_config.TextColumn("Factor", width="small"),
            "weight": st.column_config.NumberColumn("Weight", format="%.2f", width="small"),
            "formula": st.column_config.TextColumn("Formula", width="large"),
        },
    )

    st.markdown('<div class="sect">Gates</div>', unsafe_allow_html=True)
    st.markdown(
        f"- Reject any pairing scoring below **{engine.MIN_SCORE_DEFAULT:.0f}**.\n"
        f"- Reject any haul beyond **max_km x {engine.DISTANCE_HARD_LIMIT}**. Between max_km "
        "and that limit a match is listed but scores zero on proximity, and is labelled.\n"
        f"- Reject anything under **{engine.MIN_MATCH_TONNES:.0f} tonne** a year.\n"
        "- A facility is never matched to itself."
    )

    st.markdown('<div class="sect">Valuation, per year</div>', unsafe_allow_html=True)
    st.code(
        "material_value  = matched_t x substitution_ratio x virgin_value\n"
        f"disposal_saved  = matched_t x disposal_rate      (default Rs {engine.DISPOSAL_COST_DEFAULT}/t)\n"
        f"transport_cost  = matched_t x road_km x {engine.FREIGHT_RATE}      (Rs/t-km, bulk road)\n"
        "processing_cost = matched_t x "
        f"{{none {engine.PROCESSING_COST['none']}, simple {engine.PROCESSING_COST['simple']}, "
        f"moderate {engine.PROCESSING_COST['moderate']}, complex {engine.PROCESSING_COST['complex']}}}\n"
        "net = material_value + disposal_saved - transport_cost - processing_cost",
        language="text",
    )

    st.markdown('<div class="sect">Every assumption, stated</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
- **Distance** is haversine great-circle distance multiplied by
  **{engine.ROAD_CIRCUITY_FACTOR:.2f}** for road circuity. No routing engine, no traffic, no
  terrain. A hill road or a river crossing will be worse than this says.
- **Freight** is **Rs {engine.FREIGHT_RATE}/tonne-km** by bulk road, full truck loads; part
  loads and return-empty legs cost more. **Rail** is offered at
  **Rs {engine.RAIL_RATE}/tonne-km** plus **Rs {engine.RAIL_TERMINAL_COST}/tonne** of terminal
  handling covering both road legs, and is taken only above
  **{engine.RAIL_MIN_KM} km** and **{engine.RAIL_MIN_TONNES:,} t/yr** and only when it is
  genuinely cheaper door to door. Each match reports which mode it assumes.
- **Pipeline** transfer for waste heat and coke oven gas is priced separately at
  **Rs {engine.PIPELINE_RATE:.0f}/tonne-km** as an amortised figure.
- **Disposal avoided** defaults to **Rs {engine.DISPOSAL_COST_DEFAULT}/tonne**, overridden per
  material where that is wrong: a hazardous stream routed to a TSDF costs several times this,
  a captive ash pond rather less. For fly ash the saving is partly a compliance cost rather
  than a landfill fee, since utilisation is already mandatory.
- **Processing costs** are order-of-magnitude figures per tonne handled, not quotations.
- **Virgin material values** are indicative Indian market levels, not contract prices.
- **CO2 avoided** counts the displaced virgin material's production emissions only. It is not
  a verified carbon credit. Process CO2 reuse is **not** sequestration.
- **max_share** is anchored to Indian standards where they exist: IS 1489 and IS 3812 for fly
  ash in PPC, IS 455 for slag cement, IS 383 for recycled aggregate, CPCB co-processing
  guidance for regulated and mixed streams.
- **Timing** divides overlapping active months by twelve, so a six-month crushing season
  feeding a year-round kiln scores 0.50.
- **Capacities in the sample registry** are representative of plants of that type. They are
  not audited plant data.
- **Rupee values** are the gross prize across both parties.
- **Determinism**: no language model produces any figure here. The explanation text receives
  finished numbers and only arranges them into sentences.
- **The map** draws state boundaries from a simplified public GeoJSON bundled with the app,
  and Plotly's own basemap is switched off, so nothing is fetched from the internet at render
  time. State fill encodes one chosen metric; it is not a political boundary statement.
"""
    )

    st.markdown('<div class="sect">Known limits of this model</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
- **The quantity factor measures the receiver, not the supplier.** It is
  `matched_t / ceiling`, so any supplier whose output exceeds the receiver's ceiling scores
  1.00 - whether it places 90% of its output or 3%. Each match therefore also reports
  `supplier_share`, and the audit panel says so explicitly.
- **Scores are pairwise, so `matched_tpa` over-commits supply.** A supplier able to serve six
  receivers appears at full tonnage against each. The engine adds a greedy best-score-first
  allocation: `allocated_tpa` is a feasible plan that never promises the same tonne twice. At
  the current threshold it places **{engine.tonnes(summary['allocated_tonnes'])}** for
  **{engine.inr(summary['allocated_value'])}**, against a headline
  **{engine.tonnes(summary['tonnes_diverted'])}** for
  **{engine.inr(summary['value_unlocked'])}**. Neither is a plan anyone has agreed to.
- **Energy streams are forced into a mass model.** Waste heat has no tonnage; its registry
  figure is tonnes of coal equivalent, and coke oven gas is priced on a natural-gas
  displacement basis.
- **Knowledge base coverage is the ceiling on discovery.** {len(kb.SUBSTITUTIONS)} substitutions
  across {len(kb.materials())} materials is a screening tool, not an encyclopaedia.
- **No quality specification is checked.** Two facilities may both handle 'fly ash' and still
  be incompatible on fineness, loss on ignition or chloride.
"""
    )

    st.markdown('<div class="sect">Beyond the substitution table</div>',
                unsafe_allow_html=True)
    st.markdown(
        f"""
Three passes run on top of the pairwise scoring. None of them changes a score.

- **Analogue discovery.** The substitution table can only match a stream it already knows,
  which makes the genuinely hidden exchanges invisible. Every material carries a profile of
  {len(kb.PROFILE_KEYS)} indicative properties - silica, alumina, lime, iron oxide, sulphur,
  recoverable metal, organic carbon, calorific value, moisture, bulk density, alkalinity -
  and an unplaced stream is compared against all {len(kb.MATERIAL_PROFILES)} profiles by
  weighted Euclidean distance. Deterministic, offline, no model and no embeddings: the same
  stream always returns the same analogues, and each one names the properties that agree and
  the one that does not, so it can be argued with. **These profiles are indicative typical
  compositions, not an assay of anybody's actual waste, and they feed nothing but the
  resemblance ranking.** A suggestion is a reason to send a sample to a laboratory.
- **Multi-hop chains.** A depth-first walk over the match graph finds sequences where one
  plant receives a by-product and places its own. Each hop must move a different material and
  no facility may repeat, so a chain describes transformation rather than a stream being
  passed along. Chains are ranked by their weakest link. Chain totals add the individual
  exchanges and will overstate them where hops compete for the same tonnage.
- **Network optimisation.** The greedy allocation takes matches best score first, which is
  feasible but not optimal - score measures practicality, not value. The optimiser solves the
  whole allocation as a linear program (SciPy HiGHS), maximising total net value subject to
  every supplier's output, every receiver's intake and each receiver's per-material ceiling.
  Loss-making exchanges fall to zero on their own rather than by a rule. If SciPy is missing
  the app falls back to the greedy plan and says so.

**Circularity** is the share of by-product tonnage in the registry that finds a home. The
denominator is every tonne offered, the unplaced streams included, so it is deliberately hard
to move. **Virgin material avoided** applies each substitution ratio to the tonnage placed.
**Water footprint is not modelled** - there is no defensible per-tonne figure for most of
these streams, and inventing one would undermine every number that is defensible.
"""
    )

    st.markdown(f'<div class="sect">Knowledge base: {len(kb.SUBSTITUTIONS)} substitutions</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">The whole basis for matching, browsable. Nothing is matched that is '
        'not in this table.</p>',
        unsafe_allow_html=True,
    )
    st.dataframe(
        kb_table(), hide_index=True, width="stretch", height=460,
        column_config={
            "material": st.column_config.TextColumn("By-product", width="medium"),
            "application": st.column_config.TextColumn("Application", width="medium"),
            "replaces": st.column_config.TextColumn("Replaces", width="medium"),
            "accepting sectors": st.column_config.TextColumn("Accepting sectors", width="medium"),
            "ratio": st.column_config.NumberColumn("Ratio", format="%.2f", width="small"),
            "max share": st.column_config.NumberColumn("Max share", format="%.2f", width="small"),
            "max km": st.column_config.NumberColumn("Max km", format="%.0f", width="small"),
            "CO2 t/t": st.column_config.NumberColumn("CO2 t/t", format="%.2f", width="small"),
            "virgin value Rs/t": st.column_config.NumberColumn("Virgin Rs/t", format="%.0f"),
            "disposal Rs/t": st.column_config.NumberColumn("Disposal Rs/t", format="%.0f"),
            "note": st.column_config.TextColumn("Practical catch", width="large"),
        },
    )

    st.markdown('<div class="sect">Registry in use</div>', unsafe_allow_html=True)
    st.dataframe(facilities, hide_index=True, width="stretch", height=300)
