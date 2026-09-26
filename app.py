"""Industrial Symbiosis Portal - Streamlit interface.

Finds exchanges where one plant's by-product can replace another's virgin raw
material, scores how practical each one is, and prices it. Every figure on
screen is computed in engine.py; this module only arranges and draws them.

Presentation, accessibility controls and the bilingual chrome live in ui.py and
i18n.py so this file stays about the content.
"""

from __future__ import annotations

import io
import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import blending
import carbon
import conformance
import engine
import explain
import i18n
import kb
import materials
import specs
import ui

st.set_page_config(
    page_title="Industrial Symbiosis Portal",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui.init_state()
ui.inject_styles()

SUPPLIER_COLOUR = ui.SUPPLIER_COLOUR
RECEIVER_COLOUR = ui.RECEIVER_COLOUR
LOSS_COLOUR = ui.LOSS_COLOUR
BLUE_SEQUENTIAL = ui.BLUE_SEQUENTIAL
GEOJSON_PATH = "data/india_states.geojson"

CHART_FONT = dict(color="#1a1f2b", size=12, family="Noto Sans, Arial, sans-serif")
HOVER_STYLE = dict(bgcolor="#ffffff", bordercolor="#5a6472",
                   font=dict(color="#1a1f2b", size=12))

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


def flag_column(frame: pd.DataFrame) -> pd.Series:
    """Short plain-text flags, so a row's status never rests on colour alone."""
    flags = []
    for row in frame.itertuples(index=False):
        marks = []
        if float(row.net_value) < 0:
            marks.append("loss")
        if bool(row.beyond_max_km):
            marks.append("past limit")
        if str(row.hazard) == "regulated":
            marks.append("regulated")
        flags.append(", ".join(marks) or "-")
    return pd.Series(flags, index=frame.index)


def render_narrative(row):
    story = explain.explain(row)
    loss = float(row["net_value"]) < 0
    st.markdown(
        f'<div class="note{" loss" if loss else ""}">{story["headline"]}</div>',
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
# Chart builders for the materials screens
# ======================================================================

def bullet_chart(report: dict, height_per_row: int = 34) -> go.Figure:
    """One horizontal bar per limit, with the limit drawn on it as a line.

    Every value that has a threshold is shown against that threshold rather than
    written out. Bars are scaled to the limit, so 1.0 on the axis IS the limit
    and the eye reads compliance as "left of the line" without arithmetic.
    """
    rows = [r for r in report["results"] if r["measured"]]
    if not rows:
        return None

    labels, values, colours, texts = [], [], [], []
    for result in rows:
        label = " + ".join(materials.PROPERTY_LABELS.get(p.strip(), p.strip())
                           for p in result["property"].split("+"))
        # Both directions share one axis, so the label has to say which way
        # this row has to go: "at most" bars pass to the left of the line,
        # "at least" bars pass to the right.
        label += "  (at most)" if result["operator"] == "<=" else "  (at least)"
        threshold = result["threshold"] or 1.0
        ratio = result["actual"] / threshold if threshold else 0.0
        labels.append(label)
        values.append(ratio)
        colours.append(ui.STATUS_GOOD if result["passes"] else ui.STATUS_BAD)
        word = "PASS" if result["passes"] else "FAIL"
        texts.append(f'{result["actual"]:g} / {result["operator"]} '
                     f'{result["threshold"]:g}  {word}')

    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h",
        marker=dict(color=colours, line=dict(width=0)),
        text=texts, textposition="outside", textfont=dict(size=10),
        hoverinfo="text",
        hovertext=[
            f'<b>{lab}</b><br>measured {r["actual"]:g}<br>'
            f'limit {r["operator"]} {r["threshold"]:g}<br>'
            f'{"inside" if r["passes"] else "outside"} by '
            f'{abs(r["margin"]):.3g} ({abs(r["headroom_frac"]) * 100:.0f}%)'
            for lab, r in zip(labels, rows)],
    ))
    # The limit itself, at 1.0 on every row because each bar is scaled to it.
    fig.add_shape(type="line", x0=1, x1=1, y0=-0.5, y1=len(labels) - 0.5,
                  line=dict(color="#1a1f2b", width=2, dash="dash"))
    fig.add_annotation(x=1, y=len(labels) - 0.5, text="limit", showarrow=False,
                       yshift=12, font=dict(size=10, color="#1a1f2b"))
    fig.update_layout(
        height=height_per_row * len(labels) + 90,
        margin=dict(l=0, r=130, t=24, b=6),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff", font=CHART_FONT,
        xaxis=dict(title="measured value as a multiple of its limit",
                   gridcolor="#e4e7ec", zeroline=False,
                   range=[0, max(1.35, max(values) * 1.35)]),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", automargin=True,
                   autorange="reversed"),
        hoverlabel=HOVER_STYLE, showlegend=False, bargap=0.35,
    )
    return fig


OXIDE_SEGMENTS = [
    ("sio2", "SiO2", "#1f5fa9"),
    ("al2o3", "Al2O3", "#5f93cb"),
    ("fe2o3", "Fe2O3", "#9fc1e3"),
    ("cao", "CaO", "#0b3c6b"),
    ("loi", "Loss on ignition", "#8a93a3"),
]


def composition_bar(props: dict) -> go.Figure:
    """A single 100% stacked bar: what the stream is actually made of."""
    named = [(key, label, colour) for key, label, colour in OXIDE_SEGMENTS
             if props.get(key) is not None]
    accounted = sum(float(props[key]) for key, _, _ in named)
    segments = [(label, float(props[key]), colour) for key, label, colour in named]
    remainder = max(0.0, 100.0 - accounted)
    if remainder > 0.05:
        segments.append(("Other / unaccounted", remainder, "#d5d9e0"))

    fig = go.Figure()
    for label, value, colour in segments:
        fig.add_trace(go.Bar(
            x=[value], y=["composition"], orientation="h", name=label,
            marker=dict(color=colour, line=dict(width=1, color="#ffffff")),
            text=[f"{label} {value:.1f}%" if value >= 7 else ""],
            textposition="inside", insidetextanchor="middle",
            textfont=dict(size=10, color="#ffffff"),
            hovertemplate=f"<b>{label}</b><br>%{{x:.2f}}%<extra></extra>",
        ))
    fig.update_layout(
        barmode="stack", height=168, margin=dict(l=0, r=0, t=6, b=46),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=CHART_FONT,
        xaxis=dict(range=[0, 100], showgrid=False, ticksuffix="%", zeroline=False),
        yaxis=dict(showticklabels=False, showgrid=False),
        legend=dict(orientation="h", yanchor="top", y=-0.55, x=0,
                    font=dict(size=10)),
        hoverlabel=HOVER_STYLE,
    )
    return fig


# ======================================================================
# Chrome: utility bar, masthead, sidebar navigation
# ======================================================================

# Short labels. The old tab strip overflowed into a horizontal scroll once the
# materials layer was added, which reads as unfinished; a vertical nav carries
# ten sections without any of them hiding.
SECTIONS = [
    ("grading", "Grading"),
    ("cascade", "Value cascade"),
    ("blend", "Blending"),
    ("carbon", "Carbon & CCTS"),
    ("mine", "My plant"),
    ("network", "Network"),
    ("matches", "Matches"),
    ("chains", "Chains"),
    ("gaps", "Gaps"),
    ("method", "Method"),
]
SECTION_KEYS = [key for key, _ in SECTIONS]
SECTION_LABELS = dict(SECTIONS)

ui.utility_bar()
ui.masthead()

with st.sidebar:
    st.markdown('<p class="navtitle">Sections</p>', unsafe_allow_html=True)
    section = st.radio(
        "Section", SECTION_KEYS, format_func=lambda k: SECTION_LABELS[k],
        label_visibility="collapsed", key="nav_section",
    )
    st.markdown("---")
    st.markdown(f"### {ui.tr('sb_registry')}")
    source = st.radio("Source", [ui.tr("sb_sample"), ui.tr("sb_upload")],
                      label_visibility="collapsed")

    csv_text = sample_registry_text()
    if source == ui.tr("sb_upload"):
        uploaded = st.file_uploader("Facility registry (CSV)", type=["csv"])
        if uploaded is not None:
            csv_text = uploaded.getvalue().decode("utf-8", errors="replace")
        else:
            st.info("No file yet - showing the sample registry.")

    st.download_button(ui.tr("sb_template"), data=engine.template_csv(),
                       file_name="registry_template.csv", mime="text/csv",
                       width="stretch")

    st.markdown(f"### {ui.tr('sb_threshold')}")
    min_score = st.slider(
        ui.tr("sb_min_score"), 0, 90, int(engine.MIN_SCORE_DEFAULT), 1,
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
optimised, opt_report, chains = run_extras(csv_text, float(min_score))
impact = engine.circularity(matches, facilities)

if ui.lang() != "en":
    st.markdown(f'<div class="note">{ui.tr("hindi_note")}</div>', unsafe_allow_html=True)

st.markdown(f'<p class="caveat">{ui.tr("prototype")}</p>', unsafe_allow_html=True)

if problems:
    with st.expander(f"{ui.tr('data_quality')} ({len(problems)})", expanded=False):
        for problem in problems:
            st.warning(problem, icon=None)

if facilities.empty:
    st.error("No usable facilities in this registry. Check the columns against the template.")
    st.stop()

unmatched_tonnes = float(gaps["output_tpa"].sum()) if len(gaps) else 0.0
ui.stat_row([
    ui.stat_block(ui.tr("kpi_exchanges"), f"{summary['exchanges']:,}",
                  f"{summary['suppliers']} {ui.tr('suppliers_receivers')} &middot; "
                  f"{summary['receivers']} {ui.tr('receivers')}"),
    ui.stat_block(ui.tr("kpi_tonnes"), engine.tonnes(summary["tonnes_diverted"]),
                  ui.tr("per_year")),
    ui.stat_block(ui.tr("kpi_co2"), engine.tonnes(summary["co2_avoided_t"]),
                  ui.tr("per_year")),
    ui.stat_block(ui.tr("kpi_value"), engine.inr(summary["value_unlocked"]),
                  f"{summary['loss_making']} {ui.tr('at_a_loss')}",
                  bad=summary["loss_making"] > 0),
    ui.stat_block(ui.tr("kpi_unmatched"), engine.tonnes(unmatched_tonnes),
                  f"{len(gaps)} {ui.tr('streams_unplaced')}"),
    ui.stat_block(ui.tr("kpi_circularity"), f"{impact['circularity_pct']:.1f}%",
                  f"{ui.tr('of_produced')} {engine.tonnes(impact['total_byproduct_t'])}"),
], columns=6)

st.markdown(
    '<p class="caveat">Tonnes diverted and value unlocked deduplicate by supplier and '
    'material. A feasible allocation across several receivers, which never promises the '
    f'same tonne twice, places {engine.tonnes(summary["allocated_tonnes"])} for '
    f'{engine.inr(summary["allocated_value"])} - see Method.</p>',
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="breadcrumb">{ui.tr("home")} &rsaquo; '
    f'<b>{SECTION_LABELS[section]}</b></div>',
    unsafe_allow_html=True,
)

QUALIFY_COLOUR = ui.SUPPLIER_COLOUR       # navy - qualifies
BLOCKED_COLOUR = "#b9c0cc"                # grey - does not

# ======================================================================
# 0. Material grading - property vectors against written specifications
# ======================================================================

GRADE_MEANING = {
    "A": "passes every limit with 15% headroom or more",
    "B": "passes every limit, but with little margin",
    "C": "fails one limit by less than 20%",
    "D": "fails by more than that, or a required property is not measured",
}


def limit_table(report: dict) -> pd.DataFrame:
    """One row per limit: what was required, what was measured, and the gap."""
    rows = []
    for result in report["results"]:
        prop = result["property"]
        label = " + ".join(materials.PROPERTY_LABELS.get(p.strip(), p.strip())
                           for p in prop.split("+"))
        rows.append({
            "property": label,
            "required": f'{result["operator"]} {result["threshold"]:g}',
            "actual": result["actual"],
            "margin": result["margin"],
            "headroom %": (result["headroom_frac"] * 100
                           if result["headroom_frac"] is not None else None),
            "verdict": ("PASS" if result["passes"]
                        else ("NOT MEASURED" if not result["measured"] else "FAIL")),
            "basis": result["unit_note"],
        })
    for ratio in report["ratios"]:
        rows.append({
            "property": ratio["expression"],
            "required": f'> {ratio["threshold"]:g}',
            "actual": ratio["actual"],
            "margin": (ratio["actual"] - ratio["threshold"]
                       if ratio["actual"] is not None else None),
            "headroom %": None,
            "verdict": ("PASS" if ratio["passes"]
                        else ("NOT MEASURED" if not ratio["measured"] else "FAIL")),
            "basis": ratio["description"],
        })
    return pd.DataFrame(rows)


if section == "grading":
    stream = st.selectbox(ui.tr("mg_pick"), materials.materials(), index=1,
                          key="grade_material", label_visibility="collapsed")
    profile = materials.properties_of(stream) or {}
    measured = materials.measured_properties(stream)
    ladder = conformance.cascade(stream)

    spec_names = [r["spec"] for r in ladder["rungs"]]
    # Open on the most valuable rung the stream actually reaches. Opening on one
    # it misses makes an edge case look like the headline.
    default_spec = (ladder["best_qualifying"]["spec"]
                    if ladder["best_qualifying"] else spec_names[-1])
    picked_spec = st.selectbox(ui.tr("mg_detail"), spec_names,
                               index=spec_names.index(default_spec),
                               key="grade_spec", label_visibility="collapsed")
    report = conformance.grade(stream, picked_spec)

    marginal = report["passes"] and report["grade"] == "B"
    st.markdown(
        ui.grade_badge(
            report["grade"], picked_spec,
            f'{report["standard"]} &middot; basis: {report["confidence"]} '
            f'&middot; worth {engine.inr(report["value_inr_t"])}/t if it qualifies',
            "MEETS THIS SPECIFICATION" if report["passes"]
            else f'FAILS {len(report["failures"])} LIMIT(S)',
            report["passes"], marginal),
        unsafe_allow_html=True,
    )

    binding = report["binding"]
    chips = [
        ui.chip(f'{len(ladder["qualifying"])} of {len(ladder["rungs"])} uses',
                "accent"),
        ui.chip(f'best {engine.inr(ladder["best_qualifying_value"])}/t', "accent"),
        ui.chip(f'{engine.tonnes(profile.get("annual_tpa", 0))}/yr'),
        ui.chip(f'disposal Rs {profile.get("disposal_inr_t", 0):,.0f}/t'),
    ]
    if binding:
        tone = "good" if binding["headroom_frac"] >= 0.15 else (
            "warn" if binding["headroom_frac"] >= 0 else "bad")
        chips.append(ui.chip(
            f'binding: {materials.PROPERTY_LABELS.get(binding["property"], binding["property"])} '
            f'{binding["headroom_frac"] * 100:+.0f}%', tone))
    st.markdown(ui.chip_row(chips), unsafe_allow_html=True)

    left, right = st.columns([1.25, 1], gap="medium")

    with left:
        fig = bullet_chart(report)
        if fig is not None:
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        unmeasured = [r for r in report["results"] if not r["measured"]]
        if unmeasured:
            st.markdown(ui.chip_row([
                ui.chip(f'not measured: '
                        f'{materials.PROPERTY_LABELS.get(r["property"], r["property"])}',
                        "bad") for r in unmeasured]), unsafe_allow_html=True)
        for ratio in report["ratios"]:
            tone = "good" if ratio["passes"] else "bad"
            actual = f'{ratio["actual"]:.2f}' if ratio["actual"] is not None else "n/a"
            st.markdown(ui.chip_row([ui.chip(
                f'{ratio["expression"]} = {actual} (needs &gt; {ratio["threshold"]:g})',
                tone)]), unsafe_allow_html=True)

    with right:
        st.plotly_chart(composition_bar(measured), width="stretch",
                        config={"displaylogo": False})
        st.markdown(ui.card_grid([
            ui.spec_card(r["spec"], r["passes"], r["grade"],
                         engine.inr(r["value_inr_t"]),
                         marginal=r["passes"] and r["grade"] == "B")
            for r in ladder["rungs"][:8]
        ]), unsafe_allow_html=True)

    with st.expander("Full assessment, limit by limit", expanded=False):
        st.dataframe(
            limit_table(report), hide_index=True, width="stretch",
            column_config={
                "property": st.column_config.TextColumn("Property", width="medium"),
                "required": st.column_config.TextColumn("Required", width="small"),
                "actual": st.column_config.NumberColumn("Measured", format="%.4g",
                                                        width="small"),
                "margin": st.column_config.NumberColumn("Margin", format="%.4g",
                                                        width="small"),
                "headroom %": st.column_config.NumberColumn("Headroom %",
                                                            format="%.1f",
                                                            width="small"),
                "verdict": st.column_config.TextColumn("Verdict", width="small"),
                "basis": st.column_config.TextColumn("Basis of the limit",
                                                     width="large"),
            },
        )
        st.markdown(
            f'<p class="caveat">{report["note"]}</p>'
            f'<p class="caveat">{profile.get("note", "")}</p>'
            '<p class="caveat">Representative composition for a stream of this '
            'type, not an assay of a specific consignment. A real trade needs a '
            'laboratory certificate for the actual material.</p>',
            unsafe_allow_html=True,
        )


# ======================================================================
# 0a. Value cascade
# ======================================================================

if section == "cascade":
    stream = st.selectbox(ui.tr("mg_pick"), materials.materials(), index=1,
                          key="cascade_material", label_visibility="collapsed")
    ladder = conformance.cascade(stream)
    best = ladder["best_qualifying"]

    ui.stat_row([
        ui.stat_block(ui.tr("mg_discount"),
                      engine.inr(ladder["quality_discount"]) + " /t",
                      f'below {ladder["library_best"][:38]}', bad=True),
        ui.stat_block(ui.tr("mg_best"),
                      engine.inr(ladder["best_qualifying_value"]) + " /t",
                      best["spec"][:40] if best else "nothing in the library"),
        ui.stat_block(ui.tr("mg_qualifies"),
                      f'{len(ladder["qualifying"])} / {len(ladder["rungs"])}', ""),
    ], columns=3)

    rungs = list(reversed(ladder["rungs"]))
    current = best["spec"] if best else None
    ladder_fig = go.Figure(go.Bar(
        x=[r["value_inr_t"] for r in rungs],
        y=[r["spec"] for r in rungs],
        orientation="h",
        marker=dict(
            color=[ui.ACCENT if r["passes"] else ui.NEUTRAL_GREY for r in rungs],
            line=dict(width=0)),
        text=[(f'{engine.inr(r["value_inr_t"])}  &#10003;'
               + ("  &#9664; goes here today" if r["spec"] == current else ""))
              if r["passes"] else
              f'{engine.inr(r["value_inr_t"])}  &#128274; grade {r["grade"]}'
              for r in rungs],
        textposition="outside", textfont=dict(size=10),
        hoverinfo="text",
        hovertext=[
            f'<b>{r["spec"]}</b><br>{engine.inr(r["value_inr_t"])}/t'
            f'<br>{"Qualifies" if r["passes"] else "Locked - grade " + r["grade"]}'
            + (f'<br>Binding: {r["binding"]["property"]} '
               f'({r["binding"]["headroom_frac"] * 100:+.0f}%)'
               if r["binding"] else "")
            for r in rungs],
    ))
    ladder_fig.update_layout(
        height=34 * len(rungs) + 80, margin=dict(l=0, r=190, t=6, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff", font=CHART_FONT,
        xaxis=dict(title="Rs per tonne of the application", gridcolor="#e4e7ec",
                   zeroline=False,
                   range=[0, max(r["value_inr_t"] for r in rungs) * 1.55]),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", automargin=True),
        hoverlabel=HOVER_STYLE, showlegend=False, bargap=0.3,
    )
    st.plotly_chart(ladder_fig, width="stretch", config={"displaylogo": False})

    upgrade = ladder["nearest_upgrade"]
    if upgrade:
        blockers = [f for f in upgrade["failures"] if f["measured"]]
        if blockers:
            worst = max(blockers, key=lambda f: abs(f["headroom_frac"]))
            st.markdown(ui.chip_row([
                ui.chip(f'next rung: {upgrade["spec"][:44]}', "accent"),
                ui.chip(f'{engine.inr(upgrade["value_inr_t"])}/t', "accent"),
                ui.chip(f'blocked by '
                        f'{materials.PROPERTY_LABELS.get(worst["property"], worst["property"])} '
                        f'{abs(worst["headroom_frac"]) * 100:.0f}% outside', "bad"),
                ui.chip(f'worth +{engine.inr(upgrade["value_inr_t"] - ladder["best_qualifying_value"])}/t',
                        "good"),
            ]), unsafe_allow_html=True)


# ======================================================================
# 0b. Blend to specification
# ======================================================================

if section == "blend":
    st.markdown(f'<div class="sect">{ui.tr("bl_heading")}</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">Every property modelled here mixes linearly by mass, so '
        'each limit becomes a linear inequality in the blend ratio and can be '
        'solved exactly. Intersecting all of them gives the range of ratios that '
        'satisfies the whole specification - or the pair of limits that pull in '
        'opposite directions and make it impossible. This is value created by '
        'chemistry rather than by trucking: a stream that fails on its own can '
        'clear the specification blended, and nothing has to be built.</p>',
        unsafe_allow_html=True,
    )

    stream_names = materials.materials()
    b1, b2, b3 = st.columns(3)
    blend_a = b1.selectbox(ui.tr("bl_stream_a"), stream_names,
                           index=stream_names.index("Fly ash (Talcher TPS)"),
                           key="blend_a")
    blend_b = b2.selectbox(ui.tr("bl_stream_b"), stream_names,
                           index=stream_names.index("Fly ash (Vindhyachal STPS)"),
                           key="blend_b")
    target = b3.selectbox(ui.tr("bl_target"), specs.specs(),
                          index=specs.specs().index(
                              "Fly ash for structural concrete (IS 3812 Part 1)"),
                          key="blend_spec")

    result = blending.blend_to_spec(blend_a, blend_b, target)
    alone_a = conformance.grade(blend_a, target)
    alone_b = conformance.grade(blend_b, target)

    if not result["feasible"]:
        st.markdown(
            f'<div class="note loss"><strong>No blend of these two streams meets '
            f'{target}.</strong> {result["reason"]}</div>',
            unsafe_allow_html=True,
        )
        if result["blocking"]:
            st.dataframe(
                pd.DataFrame([{
                    "property": materials.PROPERTY_LABELS.get(
                        b["property"], b["property"]),
                    "required": f'{b["operator"]} {b["threshold"]:g}',
                    f"{blend_a[:22]}": b["value_a"],
                    f"{blend_b[:22]}": b["value_b"],
                    "why": (b["reason"] or
                            f'satisfied only for blend ratios '
                            f'{b["lo"]:.0%} to {b["hi"]:.0%}'),
                } for b in result["blocking"]]),
                hide_index=True, width="stretch",
                column_config={
                    "property": st.column_config.TextColumn("Property",
                                                            width="medium"),
                    "required": st.column_config.TextColumn("Required",
                                                            width="small"),
                    "why": st.column_config.TextColumn("Why it cannot be met",
                                                       width="large"),
                },
            )
        st.markdown(
            '<p class="caveat">Two limits that are each satisfiable on their own '
            'can still be jointly impossible: one needs more of A and the other '
            'needs less. That is what the rows above show.</p>',
            unsafe_allow_html=True,
        )
    else:
        f = result["f_recommended"]
        report = result["report"]
        ui.stat_row([
            ui.stat_block(ui.tr("bl_recommended"),
                          f'{f:.0%} / {1 - f:.0%}',
                          f'{blend_a[:26]} / {blend_b[:26]}'),
            ui.stat_block(ui.tr("bl_feasible"),
                          f'{result["f_min"]:.0%} - {result["f_max"]:.0%}',
                          f'mass fraction of {blend_a[:28]}'),
            ui.stat_block("Blend verdict",
                          ("PASS grade " + report["grade"]) if report["passes"]
                          else "FAIL",
                          target[:44]),
            ui.stat_block("Value of the target",
                          engine.inr(report["value_inr_t"]) + " /t",
                          report["standard"]),
        ], columns=4)

        headline = (
            f'<strong>Blend {f:.0%} {blend_a} with {1 - f:.0%} {blend_b} and the '
            f'mix meets {target}</strong>, at grade {report["grade"]}. '
        )
        if not alone_a["passes"] and alone_b["passes"]:
            headline += (f'{blend_a} cannot meet this specification on its own; '
                         f'the blend places {f:.0%} of it anyway.')
        elif not alone_a["passes"] and not alone_b["passes"]:
            headline += "Neither stream meets it alone."
        st.markdown(f'<div class="note">{headline}</div>', unsafe_allow_html=True)
        st.markdown(
            f'<p class="caveat">Ratio chosen by {result["rationale"]}. '
            'Rounded inward to the nearest 1% so a dosing error cannot push the '
            'mix outside the specification.</p>',
            unsafe_allow_html=True,
        )

        st.markdown(f'<div class="sect">{ui.tr("bl_before_after")}</div>',
                    unsafe_allow_html=True)
        props_a = materials.measured_properties(blend_a)
        props_b = materials.measured_properties(blend_b)
        rows = []
        for check in report["results"]:
            expression = check["property"]
            value_a, _ = conformance.resolve(expression, props_a)
            value_b, _ = conformance.resolve(expression, props_b)
            rows.append({
                "property": " + ".join(
                    materials.PROPERTY_LABELS.get(p.strip(), p.strip())
                    for p in expression.split("+")),
                "required": f'{check["operator"]} {check["threshold"]:g}',
                blend_a[:24]: value_a,
                blend_b[:24]: value_b,
                "blend": check["actual"],
                "headroom %": (check["headroom_frac"] * 100
                               if check["headroom_frac"] is not None else None),
                "verdict": "PASS" if check["passes"] else "FAIL",
            })
        st.dataframe(
            pd.DataFrame(rows), hide_index=True, width="stretch",
            column_config={
                "property": st.column_config.TextColumn("Property", width="medium"),
                "required": st.column_config.TextColumn("Required", width="small"),
                blend_a[:24]: st.column_config.NumberColumn(format="%.4g"),
                blend_b[:24]: st.column_config.NumberColumn(format="%.4g"),
                "blend": st.column_config.NumberColumn("Blend", format="%.4g"),
                "headroom %": st.column_config.NumberColumn("Headroom %",
                                                            format="%.1f",
                                                            width="small"),
                "verdict": st.column_config.TextColumn("Verdict", width="small"),
            },
        )

    st.markdown(
        '<p class="caveat"><strong>What this does not prove.</strong> Linear '
        'mixing is sound for composition and reasonable for fineness and loss on '
        'ignition. It is not a substitute for the performance tests the standards '
        'also require - lime reactivity, soundness, strength activity index - '
        'which cannot be predicted from an assay. A feasible blend here is a '
        'candidate for a trial mix, not a certificate.</p>',
        unsafe_allow_html=True,
    )

# ======================================================================
# 0c. Carbon and CCTS
# ======================================================================

if section == "carbon":
    st.markdown(f'<div class="sect">{ui.tr("cb_heading")}</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">India\'s Carbon Credit Trading Scheme sets '
        '<strong>intensity</strong> targets - tCO2e per tonne of product - not '
        'absolute caps. Raising the supplementary cementitious share lowers the '
        'clinker factor, which lowers the intensity the plant is legally measured '
        'on. That is why a by-product is worth more than the clinker it displaces: '
        'it also moves the plant\'s compliance position.</p>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1.4, 2])
    receiving = c1.selectbox(ui.tr("cb_plant"), carbon.plants(), index=1,
                             key="carbon_plant")
    price = c2.slider(ui.tr("cb_price"), min_value=500, max_value=6000,
                      value=int(carbon.DEFAULT_CERTIFICATE_PRICE), step=100,
                      key="carbon_price",
                      help="Indian certificate trading has no settled price yet. "
                           "Every rupee figure on this tab moves with this slider - "
                           "it is an assumption, not a forecast.")

    profile = carbon.plant(receiving) or {}
    baseline = carbon.assess(receiving, profile.get("baseline_scm_share", 0.0), price)

    # Sourcing options. SCM share is raised to 35%, the IS 1489 ceiling for fly
    # ash in PPC, for every option that can supply it.
    TARGET_SHARE = 0.35
    SPEC = "Fly ash for structural concrete (IS 3812 Part 1)"
    good_ash, poor_ash = "Fly ash (Vindhyachal STPS)", "Fly ash (Talcher TPS)"
    mix = blending.blend_to_spec(poor_ash, good_ash, SPEC)

    def margin_of(report):
        if report["binding"] is None or report["binding"]["headroom_frac"] is None:
            return None
        return report["binding"]["headroom_frac"] * 100

    grade_good = conformance.grade(good_ash, SPEC)
    grade_poor = conformance.grade(poor_ash, SPEC)

    options = [
        {"label": "Stay on clinker (no change)",
         "scm_share": profile.get("baseline_scm_share", 0.0),
         "cost_inr_t": 4200, "quality_margin": None, "meets_spec": True},
        {"label": f"Take {good_ash} to 35%", "scm_share": TARGET_SHARE,
         "cost_inr_t": 1150, "quality_margin": margin_of(grade_good),
         "meets_spec": grade_good["passes"]},
        {"label": f"Take {poor_ash} to 35%", "scm_share": TARGET_SHARE,
         "cost_inr_t": 700, "quality_margin": margin_of(grade_poor),
         "meets_spec": grade_poor["passes"]},
    ]
    if mix["feasible"]:
        f = mix["f_recommended"]
        options.append({
            "label": f"Take the {f:.0%}/{1 - f:.0%} blend to 35%",
            "scm_share": TARGET_SHARE,
            "cost_inr_t": round(f * 700 + (1 - f) * 1150),
            "quality_margin": margin_of(mix["report"]),
            "meets_spec": mix["report"]["passes"],
        })

    rows = carbon.compare_options(receiving, options, price)
    chosen = carbon.assess(receiving, TARGET_SHARE, price)

    ui.stat_row([
        ui.stat_block("Baseline intensity", f'{baseline["actual_gei"]:.3f}',
                      f'tCO2e/t at {baseline["baseline_scm_share"]:.0%} SCM'),
        ui.stat_block("Target intensity", f'{baseline["target_gei"]:.3f}',
                      "tCO2e/t under CCTS"),
        ui.stat_block("Intensity at 35% SCM", f'{chosen["actual_gei"]:.3f}',
                      f'{chosen["intensity_reduction"]:.3f} lower'),
        ui.stat_block(ui.tr("cb_position"),
                      f'{chosen["certificates"]:,.0f}',
                      "certificates earned" if chosen["compliant"]
                      else "certificate shortfall",
                      bad=not chosen["compliant"]),
        ui.stat_block("Value of the change", engine.inr(chosen["value_of_change_inr"]),
                      f'at Rs {price:,}/tCO2e'),
    ], columns=5)

    if baseline["compliant"]:
        position = (f'At its current {baseline["baseline_scm_share"]:.0%} SCM share '
                    f'{receiving} already beats its target and earns '
                    f'{baseline["certificates"]:,.0f} certificates. Raising the share '
                    f'to 35% takes that to {chosen["certificates"]:,.0f}.')
    else:
        position = (f'At its current {baseline["baseline_scm_share"]:.0%} SCM share '
                    f'{receiving} misses its target by '
                    f'{abs(baseline["certificates"]):,.0f} tCO2e a year - a liability of '
                    f'{engine.inr(abs(baseline["exposure_at_penalty_inr"]))} at the '
                    f'doubled penalty rate. Raising the share to 35% moves it to '
                    f'{chosen["certificates"]:,.0f} certificates, '
                    f'{"in compliance" if chosen["compliant"] else "still short"}.')
    st.markdown(f'<div class="note{"" if chosen["compliant"] else " loss"}">{position}</div>',
                unsafe_allow_html=True)

    st.markdown(f'<div class="sect">{ui.tr("cb_options")}</div>',
                unsafe_allow_html=True)
    st.dataframe(
        pd.DataFrame([{
            "option": r["option"],
            "SCM share": r["scm_share"],
            "delivered Rs/t": r["cost_inr_t"],
            "meets spec": "yes" if r["meets_spec"] else "NO",
            "quality margin %": r["quality_margin"],
            "tCO2e/yr": r["co2_t_yr"],
            "CO2 avoided t/yr": r["co2_avoided_t_yr"],
            "certificates": r["certificates"],
            "CCTS position Rs/yr": r["position_inr"],
        } for r in rows]),
        hide_index=True, width="stretch",
        column_config={
            "option": st.column_config.TextColumn("Option", width="large"),
            "SCM share": st.column_config.NumberColumn("SCM share", format="%.0f%%",
                                                       width="small"),
            "delivered Rs/t": st.column_config.NumberColumn("Delivered Rs/t",
                                                            format="%.0f"),
            "meets spec": st.column_config.TextColumn("Meets IS 3812", width="small"),
            "quality margin %": st.column_config.NumberColumn(
                "Quality margin %", format="%.1f",
                help="Headroom on the binding property against IS 3812 Part 1. "
                     "Negative means the stream is outside the standard."),
            "tCO2e/yr": st.column_config.NumberColumn("tCO2e/yr", format="%.0f"),
            "CO2 avoided t/yr": st.column_config.NumberColumn("CO2 avoided t/yr",
                                                              format="%.0f"),
            "certificates": st.column_config.NumberColumn("Certificates",
                                                          format="%.0f"),
            "CCTS position Rs/yr": st.column_config.NumberColumn("CCTS position Rs/yr",
                                                                 format="%.0f"),
        },
    )
    st.markdown(
        f'<p class="caveat">The SCM share is raised to 35%, the ceiling IS 1489 '
        'allows for fly ash in Portland pozzolana cement. The cheapest stream is '
        'the one that does not meet IS 3812 - which is the whole point of reading '
        'the quality margin and the cost in the same table. '
        f'<strong>{carbon.SCHEME_NOTES}</strong></p>'
        f'<p class="caveat">Intensity model: clinker factor = 1 - SCM share - '
        f'{carbon.GYPSUM_SHARE:.0%} gypsum, at '
        f'{carbon.CLINKER_EMISSION_FACTOR} tCO2/t clinker (about 0.53 from '
        'limestone calcination, which no fuel switch removes, plus kiln fuel), '
        f'plus {carbon.CEMENT_OTHER_EMISSIONS} tCO2/t for grinding power. Those '
        'are published sector averages, not this plant\'s verified figures, and '
        f'the target shown is illustrative. {profile.get("note", "")}</p>',
        unsafe_allow_html=True,
    )

# ======================================================================
# 1. Find my matches
# ======================================================================

if section == "mine":
    st.markdown(f'<div class="sect">{ui.tr("mine_heading")}</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">Pick what you make or what you need, say roughly how much and '
        'where you are, and every facility in the registry is ranked as a partner - scored '
        'by the same five factors as everything else in this tool, so the numbers are '
        'comparable.</p>',
        unsafe_allow_html=True,
    )

    role = st.radio(ui.tr("mine_role"),
                    [ui.tr("role_supplier"), ui.tr("role_receiver")],
                    horizontal=True, key="role")
    is_supplier = role == ui.tr("role_supplier")

    c1, c2, c3 = st.columns(3)
    registry_sectors = sorted({str(s) for s in facilities["sector"].unique()})
    sector_options = sorted(set(registry_sectors) | set(kb.sectors()))

    with c1:
        if is_supplier:
            all_materials = kb.materials()
            material = st.selectbox(
                ui.tr("f_byproduct"), all_materials,
                index=all_materials.index("fly ash") if "fly ash" in all_materials else 0,
                key="my_material")
            takers = engine.sectors_for_material(material)
            sector = st.selectbox(
                ui.tr("f_sector"), sector_options,
                index=(sector_options.index("thermal power")
                       if "thermal power" in sector_options else 0),
                key="my_sector_sup",
                help="Used for the registry only - what you offer is decided by the "
                     "by-product, not by your sector.")
            st.markdown(
                f'<p class="caveat">Sectors that can take {material}: '
                f'{", ".join(takers) if takers else "none recorded"}.</p>',
                unsafe_allow_html=True)
        else:
            sector = st.selectbox(
                ui.tr("f_sector"), sector_options,
                index=sector_options.index("cement") if "cement" in sector_options else 0,
                key="my_sector_rec")
            takeable = engine.materials_for_sector(sector)
            if takeable:
                material = st.selectbox(
                    ui.tr("f_accept"), ["Anything I can use"] + takeable,
                    key="my_material_rec",
                    help="The engine tests every by-product your sector can accept. Pick "
                         "one to narrow the ranking to it.")
            else:
                material = "Anything I can use"
                st.warning(
                    f"The knowledge base records no by-product that a '{sector}' plant can "
                    "accept, so there is nothing to rank. Try another sector.", icon=None)

    with c2:
        location = st.selectbox(ui.tr("f_location"), list(INDUSTRIAL_LOCATIONS),
                                index=list(INDUSTRIAL_LOCATIONS).index("Nagpur, Maharashtra"),
                                key="my_location")
        my_state, my_lat, my_lon = INDUSTRIAL_LOCATIONS[location]
        precise = st.toggle(ui.tr("f_exact"), value=False, key="my_precise")
        if precise:
            lc1, lc2 = st.columns(2)
            my_lat = lc1.number_input("Latitude", 6.0, 37.6, float(my_lat), 0.01,
                                      format="%.4f")
            my_lon = lc2.number_input("Longitude", 67.0, 98.0, float(my_lon), 0.01,
                                      format="%.4f")

    with c3:
        quantity = st.number_input(
            ui.tr("f_qty_out") if is_supplier else ui.tr("f_qty_in"),
            min_value=100, max_value=10_000_000,
            value=250_000 if is_supplier else 1_200_000, step=10_000)
        season_label = st.selectbox(ui.tr("f_season"), list(engine.SEASON_PRESETS),
                                    key="my_season")
        authorised = st.toggle(
            ui.tr("f_authorised"), value=False, key="my_auth",
            help="Regulated streams score 0.75 on compliance with authorisation and 0.25 "
                 "without it.")

    go_ranking = st.button(ui.tr("btn_rank"), type="primary", key="run_mine")

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
                "No partner in this registry clears the gates for that description. That is "
                "a real answer, not a failure: try a larger tonnage, a more central "
                "location, a different by-product, or lower the minimum score in the "
                "sidebar. If the by-product is bulky and low-value, distance is almost "
                "certainly the binding constraint."
            )
        else:
            best = mine.iloc[0]
            k1, k2, k3, k4 = st.columns(4)
            k1.metric(ui.tr("mine_partners"), f"{len(mine):,}")
            k2.metric(ui.tr("mine_best"), f"{best['score']:.1f}")
            k3.metric(ui.tr("mine_best_value"), engine.inr(best["net_value"]))
            k4.metric(ui.tr("mine_best_co2"), engine.tonnes(best["co2_avoided_t"]))

            st.markdown(
                f'<div class="sect">{ui.tr("mine_ranked")} &mdash; {len(mine)}</div>'
                '<p class="sub">Ranked by the same engine score used everywhere else: '
                'quantity 0.30, proximity 0.28, processing 0.16, timing 0.14, compliance '
                '0.12. Sort any column by clicking its header.</p>',
                unsafe_allow_html=True,
            )

            listing = mine[["rank", "score", "partner", "material", "application",
                            "partner_sector", "partner_state", "road_km", "transport_mode",
                            "matched_tpa", "net_value"]].copy()
            listing["direction"] = ["sends to" if r == "supplier" else "receives from"
                                    for r in mine["role"]]
            listing["flags"] = flag_column(mine)
            st.dataframe(
                listing, hide_index=True, width="stretch", height=430,
                column_config={
                    "rank": st.column_config.NumberColumn("#", width="small"),
                    "score": st.column_config.ProgressColumn(
                        ui.tr("score"), min_value=0, max_value=100, format="%.1f"),
                    "partner": st.column_config.TextColumn("Partner facility",
                                                           width="medium"),
                    "direction": st.column_config.TextColumn("Direction", width="small"),
                    "material": st.column_config.TextColumn("By-product", width="small"),
                    "application": st.column_config.TextColumn("Application", width="medium"),
                    "partner_sector": st.column_config.TextColumn("Sector", width="small"),
                    "partner_state": st.column_config.TextColumn("State", width="small"),
                    "road_km": st.column_config.NumberColumn("km", format="%.0f",
                                                             width="small"),
                    "transport_mode": st.column_config.TextColumn("Mode", width="small"),
                    "matched_tpa": st.column_config.NumberColumn("t/yr", format="%.0f"),
                    "net_value": st.column_config.NumberColumn("Net Rs/yr", format="%.0f"),
                    "flags": st.column_config.TextColumn("Flags", width="small"),
                },
            )

            d1, d2 = st.columns([2, 1])
            labels = [f"{r.rank}. {r.material} - {r.partner}"
                      for r in mine.itertuples(index=False)]
            picked = d1.selectbox(ui.tr("mine_inspect"), labels, index=0, key="mine_pick")
            d2.download_button(
                ui.tr("mine_download"), data=mine.to_csv(index=False).encode("utf-8"),
                file_name="my_symbiosis_matches.csv", mime="text/csv", width="stretch")
            chosen = mine.iloc[labels.index(picked)]
            render_narrative(chosen)
            with st.expander(ui.tr("audit"), expanded=False):
                render_audit(chosen)
    else:
        st.markdown(
            f'<p class="caveat">Fill in the fields above and press '
            f'<strong>{ui.tr("btn_rank")}</strong>.</p>',
            unsafe_allow_html=True,
        )

# ======================================================================
# 2. Exchange network
# ======================================================================

if section == "network":
    if matches.empty:
        st.info("No exchanges clear the current threshold, so there is no network to draw.")
    else:
        metric_labels = {
            ui.tr("m_exchanges"): "exchanges",
            ui.tr("m_supplied"): "tonnes_supplied",
            ui.tr("m_received"): "tonnes_received",
            ui.tr("m_facilities"): "facilities",
        }
        f1, f2, f3, f4 = st.columns([1.5, 1.7, 1.7, 1.2])
        metric_label = f1.selectbox(ui.tr("map_colour_by"), list(metric_labels),
                                    key="map_metric")
        states = sorted(set(matches["supplier_state"]) | set(matches["receiver_state"]))
        pick_states = f2.multiselect(ui.tr("map_filter_states"), states, default=[],
                                     placeholder="All states")
        materials = sorted(matches["material"].unique())
        pick_materials = f3.multiselect(ui.tr("map_filter_materials"), materials,
                                        default=[], placeholder="All materials")
        show_n = f4.slider(ui.tr("map_flows"), 5, max(6, min(200, len(matches))),
                           min(60, len(matches)), 5)

        view = matches
        if pick_states:
            view = view[view["supplier_state"].isin(pick_states)
                        | view["receiver_state"].isin(pick_states)]
        if pick_materials:
            view = view[view["material"].isin(pick_materials)]
        view = view.head(show_n)

        activity = engine.state_activity(view, facilities)
        metric_field = metric_labels[metric_label]
        by_state = {r.state: r for r in activity.itertuples(index=False)}
        vmax = float(activity[metric_field].max()) if len(activity) else 0.0
        vmax = vmax if vmax > 0 else 1.0

        fig = go.Figure()

        # The states are drawn as ordinary filled shapes on a plain x/y plot rather
        # than on a Plotly geo subplot. A geo subplot always pulls its own topojson
        # from Plotly's CDN - even with the basemap switched off - and this app is
        # meant to run with no internet. Longitude is x, latitude is y, the aspect
        # ratio is anchored below, and the boundaries come from the GeoJSON bundled
        # in data/, which follows the Survey of India convention.
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
                    fillcolor=ramp_colour(value / vmax),
                    line=dict(color="#8a93a3", width=0.7),
                    hoveron="fills", hoverinfo="text", text=detail,
                    name="", showlegend=False,
                ))

            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode="markers", showlegend=False, hoverinfo="skip",
                marker=dict(
                    colorscale=BLUE_SEQUENTIAL, cmin=0, cmax=vmax, color=[0],
                    showscale=True, opacity=0,
                    colorbar=dict(
                        title=dict(text=metric_label, font=dict(size=10, color="#5a6472"),
                                   side="top"),
                        orientation="h", thickness=9, len=0.46, x=0.5, xanchor="center",
                        y=-0.02, yanchor="bottom", outlinewidth=0, xpad=0, ypad=0,
                        tickfont=dict(size=9, color="#5a6472"),
                    ),
                ),
            ))

        # Viable and loss-making flows differ in colour AND dash pattern, and both
        # carry a legend entry, so the distinction never rests on colour alone.
        seen_legend = set()
        for row in view.itertuples(index=False):
            loss = row.net_value < 0
            strength = float(row.score) / 100.0
            key = "loss" if loss else "viable"
            fig.add_trace(go.Scatter(
                x=[row.supplier_lon, row.receiver_lon],
                y=[row.supplier_lat, row.receiver_lat],
                mode="lines",
                line=dict(width=1.0 + 2.6 * strength,
                          color=LOSS_COLOUR if loss else SUPPLIER_COLOUR,
                          dash="dot" if loss else "solid"),
                opacity=0.45 + 0.45 * strength,
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
            x=sup["supplier_lon"], y=sup["supplier_lat"], mode="markers",
            name="Supplier",
            marker=dict(size=9, color=SUPPLIER_COLOUR,
                        line=dict(width=1.0, color="#ffffff")),
            hoverinfo="text",
            text=[f"<b>{n}</b><br>{s}<br>offers {m}"
                  for n, s, m in zip(sup["supplier"], sup["supplier_sector"],
                                     sup["material"])],
        ))
        fig.add_trace(go.Scatter(
            x=rec["receiver_lon"], y=rec["receiver_lat"], mode="markers",
            name="Receiver",
            marker=dict(size=9, color=RECEIVER_COLOUR, symbol="square",
                        line=dict(width=1.2, color="#5a4200")),
            hoverinfo="text",
            text=[f"<b>{n}</b><br>{s}" for n, s in zip(rec["receiver"],
                                                       rec["receiver_sector"])],
        ))

        fig.update_xaxes(
            range=[engine.INDIA_BOUNDS["lon_min"], engine.INDIA_BOUNDS["lon_max"]],
            visible=False, constrain="domain")
        fig.update_yaxes(
            range=[engine.INDIA_BOUNDS["lat_min"], engine.INDIA_BOUNDS["lat_max"]],
            visible=False,
            # A degree of latitude is ~111 km; a degree of longitude ~103 km at 22 N.
            scaleanchor="x", scaleratio=1.08, constrain="domain")
        fig.update_layout(
            height=640, margin=dict(l=0, r=0, t=6, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff",
            font=CHART_FONT,
            legend=dict(orientation="v", yanchor="top", y=0.99, x=0.005,
                        bgcolor="rgba(255,255,255,0.92)", bordercolor="#d5d9e0",
                        borderwidth=1, font=dict(size=11)),
            hoverlabel=HOVER_STYLE, dragmode="pan",
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
                .head(10)
            )
            st.markdown(f'<div class="sect">{ui.tr("map_top_states")} '
                        f'{metric_label.lower()}</div>', unsafe_allow_html=True)
            if ranked_states.empty:
                st.markdown('<p class="caveat">No state has any activity under these '
                            'filters.</p>', unsafe_allow_html=True)
            else:
                show = ranked_states[["state", metric_field]].copy()
                st.dataframe(
                    show, hide_index=True, width="stretch",
                    column_config={
                        "state": st.column_config.TextColumn("State", width="medium"),
                        metric_field: st.column_config.ProgressColumn(
                            metric_label, min_value=0,
                            max_value=float(ranked_states[metric_field].max()),
                            format="%.0f"),
                    },
                )
            st.markdown(
                f'<p class="caveat"><strong>{len(view)}</strong> flow(s) drawn. Thickness '
                'and opacity scale with score; dotted red lines lose money. Hover any state '
                'for its totals, drag to pan, scroll to zoom.</p>'
                '<p class="caveat">Lines are straight-line links, not routed roads - '
                f'scoring uses straight-line distance inflated '
                f'{engine.ROAD_CIRCUITY_FACTOR:.2f}x. State boundaries follow the Survey of '
                'India convention and are bundled with the app, so nothing is fetched from '
                'the internet to draw this map.</p>',
                unsafe_allow_html=True,
            )

# ======================================================================
# 3. Ranked matches
# ======================================================================

if section == "matches":
    if matches.empty:
        st.info("No exchanges clear the current threshold.")
    else:
        left, right = st.columns([1.15, 1])

        with left:
            st.markdown(f'<div class="sect">{ui.tr("tab_matches")}</div>',
                        unsafe_allow_html=True)
            table = matches[["rank", "score", "supplier", "material", "receiver",
                             "matched_tpa", "road_km", "transport_mode",
                             "net_value"]].copy()
            table["flags"] = flag_column(matches)
            st.dataframe(
                table, hide_index=True, height=540, width="stretch",
                column_config={
                    "rank": st.column_config.NumberColumn("#", width="small"),
                    "score": st.column_config.ProgressColumn(
                        ui.tr("score"), min_value=0, max_value=100, format="%.1f"),
                    "supplier": st.column_config.TextColumn("Supplier"),
                    "material": st.column_config.TextColumn("By-product"),
                    "receiver": st.column_config.TextColumn("Receiver"),
                    "matched_tpa": st.column_config.NumberColumn("t/yr", format="%.0f"),
                    "road_km": st.column_config.NumberColumn("km", format="%.0f",
                                                             width="small"),
                    "transport_mode": st.column_config.TextColumn("Mode", width="small"),
                    "net_value": st.column_config.NumberColumn("Net Rs/yr", format="%.0f"),
                    "flags": st.column_config.TextColumn("Flags", width="small"),
                },
            )
            st.download_button(ui.tr("download_all"),
                               data=matches.to_csv(index=False).encode("utf-8"),
                               file_name="symbiosis_matches.csv", mime="text/csv",
                               width="stretch")

        with right:
            labels = [f"{r.rank}. {r.material} - {r.supplier} to {r.receiver}"
                      for r in matches.itertuples(index=False)]
            chosen = st.selectbox(ui.tr("exchange"), labels, index=0, key="match_pick")
            row = matches.iloc[labels.index(chosen)]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric(ui.tr("score"), f"{row['score']:.1f}")
            m2.metric(ui.tr("tonnes_yr"), engine.tonnes(row["matched_tpa"]))
            m3.metric(ui.tr("net_value_yr"), engine.inr(row["net_value"]))
            m4.metric(ui.tr("co2_yr"), engine.tonnes(row["co2_avoided_t"]))

            render_narrative(row)

        st.markdown("---")
        with st.expander(ui.tr("audit"), expanded=False):
            render_audit(row)

# ======================================================================
# 4. Chains and impact
# ======================================================================

if section == "chains":
    st.markdown(f'<div class="sect">{ui.tr("chains_heading")}</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">Pairwise scoring says which exchanges are practical. It does not '
        'say how to run them all together, and it cannot see an arrangement that only '
        'makes sense through a third plant. These two passes do.</p>',
        unsafe_allow_html=True,
    )

    basis = st.radio(
        ui.tr("basis"), [ui.tr("basis_opt"), ui.tr("basis_greedy")],
        horizontal=True, key="impact_basis",
        help="Greedy walks the matches best score first and gives each whatever is left. "
             "The optimiser solves the whole allocation at once to maximise net value, "
             "subject to the same supply, intake and ceiling limits.",
    )
    use_optimised = basis == ui.tr("basis_opt")
    column = "optimised_tpa" if use_optimised else "allocated_tpa"
    frame = optimised if use_optimised else matches
    stats = engine.circularity(frame, facilities, tonnes_column=column)

    ui.stat_row([
        ui.stat_block(ui.tr("kpi_circularity"), f"{stats['circularity_pct']:.1f}%",
                      f"{ui.tr('of_produced')} "
                      f"{engine.tonnes(stats['total_byproduct_t'])}"),
        ui.stat_block(ui.tr("imp_landfill"),
                      engine.tonnes(stats["landfill_diverted_t"]), ui.tr("per_year")),
        ui.stat_block(ui.tr("imp_virgin"), engine.tonnes(stats["virgin_avoided_t"]),
                      "not quarried, mined or grown"),
        ui.stat_block(ui.tr("kpi_co2"), engine.tonnes(stats["co2_avoided_t"]),
                      ui.tr("per_year")),
        ui.stat_block(ui.tr("imp_net"), engine.inr(stats["net_value"]),
                      ui.tr("per_year")),
    ], columns=5)

    st.markdown(
        '<p class="caveat">Circularity is the share of by-product tonnage in this registry '
        'that actually finds a home. The denominator is every tonne offered, including the '
        'streams with no viable receiver, so it is deliberately hard to move. Virgin '
        'material avoided applies each substitution ratio to the tonnage placed - it is the '
        'quarrying, mining and growing that does not have to happen. Water footprint is not '
        'modelled: there is no defensible per-tonne figure for most of these streams.</p>',
        unsafe_allow_html=True,
    )

    st.markdown(f'<div class="sect">{ui.tr("opt_vs_greedy")}</div>',
                unsafe_allow_html=True)
    greedy_value = float(matches["allocated_net_value"].sum()) if len(matches) else 0.0
    o1, o2, o3 = st.columns(3)
    o1.metric("Greedy allocation", engine.inr(greedy_value))
    o2.metric("Optimised allocation", engine.inr(opt_report["objective"]),
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
    st.markdown(f'<div class="sect">{ui.tr("chains_found")} &mdash; {len(chains)}</div>',
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
            hide_index=True, width="stretch", height=320,
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

        chain_labels = [f"{i + 1}. {r.path}"
                        for i, r in enumerate(chains.itertuples(index=False))]
        picked_chain = st.selectbox(ui.tr("chain_walk"), chain_labels, index=0,
                                    key="chain_pick")
        chain = chains.iloc[chain_labels.index(picked_chain)]

        st.dataframe(
            pd.DataFrame({
                "step": range(1, chain["hops"] + 1),
                "exchange": str(chain["steps"]).split(" | "),
            }),
            hide_index=True, width="stretch",
            column_config={
                "step": st.column_config.NumberColumn("Step", width="small"),
                "exchange": st.column_config.TextColumn("Exchange", width="large"),
            },
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Weakest link", f"{chain['weakest_score']:.1f}")
        c2.metric("Chain net value", engine.inr(chain["total_net_value"]))
        c3.metric("Chain CO2 avoided", engine.tonnes(chain["total_co2_t"]))
        st.markdown(
            '<p class="caveat">Chain totals add the individual exchanges, which overstates '
            'them if the hops compete for the same tonnage - read the optimised allocation '
            'above for what the network can actually run at once.</p>',
            unsafe_allow_html=True,
        )

# ======================================================================
# 5. Gap analysis
# ======================================================================

if section == "gaps":
    st.markdown(f'<div class="sect">{ui.tr("gaps_heading")}</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">These are not errors. Each is a stream someone is paying to dispose '
        'of, with no receiver in this registry that clears the gates - which is exactly '
        'where a new processing or aggregation facility would pay for itself.</p>',
        unsafe_allow_html=True,
    )

    if gaps.empty:
        st.success("Every by-product in this registry found at least one viable receiver.")
    else:
        ui.stat_row([
            ui.stat_block(ui.tr("gaps_unplaced"), f"{len(gaps):,}"),
            ui.stat_block(ui.tr("gaps_tonnes"), engine.tonnes(gaps["output_tpa"].sum()),
                          ui.tr("per_year")),
            ui.stat_block(ui.tr("gaps_disposal"), engine.inr(gaps["disposal_cost"].sum()),
                          ui.tr("per_year"), bad=True),
        ], columns=3)

        top = gaps.head(10).iloc[::-1]
        bar = go.Figure(go.Bar(
            x=top["output_tpa"],
            y=[f"{m} - {s}" for m, s in zip(top["material"], top["supplier"])],
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
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff", font=CHART_FONT,
            xaxis=dict(title="tonnes per year with nowhere to go",
                       gridcolor="#e4e7ec", zeroline=False),
            yaxis=dict(gridcolor="rgba(0,0,0,0)"),
            hoverlabel=HOVER_STYLE, showlegend=False,
        )
        st.plotly_chart(bar, width="stretch", config={"displaylogo": False})

        st.dataframe(
            gaps[["supplier", "sector", "state", "material", "output_tpa",
                  "disposal_cost", "recorded_uses", "candidate_sectors"]],
            hide_index=True, width="stretch", height=300,
            column_config={
                "supplier": st.column_config.TextColumn("Facility"),
                "sector": st.column_config.TextColumn("Sector", width="small"),
                "state": st.column_config.TextColumn("State", width="small"),
                "material": st.column_config.TextColumn("By-product"),
                "output_tpa": st.column_config.NumberColumn("t/yr", format="%.0f"),
                "disposal_cost": st.column_config.NumberColumn("Disposal Rs/yr",
                                                               format="%.0f"),
                "recorded_uses": st.column_config.NumberColumn("Known uses", width="small"),
                "candidate_sectors": st.column_config.TextColumn(
                    "Sectors that could take it", width="large"),
            },
        )

        gap_labels = [f"{r.material} - {r.supplier} ({r.output_tpa:,.0f} t/yr)"
                      for r in gaps.itertuples(index=False)]
        picked = st.selectbox(ui.tr("gaps_examine"), gap_labels, index=0, key="gap_pick")
        gap = gaps.iloc[gap_labels.index(picked)]
        st.markdown(f'<div class="note loss">{explain.explain_gap(gap)}</div>',
                    unsafe_allow_html=True)

        st.markdown(f'<div class="sect">{ui.tr("gaps_resembles")}</div>',
                    unsafe_allow_html=True)
        st.markdown(
            '<p class="sub">The substitution table can only match a stream it has heard '
            'of. This compares the by-product\'s measured properties against every material '
            'the knowledge base does know and reports the closest, with the properties that '
            'drive the resemblance and the one that does not. It is a lead to test, never a '
            'scored match - nothing here touches the score or the valuation.</p>',
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
                    "shared_properties": st.column_config.TextColumn("What lines up",
                                                                     width="medium"),
                    "biggest_difference": st.column_config.TextColumn("What does not",
                                                                      width="small"),
                },
            )
            best = similar.iloc[0]
            st.markdown(
                f'<p class="caveat">Closest analogue: <strong>{best["material"]}</strong> at '
                f'{best["similarity"]:.0%} resemblance, agreeing on '
                f'{best["shared_properties"]}, differing most on '
                f'{best["biggest_difference"]}. It is accepted by '
                f'{best["accepting_sectors"]}. The next step is a laboratory analysis of the '
                'real material against that sector\'s specification - resemblance on paper '
                'is a reason to test, not a reason to sign.</p>',
                unsafe_allow_html=True,
            )

        uses = kb.uses_for(gap["material"])
        st.markdown(f'<div class="sect">{ui.tr("gaps_uses")}</div>', unsafe_allow_html=True)
        if not uses:
            st.info("The knowledge base records no use for this material. Adding one is a "
                    "research task, not a code change - see kb.py.")
        else:
            st.dataframe(
                pd.DataFrame([{
                    "application": u["application"], "replaces": u["replaces"],
                    "accepting sectors": ", ".join(u["accepting_sectors"]),
                    "max share": u["max_share"], "max km": u["max_km"],
                    "processing": u["processing"], "hazard": u["hazard"],
                    "note": u["note"],
                } for u in uses]),
                hide_index=True, width="stretch",
                column_config={
                    "application": st.column_config.TextColumn("Application",
                                                               width="medium"),
                    "max share": st.column_config.NumberColumn("Max share", format="%.2f",
                                                               width="small"),
                    "max km": st.column_config.NumberColumn("Max km", format="%.0f",
                                                            width="small"),
                    "note": st.column_config.TextColumn("Practical catch", width="large"),
                },
            )

if section == "method":
    st.markdown(f'<div class="sect">{ui.tr("method_scoring")}</div>',
                unsafe_allow_html=True)
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
