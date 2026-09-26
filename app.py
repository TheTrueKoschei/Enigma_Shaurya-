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
import reach
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


def render_verdict(row):
    """One sentence and the operational chips - fits a narrow column."""
    loss = float(row["net_value"]) < 0
    st.markdown(
        f'<div class="note{" loss" if loss else ""}">'
        f'<strong>{row["supplier"]} &rarr; {row["receiver"]}</strong>: '
        f'{engine.tonnes(row["matched_tpa"])} of {row["material"]} a year for '
        f'{row["application"]}, scoring {float(row["score"]):.0f} and worth '
        f'{engine.inr(row["net_value"])} a year.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(match_chips(row), unsafe_allow_html=True)


def render_detail_charts(row):
    """Score composition and the money, given the full page width.

    Kept out of render_verdict because these two need room: nested inside a
    half-width column the legend collides with the axis.
    """
    left, right = st.columns([1, 1], gap="medium")
    with left:
        st.plotly_chart(score_bar(row), width="stretch",
                        config={"displaylogo": False})
    with right:
        st.plotly_chart(money_waterfall(row), width="stretch",
                        config={"displaylogo": False})

    story = explain.explain(row)
    loss = float(row["net_value"]) < 0
    with st.expander("Full assessment", expanded=False):
        st.markdown(f'<div class="note{" loss" if loss else ""}">'
                    f'{story["headline"]}</div>', unsafe_allow_html=True)
        for title in explain.SECTION_ORDER:
            st.markdown(f'<p class="sec-title">{title}</p>',
                        unsafe_allow_html=True)
            st.markdown(f'<p class="sec-body">{story["sections"][title]}</p>',
                        unsafe_allow_html=True)


def render_narrative(row):
    """Verdict then charts, for callers that have the full width already."""
    render_verdict(row)
    render_detail_charts(row)


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


# Five factor identities for the score breakdown. Validated adjacent-pair on the
# light surface; every segment is also labelled and legended, which is what the
# two low-contrast steps require. Deliberately avoids the status green and red,
# which are reserved for pass and fail everywhere else.
FACTOR_COLOURS = {
    "quantity": "#2a78d6", "proximity": "#eb6834", "timing": "#4a3aa7",
    "processing": "#eda100", "compliance": "#e87ba4",
}
FACTOR_LABELS = {
    "quantity": "Quantity", "proximity": "Proximity", "timing": "Timing",
    "processing": "Processing", "compliance": "Compliance",
}


def score_bar(row) -> go.Figure:
    """One stacked bar: each factor sized by weight x its value, out of 100."""
    fig = go.Figure()
    for key in ("quantity", "proximity", "timing", "processing", "compliance"):
        points = float(row[f"c_{key}"])
        raw = float(row[f"f_{key}"])
        weight = engine.WEIGHTS[key]
        fig.add_trace(go.Bar(
            x=[points], y=["score"], orientation="h",
            name=FACTOR_LABELS[key],
            marker=dict(color=FACTOR_COLOURS[key],
                        line=dict(width=1, color="#ffffff")),
            text=[f"{points:.0f}" if points >= 6 else ""],
            textposition="inside", insidetextanchor="middle",
            textfont=dict(size=11, color="#ffffff"),
            hovertemplate=(f"<b>{FACTOR_LABELS[key]}</b><br>"
                           f"raw {raw:.2f} x weight {weight:.2f}"
                           f" = {points:.2f} points<extra></extra>"),
        ))
    # The points not earned, so the bar always reads out of 100.
    lost = 100.0 - float(row["score"])
    if lost > 0.01:
        fig.add_trace(go.Bar(
            x=[lost], y=["score"], orientation="h", name="not earned",
            marker=dict(color="#e8ebef", line=dict(width=1, color="#ffffff")),
            hovertemplate=f"Not earned: {lost:.1f} points<extra></extra>",
        ))
    fig.update_layout(
        barmode="stack", height=190, margin=dict(l=0, r=0, t=6, b=70),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=CHART_FONT,
        xaxis=dict(range=[0, 100], showgrid=False, zeroline=False,
                   title="score out of 100"),
        yaxis=dict(showticklabels=False, showgrid=False),
        legend=dict(orientation="h", yanchor="top", y=-0.75, x=0,
                    font=dict(size=10)),
        hoverlabel=HOVER_STYLE,
    )
    return fig


def money_waterfall(row) -> go.Figure:
    """Material value, plus disposal avoided, less freight and processing."""
    values = [float(row["material_value"]), float(row["disposal_saved"]),
              -float(row["transport_cost"]), -float(row["processing_cost"])]
    net = float(row["net_value"])
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["relative", "relative", "relative", "relative", "total"],
        x=["Material<br>displaced", "Disposal<br>avoided", "Transport",
           "Processing", "Net"],
        y=values + [net],
        text=[engine.inr(v) for v in values] + [engine.inr(net)],
        textposition="outside", textfont=dict(size=10),
        connector=dict(line=dict(color="#b9c0cc", width=1)),
        increasing=dict(marker=dict(color=ui.STATUS_GOOD)),
        decreasing=dict(marker=dict(color=ui.STATUS_BAD)),
        totals=dict(marker=dict(color=ui.ACCENT if net >= 0 else ui.STATUS_BAD)),
        hoverinfo="x+y",
    ))
    # A loss has to be visible as a bar below the axis, not just a red number.
    low = min(0.0, net, min(values)) * 1.25
    high = max(values + [net]) * 1.3
    fig.update_layout(
        height=330, margin=dict(l=0, r=0, t=22, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff", font=CHART_FONT,
        yaxis=dict(title="Rs per year", gridcolor="#e4e7ec", zeroline=True,
                   zerolinecolor="#1a1f2b", zerolinewidth=1,
                   range=[low, high]),
        xaxis=dict(showgrid=False, tickangle=0, tickfont=dict(size=10)),
        showlegend=False, hoverlabel=HOVER_STYLE,
    )
    return fig


def stream_short(name: str) -> str:
    """"Fly ash (Talcher TPS)" -> "Talcher TPS".

    Two streams of the same material differ only by the plant, so the plant is
    what a chip has to show - splitting on the material name makes both read
    identically.
    """
    if "(" in name and name.rstrip().endswith(")"):
        return name[name.index("(") + 1:name.rindex(")")]
    return name


def match_chips(row) -> str:
    """The operational facts of an exchange, as tags rather than a paragraph."""
    processing = str(row["processing"])
    chips = [
        ui.chip(f'{row["road_km"]:,.0f} km by {row["transport_mode"]}', "accent"),
        ui.chip(f'{engine.tonnes(row["matched_tpa"])}/yr'),
        ui.chip(f'{row["supplier_share"] * 100:.0f}% of supplier output'),
        ui.chip(f'{row["max_share"] * 100:.0f}% max of receiver input'),
        ui.chip(f'{processing} processing',
                "good" if processing == "none" else
                ("warn" if processing in ("simple", "moderate") else "bad")),
        ui.chip(f'{row["supplier_availability"]}',
                "good" if float(row["f_timing"]) >= 0.999 else "warn"),
    ]
    if str(row["hazard"]) == "regulated":
        chips.append(ui.chip(
            "regulated" + (" - receiver authorised" if row["receiver_authorised"]
                           else " - receiver NOT authorised"),
            "warn" if row["receiver_authorised"] else "bad"))
    if bool(row["beyond_max_km"]):
        chips.append(ui.chip(f'past the {row["max_km"]:,.0f} km limit', "bad"))
    if float(row["net_value"]) < 0:
        chips.append(ui.chip("loses money", "bad"))
    return ui.chip_row(chips)



def flow_sankey(view: pd.DataFrame, max_flows: int = 18) -> go.Figure:
    """By-product streams, through applications, to the virgin material displaced.

    The classic industrial-ecology picture: it makes the whole system legible in
    one image in a way a ranked table never does. Link thickness is tonnes a
    year, taken from the allocation so the same tonne is not drawn twice.
    """
    if view is None or len(view) == 0:
        return None
    top = view.nlargest(min(max_flows, len(view)), "allocated_tpa")
    top = top[top["allocated_tpa"] > 0]
    if top.empty:
        top = view.nlargest(min(max_flows, len(view)), "matched_tpa")
        column = "matched_tpa"
    else:
        column = "allocated_tpa"

    materials_in = sorted(top["material"].unique())
    applications = sorted(top["application"].unique())
    replaced = sorted(top["replaces"].unique())
    labels = materials_in + applications + replaced
    index = {name: i for i, name in enumerate(labels)}
    offset_app = len(materials_in)
    offset_rep = offset_app + len(applications)

    sources, targets, values, hovers = [], [], [], []
    for row in top.itertuples(index=False):
        tonnes = float(getattr(row, column))
        sources.append(index[row.material])
        targets.append(offset_app + applications.index(row.application))
        values.append(tonnes)
        hovers.append(f"{row.material} to {row.application}<br>"
                      f"{engine.tonnes(tonnes)}/yr")
        sources.append(offset_app + applications.index(row.application))
        targets.append(offset_rep + replaced.index(row.replaces))
        values.append(tonnes)
        hovers.append(f"{row.application} displaces {row.replaces}<br>"
                      f"{engine.tonnes(tonnes)}/yr")

    node_colours = ([ui.ACCENT] * len(materials_in)
                    + ["#5f93cb"] * len(applications)
                    + [ui.STATUS_GOOD] * len(replaced))
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=labels, pad=13, thickness=14,
                  color=node_colours,
                  line=dict(color="#ffffff", width=1),
                  hovertemplate="%{label}<br>%{value:,.0f} t/yr<extra></extra>"),
        link=dict(source=sources, target=targets, value=values,
                  color="rgba(31,95,169,0.22)",
                  customdata=hovers,
                  hovertemplate="%{customdata}<extra></extra>"),
    ))
    fig.update_layout(
        # Capped: past this the diagram scrolls off the screen and stops being
        # the one-image summary it exists to be.
        height=min(560, max(380, 24 * len(labels))),
        margin=dict(l=4, r=4, t=26, b=4),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#1a1f2b", size=11, family="Noto Sans, Arial, sans-serif"),
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

    st.markdown("---")
    ui.build_stamp()

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

# ----------------------------------------------------------------------
# Coverage band. Two numbers, never conflated: what is loaded, and how big the
# problem is. A headline claiming a million companies over a 255-row registry
# is the fastest way to lose an assessor, so the source sits next to the figure.
# ----------------------------------------------------------------------
coverage_stats = reach.summary(facilities, kb, specs, materials)
st.markdown(ui.chip_row([
    ui.chip(f'<strong>{coverage_stats["loaded"]:,}</strong> facilities loaded', "accent"),
    ui.chip(f'{coverage_stats["supplying"]} offering a by-product'),
    ui.chip(f'{coverage_stats["sectors"]} sectors &middot; {coverage_stats["states"]} states'),
    ui.chip(f'{coverage_stats["substitutions"]} substitutions &middot; '
            f'{coverage_stats["specifications"]} specifications &middot; '
            f'{coverage_stats["profiled_materials"]} property profiles'),
    ui.chip(f'addressable: <strong>{coverage_stats["addressable_pretty"]}</strong> '
            f'{coverage_stats["addressable_label"].lower()}', "good"),
    ui.chip(f'source: {coverage_stats["addressable_source"]} &mdash; verify before quoting',
            "warn"),
]), unsafe_allow_html=True)

unmatched_tonnes = float(gaps["output_tpa"].sum()) if len(gaps) else 0.0
placed_share = (100.0 * summary["tonnes_diverted"]
                / max(1.0, impact["total_byproduct_t"]))
viable_share = (100.0 * (summary["exchanges"] - summary["loss_making"])
                / max(1, summary["exchanges"]))
ui.stat_row([
    ui.stat_block(ui.tr("kpi_exchanges"), f"{summary['exchanges']:,}",
                  meter=viable_share,
                  meter_label=f"{summary['loss_making']} {ui.tr('at_a_loss')}",
                  meter_tone="bad" if summary["loss_making"] else "good"),
    ui.stat_block(ui.tr("kpi_tonnes"), engine.tonnes(summary["tonnes_diverted"]),
                  meter=placed_share,
                  meter_label=f"of {engine.tonnes(impact['total_byproduct_t'])} produced"),
    ui.stat_block(ui.tr("kpi_co2"), engine.tonnes(summary["co2_avoided_t"]),
                  sub=ui.tr("per_year")),
    ui.stat_block(ui.tr("kpi_value"), engine.inr(summary["value_unlocked"]),
                  sub=ui.tr("per_year")),
    ui.stat_block(ui.tr("kpi_unmatched"), engine.tonnes(unmatched_tonnes),
                  meter=100.0 - placed_share,
                  meter_label=f"{len(gaps)} {ui.tr('streams_unplaced')}",
                  meter_tone="bad"),
    ui.stat_block(ui.tr("kpi_circularity"), f"{impact['circularity_pct']:.1f}%",
                  meter=impact["circularity_pct"],
                  meter_label=ui.tr("of_produced")),
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
    props_a = materials.measured_properties(blend_a)
    props_b = materials.measured_properties(blend_b)

    if not props_a or not props_b or blend_a == blend_b:
        st.markdown(ui.chip_row([ui.chip(result["reason"] or
                                         "Pick two different streams", "bad")]),
                    unsafe_allow_html=True)
    else:
        # The slider is the whole screen: drag it and the bars move across the
        # limit line. The engine's recommendation is the starting position.
        default_f = int(round((result["f_recommended"]
                               if result["feasible"] else 0.5) * 100))
        mix = st.slider(
            f"Mass fraction of {blend_a}", 0, 100, default_f, 1,
            format="%d%%", key="blend_fraction",
            help="Drag to change the mix. Every bar below is redrawn against its "
                 "limit as you move it.",
        )
        f = mix / 100.0
        blended = blending.blend_properties(props_a, props_b, f)
        live = conformance.grade_properties(blended, target,
                                            material_label="blend")

        if result["feasible"]:
            window = (f'feasible {result["f_min"]:.0%} to {result["f_max"]:.0%}')
            window_tone = "accent"
        else:
            blocked = result["blocking"][0] if result["blocking"] else None
            window = ("no feasible blend"
                      + (f' - {materials.PROPERTY_LABELS.get(blocked["property"], blocked["property"])} '
                         "cannot be met" if blocked else ""))
            window_tone = "bad"

        verdict = (f'{ui.GLYPH_PASS} PASSES at {f:.0%} {stream_short(blend_a)}'
                   if live["passes"] else
                   f'{ui.GLYPH_FAIL} FAILS at {f:.0%} - '
                   f'{len(live["failures"])} limit(s) outside')
        st.markdown(ui.chip_row([
            ui.chip(verdict, "good" if live["passes"] else "bad"),
            ui.chip(f'grade {live["grade"]}', "good" if live["passes"] else "bad"),
            ui.chip(window, window_tone),
            ui.chip(f'{engine.inr(live["value_inr_t"])}/t if it qualifies', "accent"),
            ui.chip(f'{live["standard"]}'),
        ]), unsafe_allow_html=True)

        fig = bullet_chart(live)
        if fig is not None:
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})

        alone_a = conformance.grade(blend_a, target)
        alone_b = conformance.grade(blend_b, target)
        st.markdown(ui.chip_row([
            ui.chip(f'{stream_short(blend_a)} alone: '
                    f'{ui.GLYPH_PASS if alone_a["passes"] else ui.GLYPH_FAIL} '
                    f'{alone_a["grade"]}',
                    "good" if alone_a["passes"] else "bad"),
            ui.chip(f'{stream_short(blend_b)} alone: '
                    f'{ui.GLYPH_PASS if alone_b["passes"] else ui.GLYPH_FAIL} '
                    f'{alone_b["grade"]}',
                    "good" if alone_b["passes"] else "bad"),
            ui.chip(f'blend at {f:.0%}: '
                    f'{ui.GLYPH_PASS if live["passes"] else ui.GLYPH_FAIL} '
                    f'{live["grade"]}',
                    "good" if live["passes"] else "bad"),
        ]), unsafe_allow_html=True)

        with st.expander("Per-limit feasible range, and what each stream brings",
                         expanded=False):
            rows = []
            for interval, check in zip(result["intervals"], live["results"]):
                rows.append({
                    "property": " + ".join(
                        materials.PROPERTY_LABELS.get(part.strip(), part.strip())
                        for part in interval["property"].split("+")),
                    "required": f'{interval["operator"]} {interval["threshold"]:g}',
                    blend_a[:22]: interval["value_a"],
                    blend_b[:22]: interval["value_b"],
                    "blend now": check["actual"],
                    "allows f from": (interval["lo"] if interval["feasible"] else None),
                    "to": (interval["hi"] if interval["feasible"] else None),
                    "verdict": "PASS" if check["passes"] else "FAIL",
                })
            st.dataframe(
                pd.DataFrame(rows), hide_index=True, width="stretch",
                column_config={
                    "property": st.column_config.TextColumn("Property",
                                                            width="medium"),
                    "required": st.column_config.TextColumn("Required",
                                                            width="small"),
                    blend_a[:22]: st.column_config.NumberColumn(format="%.4g"),
                    blend_b[:22]: st.column_config.NumberColumn(format="%.4g"),
                    "blend now": st.column_config.NumberColumn(format="%.4g"),
                    "allows f from": st.column_config.NumberColumn(format="%.0f%%",
                                                                   width="small"),
                    "to": st.column_config.NumberColumn(format="%.0f%%",
                                                        width="small"),
                    "verdict": st.column_config.TextColumn("Verdict", width="small"),
                },
            )
            st.markdown(
                '<p class="caveat">Linear mixing is sound for composition and '
                'reasonable for fineness and loss on ignition. It does not predict '
                'lime reactivity, soundness or strength activity index, which the '
                'standards also require. A feasible blend is a candidate for a '
                'trial mix, not a certificate.</p>',
                unsafe_allow_html=True,
            )


# ======================================================================
# 0c. Carbon and CCTS
# ======================================================================

if section == "carbon":
    st.markdown(f'<div class="sect">{ui.tr("cb_heading")}</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">CCTS targets are intensity, not tonnage - so raising the '
        'supplementary cementitious share moves the number the plant is legally '
        'measured on.</p>',
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
    with st.expander("Model, constants and what is assumed", expanded=False):
        st.markdown(ui.chip_row([
            ui.chip("SCM raised to 35%, the IS 1489 ceiling", "accent"),
            ui.chip(f'clinker {carbon.CLINKER_EMISSION_FACTOR} tCO2/t', "accent"),
            ui.chip(f'grinding {carbon.CEMENT_OTHER_EMISSIONS} tCO2/t', "accent"),
            ui.chip(f'gypsum {carbon.GYPSUM_SHARE:.0%}', "accent"),
            ui.chip("certificate price is an assumption", "warn"),
            ui.chip("targets illustrative, not notified", "warn"),
            ui.chip("sector averages, not verified plant data", "warn"),
        ]), unsafe_allow_html=True)
        st.markdown(
            f'<p class="caveat">The cheapest stream is the one that does not meet '
            'IS 3812, which is why cost and quality margin belong in the same '
            f'table. {carbon.SCHEME_NOTES} {profile.get("note", "")}</p>',
            unsafe_allow_html=True,
        )

# ======================================================================
# 1. Find my matches
# ======================================================================

if section == "mine":
    st.markdown(f'<div class="sect">{ui.tr("mine_heading")}</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">Describe a plant and every facility in the registry is ranked '
        'as a partner, on the same five factors as everything else here.</p>',
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
            st.markdown(ui.chip_row(
                [ui.chip(f'taken by {sector_name}', "accent") for sector_name in takers]
                or [ui.chip("no sector recorded takes this stream", "bad")]),
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
                f'<div class="sect">{ui.tr("mine_ranked")} &mdash; {len(mine)}</div>',
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
            render_verdict(chosen)
            render_detail_charts(chosen)
            with st.expander(ui.tr("audit"), expanded=False):
                render_audit(chosen)
    else:
        st.markdown(ui.chip_row([
            ui.chip(f'fill in the fields, then press {ui.tr("btn_rank")}', "accent"),
        ]), unsafe_allow_html=True)

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

        sankey = flow_sankey(view)
        if sankey is not None:
            st.markdown(
                ui.chip_row([
                    ui.chip("by-product", "accent"),
                    ui.chip("&rarr; application"),
                    ui.chip("&rarr; virgin material displaced", "good"),
                    ui.chip("thickness = tonnes a year"),
                ]), unsafe_allow_html=True)
            st.plotly_chart(sankey, width="stretch",
                            config={"displaylogo": False})

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
            st.markdown(ui.chip_row([
                ui.chip(f'{len(view)} flows drawn', "accent"),
                ui.chip("thickness = score"),
                ui.chip("dotted red = loses money", "bad"),
                ui.chip("drag to pan, scroll to zoom"),
                ui.chip(f'straight-line x {engine.ROAD_CIRCUITY_FACTOR:.2f}', "warn"),
                ui.chip("Survey of India boundary, bundled offline"),
            ]), unsafe_allow_html=True)

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

            render_verdict(row)

        render_detail_charts(row)
        with st.expander(ui.tr("audit"), expanded=False):
            render_audit(row)

# ======================================================================
# 4. Chains and impact
# ======================================================================

if section == "chains":
    st.markdown(f'<div class="sect">{ui.tr("chains_heading")}</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">Pairwise scoring cannot see an arrangement that only works '
        'through a third plant, or how to run them all at once. These two passes can.</p>',
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

    st.markdown(ui.chip_row([
        ui.chip("denominator is every tonne offered, gaps included", "accent"),
        ui.chip("virgin avoided = tonnage x substitution ratio", "accent"),
        ui.chip("water footprint not modelled", "warn"),
    ]), unsafe_allow_html=True)

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
    st.markdown(ui.chip_row([
        ui.chip(f'solver: {opt_report["solver"]}', "accent"),
        ui.chip("maximises net value subject to supply, intake and ceilings"),
        ui.chip("both plans feasible; neither agreed by anyone", "warn"),
    ]), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f'<div class="sect">{ui.tr("chains_found")} &mdash; {len(chains)}</div>',
                unsafe_allow_html=True)
    st.markdown(ui.chip_row([
        ui.chip("one plant receives a by-product and places its own", "accent"),
        ui.chip("ranked by the weakest link"),
    ]), unsafe_allow_html=True)

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
        st.markdown(ui.chip_row([
            ui.chip("each hop moves a different material"),
            ui.chip("no facility appears twice"),
            ui.chip("totals overstate if hops share tonnage", "warn"),
        ]), unsafe_allow_html=True)

# ======================================================================
# 5. Gap analysis
# ======================================================================

if section == "gaps":
    st.markdown(f'<div class="sect">{ui.tr("gaps_heading")}</div>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">Not errors - streams someone is paying to dispose of, which is '
        'where a new facility would pay for itself.</p>',
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
        st.markdown(ui.chip_row([
            ui.chip("compared on measured properties, not names", "accent"),
            ui.chip("a lead to test, never a scored match", "warn"),
            ui.chip("touches neither the score nor the valuation", "warn"),
        ]), unsafe_allow_html=True)
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
            st.markdown(ui.chip_row([
                ui.chip(f'closest: {best["material"]}', "accent"),
                ui.chip(f'{best["similarity"]:.0%} resemblance', "accent"),
                ui.chip(f'agrees on {best["shared_properties"]}', "good"),
                ui.chip(f'differs on {best["biggest_difference"]}', "warn"),
                ui.chip(f'taken by {best["accepting_sectors"]}'),
                ui.chip("test before you sign", "warn"),
            ]), unsafe_allow_html=True)

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

    m1, m2 = st.columns([1, 1.25], gap="medium")
    with m1:
        weights = list(engine.WEIGHTS.items())
        donut = go.Figure(go.Pie(
            labels=[FACTOR_LABELS[k] for k, _ in weights],
            values=[v for _, v in weights],
            hole=0.58, sort=False, direction="clockwise",
            marker=dict(colors=[FACTOR_COLOURS[k] for k, _ in weights],
                        line=dict(color="#ffffff", width=2)),
            texttemplate="%{label}<br>%{percent}",
            textposition="outside", textfont=dict(size=10),
            hovertemplate="<b>%{label}</b><br>weight %{value:.2f}<extra></extra>",
        ))
        donut.add_annotation(text="score<br>weights", showarrow=False,
                             font=dict(size=13, color="#1a1f2b"))
        donut.update_layout(
            height=330, margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor="rgba(0,0,0,0)", showlegend=False, font=CHART_FONT,
            hoverlabel=HOVER_STYLE,
        )
        st.plotly_chart(donut, width="stretch", config={"displaylogo": False})

    with m2:
        st.markdown(ui.chip_row([
            ui.chip(f'reject below {engine.MIN_SCORE_DEFAULT:.0f}', "bad"),
            ui.chip(f'reject beyond max_km x {engine.DISTANCE_HARD_LIMIT}', "bad"),
            ui.chip(f'reject under {engine.MIN_MATCH_TONNES:.0f} t/yr', "bad"),
            ui.chip("never matched to itself", "bad"),
        ]), unsafe_allow_html=True)
        st.markdown(ui.chip_row([
            ui.chip(f'road Rs {engine.FREIGHT_RATE}/t-km', "accent"),
            ui.chip(f'rail Rs {engine.RAIL_RATE}/t-km + Rs {engine.RAIL_TERMINAL_COST}/t',
                    "accent"),
            ui.chip(f'pipeline Rs {engine.PIPELINE_RATE:.0f}/t-km', "accent"),
            ui.chip(f'disposal Rs {engine.DISPOSAL_COST_DEFAULT}/t default', "accent"),
            ui.chip(f'road factor {engine.ROAD_CIRCUITY_FACTOR:.2f}x haversine',
                    "accent"),
        ]), unsafe_allow_html=True)
        st.markdown(ui.chip_row([
            ui.chip("capacities representative, not audited", "warn"),
            ui.chip("rupees gross across both parties, not margin", "warn"),
            ui.chip("CO2 is displaced production, not a verified credit", "warn"),
            ui.chip("distance is straight-line, not routed", "warn"),
            ui.chip("no quality specification checked in the logistics engine",
                    "warn"),
            ui.chip("water footprint not modelled", "warn"),
        ]), unsafe_allow_html=True)
        st.code(
            "material_value  = matched_t x substitution_ratio x virgin_value\n"
            "disposal_saved  = matched_t x disposal_rate\n"
            "transport_cost  = matched_t x (road_km x rate + terminal)\n"
            "processing_cost = matched_t x processing_rate\n"
            "net = material_value + disposal_saved - transport_cost - processing_cost",
            language="text",
        )

    with st.expander("Scoring formulas, gates and every assumption in full",
                     expanded=False):
        st.dataframe(
            pd.DataFrame([
                {"factor": "Quantity", "weight": engine.W_QUANTITY,
                 "formula": "matched_t / ceiling, where ceiling = receiver need "
                            "x max_share and matched_t = min(supplier output, ceiling)"},
                {"factor": "Proximity", "weight": engine.W_PROXIMITY,
                 "formula": f"max(0, 1 - (road_km / max_km) ^ {engine.PROXIMITY_EXPONENT})"},
                {"factor": "Processing", "weight": engine.W_PROCESSING,
                 "formula": "none 1.00, simple 0.85, moderate 0.55, complex 0.25"},
                {"factor": "Timing", "weight": engine.W_TIMING,
                 "formula": "months in which both sides are active, divided by 12"},
                {"factor": "Compliance", "weight": engine.W_COMPLIANCE,
                 "formula": f"unregulated {engine.COMPLIANCE_UNREGULATED:.2f}; "
                            f"regulated and authorised {engine.COMPLIANCE_REGULATED_AUTHORISED:.2f}; "
                            f"regulated and not {engine.COMPLIANCE_REGULATED_UNAUTHORISED:.2f}"},
            ]),
            hide_index=True, width="stretch",
            column_config={
                "factor": st.column_config.TextColumn("Factor", width="small"),
                "weight": st.column_config.NumberColumn("Weight", format="%.2f",
                                                        width="small"),
                "formula": st.column_config.TextColumn("Formula", width="large"),
            },
        )
        st.markdown(
            f"""
- Distance is haversine multiplied by **{engine.ROAD_CIRCUITY_FACTOR:.2f}** for road
  circuity. No routing, no traffic, no terrain.
- Rail is taken only above **{engine.RAIL_MIN_KM} km** and
  **{engine.RAIL_MIN_TONNES:,} t/yr**, and only when genuinely cheaper door to door.
- Disposal avoided defaults to **Rs {engine.DISPOSAL_COST_DEFAULT}/t**, overridden per
  material; for fly ash the saving is partly a compliance cost, since utilisation is
  already mandatory.
- max_share is anchored to IS 1489, IS 3812, IS 455, IS 383 and CPCB co-processing
  guidance where those exist.
- Timing divides overlapping active months by twelve, so a six-month crushing season
  feeding a year-round kiln scores 0.50.
- The quantity factor measures the receiver, not the supplier, so a large supplier can
  score 1.00 while placing a small fraction of its output - each match also reports
  supplier_share.
- Pairwise scores over-commit supply; allocated_tpa is a feasible plan and the
  optimiser solves the whole allocation at once.
- The materials layer's property profiles are indicative typical compositions, not
  assays, and feed only the grading and blending screens - never the logistics score.
- No language model produces any figure. The same registry always yields the same
  matches in the same order.
"""
        )

    st.markdown(f'<div class="sect">{ui.tr("method_kb")} '
                f'&mdash; {len(kb.SUBSTITUTIONS)}</div>', unsafe_allow_html=True)
    st.dataframe(
        kb_table(), hide_index=True, width="stretch", height=420,
        column_config={
            "material": st.column_config.TextColumn("By-product", width="medium"),
            "application": st.column_config.TextColumn("Application", width="medium"),
            "replaces": st.column_config.TextColumn("Replaces", width="medium"),
            "accepting sectors": st.column_config.TextColumn("Accepting sectors",
                                                             width="medium"),
            "ratio": st.column_config.NumberColumn("Ratio", format="%.2f",
                                                   width="small"),
            "max share": st.column_config.NumberColumn("Max share", format="%.2f",
                                                       width="small"),
            "max km": st.column_config.NumberColumn("Max km", format="%.0f",
                                                    width="small"),
            "CO2 t/t": st.column_config.NumberColumn("CO2 t/t", format="%.2f",
                                                     width="small"),
            "virgin value Rs/t": st.column_config.NumberColumn("Virgin Rs/t",
                                                               format="%.0f"),
            "disposal Rs/t": st.column_config.NumberColumn("Disposal Rs/t",
                                                           format="%.0f"),
            "note": st.column_config.TextColumn("Practical catch", width="large"),
        },
    )

    st.markdown('<div class="sect">Coverage and capacity</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<p class="sub">Two different numbers: what this registry holds, and how '
        'large the universe is that the engine could score.</p>',
        unsafe_allow_html=True,
    )
    st.dataframe(
        pd.DataFrame([{
            "register": entry["label"],
            "count": entry["count"],
            "as": reach.format_count(entry["count"]),
            "source": entry["source"],
            "period": entry["period"],
            "verified in this build": "no",
            "what it means here": entry["caveat"],
        } for entry in reach.ADDRESSABLE.values()]),
        hide_index=True, width="stretch",
        column_config={
            "register": st.column_config.TextColumn("Public register",
                                                    width="medium"),
            "count": st.column_config.NumberColumn("Count", format="%.0f"),
            "as": st.column_config.TextColumn("As reported", width="small"),
            "source": st.column_config.TextColumn("Source", width="medium"),
            "period": st.column_config.TextColumn("Period", width="medium"),
            "verified in this build": st.column_config.TextColumn("Verified here",
                                                                  width="small"),
            "what it means here": st.column_config.TextColumn("What it means here",
                                                              width="large"),
        },
    )
    st.markdown(ui.chip_row([
        ui.chip("loaded and addressable are different numbers", "warn"),
        ui.chip("none of these were fetched live from this build", "warn"),
        ui.chip("edit them in reach.py before quoting", "warn"),
    ]), unsafe_allow_html=True)

    if st.button("Run a capacity test", key="run_benchmark"):
        with st.spinner("Scoring a synthetic national registry..."):
            st.session_state["benchmark"] = reach.benchmark(facilities, 2000)
    bench = st.session_state.get("benchmark")
    if bench and bench.get("ran"):
        ui.stat_row([
            ui.stat_block("Synthetic facilities scored",
                          f'{bench["facilities"]:,}', "scattered across India"),
            ui.stat_block("Wall clock", f'{bench["seconds"]:.2f} s',
                          "single core, this machine"),
            ui.stat_block("Candidate exchanges found",
                          f'{bench["matches"]:,}', ""),
            ui.stat_block("Throughput",
                          f'{bench["facilities_per_second"]:,.0f} /s',
                          "facilities scored per second"),
        ], columns=4)
        st.markdown(ui.chip_row([
            ui.chip("synthetic registry, used only to time the engine", "warn"),
            ui.chip("never mixed with the loaded registry", "warn"),
            ui.chip("national spread - the hard case for the spatial index"),
        ]), unsafe_allow_html=True)

    with st.expander(ui.tr("method_registry"), expanded=False):
        st.dataframe(facilities, hide_index=True, width="stretch", height=300)
