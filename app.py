"""Symbiosis Finder - Streamlit interface.

Discovers exchanges where one plant's by-product can replace another's raw
material, scores how practical each one actually is, and prices it. Every
figure on screen is computed in engine.py; this module only displays them.
"""

from __future__ import annotations

import io

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

# Typography and spacing only - no colour overrides, so .streamlit/config.toml
# stays the single source of truth for the theme.
st.markdown(
    """
    <style>
      .block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1500px;}
      h1 {font-size: 1.85rem !important; font-weight: 650; letter-spacing: -0.02em;}
      h2 {font-size: 1.15rem !important; font-weight: 600; margin-top: 1.4rem;}
      h3 {font-size: 1.0rem !important; font-weight: 600;}
      [data-testid="stMetricValue"] {font-size: 1.45rem; font-weight: 620;}
      [data-testid="stMetricLabel"] {font-size: 0.78rem; opacity: 0.72;
        text-transform: uppercase; letter-spacing: 0.06em;}
      .caveat {font-size: 0.80rem; opacity: 0.62; line-height: 1.5;}
      .sec-title {font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.09em;
        opacity: 0.60; margin-bottom: 0.15rem; font-weight: 600;}
      .sec-body {font-size: 0.93rem; line-height: 1.62; margin-bottom: 0.95rem;}
      .headline {font-size: 1.02rem; line-height: 1.55; font-weight: 550;
        padding: 0.8rem 1rem; border-left: 3px solid #4cc9a4;
        background: rgba(76,201,164,0.07); border-radius: 3px; margin-bottom: 1.1rem;}
      .headline.loss {border-left-color: #e8794a; background: rgba(232,121,74,0.07);}
      div[data-testid="stDataFrame"] {font-variant-numeric: tabular-nums;}
    </style>
    """,
    unsafe_allow_html=True,
)

SUPPLIER_COLOUR = "#4cc9a4"
RECEIVER_COLOUR = "#6aa8ff"
LOSS_COLOUR = "#e8794a"


# ======================================================================
# Data loading - cached on the registry text, so uploads and the sample
# registry are treated identically and the engine runs once per input.
# ======================================================================

@st.cache_data(show_spinner=False)
def read_registry(csv_text: str):
    """Parse and validate a registry from raw CSV text."""
    try:
        raw = pd.read_csv(io.StringIO(csv_text))
    except Exception as exc:                     # malformed file, not a crash
        return pd.DataFrame(columns=engine.REQUIRED_COLUMNS), [
            f"The file could not be read as CSV: {exc}"
        ]
    return engine.validate(raw)


@st.cache_data(show_spinner=False)
def run_engine(csv_text: str, min_score: float):
    """Full pipeline: validate, match, find gaps, total up."""
    clean, problems = read_registry(csv_text)
    matches = engine.find_matches(clean, min_score)
    gaps = engine.unmatched_outputs(clean, matches)
    summary = engine.network_summary(matches)
    return clean, problems, matches, gaps, summary


@st.cache_data(show_spinner=False)
def sample_registry_text() -> str:
    with open("sample_facilities.csv", encoding="utf-8") as fh:
        return fh.read()


@st.cache_data(show_spinner=False)
def kb_table() -> pd.DataFrame:
    rows = []
    for e in kb.SUBSTITUTIONS:
        rows.append({
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
        })
    return pd.DataFrame(rows)


# ======================================================================
# Sidebar
# ======================================================================

with st.sidebar:
    st.markdown("### Registry")
    source = st.radio(
        "Source",
        ["Sample registry", "Upload a CSV"],
        label_visibility="collapsed",
    )

    csv_text = sample_registry_text()
    if source == "Upload a CSV":
        uploaded = st.file_uploader("Facility registry (CSV)", type=["csv"])
        if uploaded is not None:
            csv_text = uploaded.getvalue().decode("utf-8", errors="replace")
        else:
            st.info("No file yet - showing the sample registry.")

    st.download_button(
        "Download CSV template",
        data=engine.template_csv(),
        file_name="registry_template.csv",
        mime="text/csv",
        width="stretch",
    )

    st.markdown("### Threshold")
    min_score = st.slider(
        "Minimum score",
        min_value=0, max_value=90,
        value=int(engine.MIN_SCORE_DEFAULT), step=1,
        help="Exchanges scoring below this are not listed. The engine's own floor "
             "is 35 - lowering this shows weaker pairings, not new ones.",
    )

    st.markdown(
        '<p class="caveat">Sample capacities are representative of plants of this '
        'type, not audited figures. Rupee values are the size of the prize across '
        'both parties, not either one\'s margin.</p>',
        unsafe_allow_html=True,
    )

facilities, problems, matches, gaps, summary = run_engine(csv_text, float(min_score))

# ======================================================================
# Header and KPI strip
# ======================================================================

st.markdown("# Symbiosis Finder")
st.markdown(
    f'<p class="caveat">Industrial by-product exchange discovery across '
    f'{len(facilities)} facilities and {len(kb.SUBSTITUTIONS)} documented '
    f'substitutions. Every number below is computed in Python and auditable '
    f'to its inputs.</p>',
    unsafe_allow_html=True,
)

if problems:
    with st.expander(f"Data quality: {len(problems)} note(s) on this registry", expanded=False):
        for p in problems:
            st.warning(p, icon=None)

if facilities.empty:
    st.error("No usable facilities in this registry. Check the columns against the template.")
    st.stop()

unmatched_tonnes = float(gaps["output_tpa"].sum()) if len(gaps) else 0.0
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Viable exchanges", f"{summary['exchanges']:,}",
          help="Supplier, by-product, receiver and application combinations clearing "
               "every gate at the current threshold.")
k2.metric("Tonnes diverted", engine.tonnes(summary["tonnes_diverted"]),
          help="Best match per supplier and material, so a supplier's output is never "
               "counted twice.")
k3.metric("CO2 avoided", engine.tonnes(summary["co2_avoided_t"]) + " / yr")
k4.metric("Value unlocked", engine.inr(summary["value_unlocked"]),
          delta=f"{summary['loss_making']} run at a loss",
          delta_color="inverse",
          help="Net of freight and processing. The delta counts exchanges whose net is "
               "negative - they are listed and labelled, not hidden.")
k5.metric("Still unmatched", engine.tonnes(unmatched_tonnes),
          help="By-products with no viable receiver anywhere in this registry.")

st.markdown(
    '<p class="caveat">Tonnes diverted and value unlocked deduplicate by supplier and '
    'material. A feasible allocation across several receivers, which never promises the '
    'same tonne twice, places '
    f'{engine.tonnes(summary["allocated_tonnes"])} for {engine.inr(summary["allocated_value"])} '
    '- see Method.</p>',
    unsafe_allow_html=True,
)

tab_network, tab_matches, tab_gaps, tab_method = st.tabs(
    ["Exchange network", "Ranked matches", "Gap analysis", "Method"]
)

# ======================================================================
# 1. Exchange network
# ======================================================================

with tab_network:
    if matches.empty:
        st.info("No exchanges clear the current threshold, so there is no network to draw.")
    else:
        f1, f2, f3, f4 = st.columns([2, 2, 1.3, 1.1])
        states = sorted(set(matches["supplier_state"]) | set(matches["receiver_state"]))
        pick_states = f1.multiselect("States", states, default=[],
                                     placeholder="All states")
        materials = sorted(matches["material"].unique())
        pick_materials = f2.multiselect("Materials", materials, default=[],
                                        placeholder="All materials")
        show_n = f3.slider("Exchanges to draw", 5, max(6, min(200, len(matches))),
                           min(60, len(matches)), step=5)
        # Plotly fetches its geographic basemap from cdn.plot.ly at render time. That is
        # the only network call anywhere in this app, and it is the browser's, not the
        # server's. Turning the basemap off draws the same network on plain axes with
        # nothing fetched at all, so the tool still works on a dead connection.
        use_basemap = f4.toggle("Basemap", value=True,
                                help="Off draws the same network on plain lat/lon axes "
                                     "with no basemap fetch - use this if the venue "
                                     "network is unreliable.")

        view = matches
        if pick_states:
            view = view[view["supplier_state"].isin(pick_states)
                        | view["receiver_state"].isin(pick_states)]
        if pick_materials:
            view = view[view["material"].isin(pick_materials)]
        view = view.head(show_n)

        if view.empty:
            st.info("No exchanges match those filters.")
        else:
            fig = go.Figure()
            Trace = go.Scattergeo if use_basemap else go.Scatter

            def coords(lon_pair, lat_pair):
                """Scattergeo takes lon/lat; plain Scatter takes x/y."""
                if use_basemap:
                    return {"lon": lon_pair, "lat": lat_pair}
                return {"x": lon_pair, "y": lat_pair}

            # One trace per exchange: thickness and opacity scale with score, so the
            # strong exchanges read first.
            for row in view.itertuples(index=False):
                strength = float(row.score) / 100.0
                fig.add_trace(Trace(
                    mode="lines",
                    line=dict(
                        width=0.9 + 3.6 * strength,
                        color=LOSS_COLOUR if row.net_value < 0 else SUPPLIER_COLOUR,
                    ),
                    opacity=0.22 + 0.62 * strength,
                    hoverinfo="text",
                    text=(
                        f"{row.material}: {row.supplier} to {row.receiver}"
                        f"<br>Score {row.score:.1f}"
                        f"<br>{engine.tonnes(row.matched_tpa)}/yr over {row.road_km:,.0f} km"
                        f"<br>Net {engine.inr(row.net_value)}/yr"
                    ),
                    showlegend=False,
                    **coords([row.supplier_lon, row.receiver_lon],
                             [row.supplier_lat, row.receiver_lat]),
                ))

            sup = view.drop_duplicates("supplier")
            rec = view.drop_duplicates("receiver")
            fig.add_trace(Trace(
                mode="markers", name="Supplier",
                marker=dict(size=9, color=SUPPLIER_COLOUR, opacity=0.92,
                            line=dict(width=0.8, color="#0e1117")),
                hoverinfo="text",
                text=[f"{n}<br>{s} - {m}" for n, s, m in
                      zip(sup["supplier"], sup["supplier_sector"], sup["material"])],
                **coords(sup["supplier_lon"], sup["supplier_lat"]),
            ))
            fig.add_trace(Trace(
                mode="markers", name="Receiver",
                marker=dict(size=9, color=RECEIVER_COLOUR, opacity=0.92,
                            symbol="square",
                            line=dict(width=0.8, color="#0e1117")),
                hoverinfo="text",
                text=[f"{n}<br>{s}" for n, s in
                      zip(rec["receiver"], rec["receiver_sector"])],
                **coords(rec["receiver_lon"], rec["receiver_lat"]),
            ))

            if use_basemap:
                # Bounded to India. No mapbox, no token, no access key.
                fig.update_geos(
                    resolution=50,
                    scope="asia",
                    showcountries=True, countrycolor="#3a4152",
                    showsubunits=True, subunitcolor="#2a3040",
                    showland=True, landcolor="#141821",
                    showocean=True, oceancolor="#0b0e14",
                    showlakes=False, showframe=False, showcoastlines=True,
                    coastlinecolor="#3a4152",
                    lataxis_range=[engine.INDIA_BOUNDS["lat_min"],
                                   engine.INDIA_BOUNDS["lat_max"]],
                    lonaxis_range=[engine.INDIA_BOUNDS["lon_min"],
                                   engine.INDIA_BOUNDS["lon_max"]],
                )
            else:
                fig.update_xaxes(
                    title="Longitude", range=[engine.INDIA_BOUNDS["lon_min"],
                                              engine.INDIA_BOUNDS["lon_max"]],
                    gridcolor="#222836", zeroline=False, dtick=5,
                    # constrain the drawing area rather than widening the range, so the
                    # view stays bounded to India instead of stretching to fill the page
                    constrain="domain",
                )
                fig.update_yaxes(
                    title="Latitude", range=[engine.INDIA_BOUNDS["lat_min"],
                                             engine.INDIA_BOUNDS["lat_max"]],
                    gridcolor="#222836", zeroline=False, dtick=5,
                    # 1 degree of latitude is about 111 km; 1 degree of longitude about
                    # 103 km at 22 N. Anchoring the aspect keeps distances honest.
                    scaleanchor="x", scaleratio=1.08, constrain="domain",
                )

            fig.update_layout(
                height=620, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)" if use_basemap else "#0b0e14",
                font=dict(color="#e6e9ef", size=12),
                legend=dict(orientation="h", yanchor="bottom", y=0.01, x=0.01,
                            bgcolor="rgba(14,17,23,0.72)"),
            )
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.markdown(
                f'<p class="caveat">{len(view)} exchange(s) drawn. Line thickness and '
                'opacity scale with score; orange lines lose money. Lines are '
                'straight-line links, not routed roads - scoring uses straight-line '
                f'distance inflated {engine.ROAD_CIRCUITY_FACTOR:.2f}x. '
                + ('The basemap outline is fetched by your browser from Plotly\'s CDN; '
                   'turn Basemap off for a fully offline view.' if use_basemap
                   else 'No basemap: plain axes, nothing fetched.')
                + '</p>',
                unsafe_allow_html=True,
            )


# ======================================================================
# 2. Ranked matches
# ======================================================================

with tab_matches:
    if matches.empty:
        st.info("No exchanges clear the current threshold.")
    else:
        left, right = st.columns([1.05, 1])

        with left:
            st.markdown("## Ranked exchanges")
            table = matches[[
                "rank", "score", "supplier", "material", "receiver",
                "matched_tpa", "road_km", "net_value",
            ]].copy()
            table["at a loss"] = matches["net_value"] < 0
            st.dataframe(
                table, hide_index=True, height=560, width="stretch",
                column_config={
                    "rank": st.column_config.NumberColumn("#", width="small"),
                    "score": st.column_config.ProgressColumn(
                        "Score", min_value=0, max_value=100, format="%.1f", width="medium"),
                    "supplier": st.column_config.TextColumn("Supplier"),
                    "material": st.column_config.TextColumn("By-product"),
                    "receiver": st.column_config.TextColumn("Receiver"),
                    "matched_tpa": st.column_config.NumberColumn("t/yr", format="%.0f"),
                    "road_km": st.column_config.NumberColumn("km", format="%.0f"),
                    "net_value": st.column_config.NumberColumn("Net Rs/yr", format="%.0f"),
                    "at a loss": st.column_config.CheckboxColumn("Loss", width="small"),
                },
            )
            st.download_button(
                "Download all matches as CSV",
                data=matches.to_csv(index=False).encode("utf-8"),
                file_name="symbiosis_matches.csv",
                mime="text/csv",
                width="stretch",
            )

        with right:
            labels = [
                f"{r.rank}. {r.material} - {r.supplier} to {r.receiver}"
                for r in matches.itertuples(index=False)
            ]
            chosen = st.selectbox("Exchange", labels, index=0, key="match_pick")
            row = matches.iloc[labels.index(chosen)]
            story = explain.explain(row)

            loss = float(row["net_value"]) < 0
            st.markdown(
                f'<div class="headline{" loss" if loss else ""}">{story["headline"]}</div>',
                unsafe_allow_html=True,
            )

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Score", f"{row['score']:.1f}")
            m2.metric("Tonnes/yr", engine.tonnes(row["matched_tpa"]))
            m3.metric("Net value/yr", engine.inr(row["net_value"]))
            m4.metric("CO2 avoided/yr", engine.tonnes(row["co2_avoided_t"]))

            if bool(row["beyond_max_km"]):
                st.warning(
                    f"This haul of {row['road_km']:,.0f} km is past the "
                    f"{row['max_km']:,.0f} km economic limit for {row['material']}. It is "
                    "admitted by the distance gate but scores zero on proximity.",
                    icon=None,
                )

            for title in explain.SECTION_ORDER:
                st.markdown(f'<p class="sec-title">{title}</p>', unsafe_allow_html=True)
                st.markdown(
                    f'<p class="sec-body">{story["sections"][title]}</p>',
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        with st.expander("Audit this score and valuation", expanded=False):
            st.markdown("**Score: five factors, weighted**")
            audit = pd.DataFrame([
                {"factor": "Quantity", "raw": row["f_quantity"],
                 "weight": engine.W_QUANTITY, "points": row["c_quantity"],
                 "how it was computed":
                     f"matched {row['matched_tpa']:,.0f} t / ceiling "
                     f"{row['ceiling_tpa']:,.0f} t "
                     f"(need {row['receiver_need_tpa']:,.0f} t x max share "
                     f"{row['max_share']:.2f})"},
                {"factor": "Proximity", "raw": row["f_proximity"],
                 "weight": engine.W_PROXIMITY, "points": row["c_proximity"],
                 "how it was computed":
                     f"max(0, 1 - ({row['road_km']:,.0f} km / {row['max_km']:,.0f} km) "
                     f"^ {engine.PROXIMITY_EXPONENT})"},
                {"factor": "Timing", "raw": row["f_timing"],
                 "weight": engine.W_TIMING, "points": row["c_timing"],
                 "how it was computed":
                     f"months both active / 12; supplier {row['supplier_availability']}, "
                     f"receiver {row['receiver_availability']}"},
                {"factor": "Processing", "raw": row["f_processing"],
                 "weight": engine.W_PROCESSING, "points": row["c_processing"],
                 "how it was computed":
                     f"'{row['processing']}' processing maps to "
                     f"{engine.PROCESSING_FACTOR[row['processing']]:.2f}"},
                {"factor": "Compliance", "raw": row["f_compliance"],
                 "weight": engine.W_COMPLIANCE, "points": row["c_compliance"],
                 "how it was computed":
                     f"hazard '{row['hazard']}', receiver authorised "
                     f"{bool(row['receiver_authorised'])}"},
            ])
            st.dataframe(
                audit, hide_index=True, width="stretch",
                column_config={
                    "factor": st.column_config.TextColumn("Factor", width="small"),
                    "raw": st.column_config.ProgressColumn(
                        "Raw value (0-1)", min_value=0, max_value=1, format="%.3f"),
                    "weight": st.column_config.NumberColumn("Weight", format="%.2f",
                                                            width="small"),
                    "points": st.column_config.NumberColumn("Points", format="%.2f",
                                                            width="small"),
                    "how it was computed": st.column_config.TextColumn(
                        "How it was computed", width="large"),
                },
            )
            st.markdown(
                f"Total: **{row['score']:.2f}** of 100 "
                f"(sum of points; weights sum to {sum(engine.WEIGHTS.values()):.2f})."
            )

            st.markdown("**Valuation, line by line, per year**")
            money = pd.DataFrame([
                {"line": "Virgin material displaced", "amount": row["material_value"],
                 "how it was computed":
                     f"{row['matched_tpa']:,.0f} t x ratio {row['substitution_ratio']:.2f} "
                     f"x Rs {row['virgin_value']:,.0f}/t"},
                {"line": "Disposal avoided", "amount": row["disposal_saved"],
                 "how it was computed":
                     f"{row['matched_tpa']:,.0f} t x Rs {row['disposal_rate']:,.0f}/t"},
                {"line": "Transport", "amount": -row["transport_cost"],
                 "how it was computed":
                     f"{row['matched_tpa']:,.0f} t x {row['road_km']:,.0f} km x "
                     f"Rs {row['freight_rate']:,.1f}/t-km ({row['transport_mode']})"},
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
                    "how it was computed": st.column_config.TextColumn(
                        "How it was computed", width="large"),
                },
            )

            st.markdown("**Tonnage and allocation**")
            st.dataframe(
                pd.DataFrame([
                    {"quantity": "Supplier output", "t/yr": row["supplier_output_tpa"]},
                    {"quantity": "Receiver input need", "t/yr": row["receiver_need_tpa"]},
                    {"quantity": f"Ceiling at max share {row['max_share']:.2f}",
                     "t/yr": row["ceiling_tpa"]},
                    {"quantity": "Matched in this pairing", "t/yr": row["matched_tpa"]},
                    {"quantity": "Allocated once other matches are served",
                     "t/yr": row["allocated_tpa"]},
                ]),
                hide_index=True, width="stretch",
                column_config={
                    "quantity": st.column_config.TextColumn("Quantity", width="large"),
                    "t/yr": st.column_config.NumberColumn("t/yr", format="%.0f"),
                },
            )
            st.markdown(
                f'<p class="caveat">This pairing places '
                f'{row["supplier_share"] * 100:.0f}% of the supplier\'s output of '
                f'{row["material"]}. The quantity factor measures how much of the '
                '<em>receiver\'s</em> ceiling is filled, so a very large supplier can '
                'score 1.00 while still placing a small fraction of its output - that '
                'is what this line exposes.</p>',
                unsafe_allow_html=True,
            )
            st.markdown(f'<p class="caveat">Knowledge base note: {row["note"]}</p>',
                        unsafe_allow_html=True)

# ======================================================================
# 3. Gap analysis
# ======================================================================

with tab_gaps:
    st.markdown("## By-products with no viable receiver")
    st.markdown(
        '<p class="caveat">These are not errors. Each is a stream someone is paying to '
        'dispose of, with no receiver in this registry that clears the gates - which is '
        'exactly where a new processing or aggregation facility would pay for '
        'itself.</p>',
        unsafe_allow_html=True,
    )

    if gaps.empty:
        st.success("Every by-product in this registry found at least one viable receiver.")
    else:
        g1, g2, g3 = st.columns(3)
        g1.metric("Unplaced streams", f"{len(gaps):,}")
        g2.metric("Tonnes with nowhere to go", engine.tonnes(gaps["output_tpa"].sum()))
        g3.metric("Disposal cost carried", engine.inr(gaps["disposal_cost"].sum()) + " / yr")

        st.dataframe(
            gaps[["supplier", "sector", "state", "material", "output_tpa",
                  "disposal_cost", "recorded_uses", "candidate_sectors"]],
            hide_index=True, width="stretch", height=320,
            column_config={
                "supplier": st.column_config.TextColumn("Facility"),
                "sector": st.column_config.TextColumn("Sector", width="small"),
                "state": st.column_config.TextColumn("State", width="small"),
                "material": st.column_config.TextColumn("By-product"),
                "output_tpa": st.column_config.NumberColumn("t/yr", format="%.0f"),
                "disposal_cost": st.column_config.NumberColumn("Disposal Rs/yr", format="%.0f"),
                "recorded_uses": st.column_config.NumberColumn("Known uses", width="small"),
                "candidate_sectors": st.column_config.TextColumn(
                    "Sectors that could take it", width="large"),
            },
        )

        gap_labels = [
            f"{r.material} - {r.supplier} ({r.output_tpa:,.0f} t/yr)"
            for r in gaps.itertuples(index=False)
        ]
        picked = st.selectbox("Examine a stream", gap_labels, index=0, key="gap_pick")
        gap = gaps.iloc[gap_labels.index(picked)]

        st.markdown(f'<div class="headline loss">{explain.explain_gap(gap)}</div>',
                    unsafe_allow_html=True)

        uses = kb.uses_for(gap["material"])
        st.markdown("### Every recorded use for this stream")
        if not uses:
            st.info(
                "The knowledge base records no use for this material. Adding one is a "
                "research task, not a code change - see kb.py."
            )
        else:
            st.dataframe(
                pd.DataFrame([{
                    "application": u["application"],
                    "replaces": u["replaces"],
                    "accepting sectors": ", ".join(u["accepting_sectors"]),
                    "max share": u["max_share"],
                    "max km": u["max_km"],
                    "processing": u["processing"],
                    "hazard": u["hazard"],
                    "note": u["note"],
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
# 4. Method
# ======================================================================

with tab_method:
    st.markdown("## How a match is scored")
    st.markdown(
        "A match is one combination of supplier, by-product, receiver and application. "
        "The score is 100 times the weighted sum of five factors, each normalised to 0-1."
    )
    st.dataframe(
        pd.DataFrame([
            {"factor": "Quantity", "weight": engine.W_QUANTITY,
             "formula": "matched_t / ceiling, where ceiling = receiver need x max_share "
                        "and matched_t = min(supplier output, ceiling)"},
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

    st.markdown("## Gates")
    st.markdown(
        f"- Reject any pairing scoring below **{engine.MIN_SCORE_DEFAULT:.0f}**.\n"
        f"- Reject any haul beyond **max_km x {engine.DISTANCE_HARD_LIMIT}**. Between max_km "
        "and that limit a match is listed but scores zero on proximity, and is labelled.\n"
        f"- Reject anything under **{engine.MIN_MATCH_TONNES:.0f} tonne** a year.\n"
        "- A facility is never matched to itself."
    )

    st.markdown("## Valuation, per year")
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

    st.markdown("## Every assumption, stated")
    st.markdown(
        f"""
- **Distance** is haversine great-circle distance multiplied by
  **{engine.ROAD_CIRCUITY_FACTOR:.2f}** for road circuity. No routing engine, no traffic, no
  terrain. A hill road or a river crossing will be worse than this says.
- **Freight** is **Rs {engine.FREIGHT_RATE}/tonne-km**, bulk road, full truck loads. Part loads
  and return-empty legs cost more. Rail is cheaper and is not modelled.
- **Pipeline** transfer for waste heat and coke oven gas is priced separately at
  **Rs {engine.PIPELINE_RATE:.0f}/tonne-km** as an amortised figure. Far dearer per km than road,
  which is why those exchanges only work over a few kilometres.
- **Disposal avoided** defaults to **Rs {engine.DISPOSAL_COST_DEFAULT}/tonne**, overridden per
  material where that is wrong: a hazardous stream routed to a TSDF costs several times this,
  a captive ash pond rather less. For fly ash the saving is partly a compliance cost rather
  than a landfill fee, since utilisation is already mandatory.
- **Processing costs** are order-of-magnitude figures per tonne handled, not quotations.
- **Virgin material values** are indicative Indian market levels, not contract prices, and
  they move.
- **CO2 avoided** counts the displaced virgin material's production emissions only. It is not
  a verified carbon credit and would not survive a registry audit as stated. Process CO2 reuse
  is **not** sequestration - the carbon is released later.
- **max_share** is anchored to Indian standards where they exist: IS 1489 and IS 3812 for fly
  ash in PPC, IS 455 for slag cement, IS 383 for recycled aggregate, CPCB co-processing
  guidance for regulated and mixed streams. Where no standard exists it reflects published
  plant practice.
- **Timing** divides overlapping active months by twelve. A six-month crushing season feeding a
  year-round kiln therefore scores 0.50, because for half the year the kiln must source
  elsewhere or someone must pay to store the material.
- **Capacities in the sample registry** are representative of plants of that type at those
  locations. They are not audited plant data and should not be quoted as such.
- **Rupee values** are the gross prize across both parties. How it splits between supplier and
  receiver is a commercial negotiation, and neither party's margin is modelled.
- **Determinism**: no language model produces any figure here. The explanation text receives
  finished numbers and only arranges them into sentences.
"""
    )

    st.markdown("## Known limits of this model")
    st.markdown(
        f"""
- **The quantity factor measures the receiver, not the supplier.** It is
  `matched_t / ceiling`, so any supplier whose output exceeds the receiver's ceiling scores
  1.00 - whether it places 90% of its output or 3%. Each match therefore also reports
  `supplier_share`, and the audit panel says so explicitly.
- **Scores are pairwise, so `matched_tpa` over-commits supply.** A supplier able to serve six
  receivers appears at full tonnage against each. The engine adds a greedy best-score-first
  allocation on top: `allocated_tpa` is a feasible plan that never promises the same tonne
  twice. At the current threshold that plan places
  **{engine.tonnes(summary['allocated_tonnes'])}** for **{engine.inr(summary['allocated_value'])}**,
  against a headline **{engine.tonnes(summary['tonnes_diverted'])}** for
  **{engine.inr(summary['value_unlocked'])}** taken as the best match per supplier and material.
  Neither is a plan anyone has agreed to.
- **Energy streams are forced into a mass model.** Waste heat has no tonnage; its registry
  figure is tonnes of coal equivalent, and coke oven gas is priced on a natural-gas
  displacement basis. Both are flagged in the interface wherever they appear.
- **Knowledge base coverage is the ceiling on discovery.** {len(kb.SUBSTITUTIONS)} substitutions
  across {len(kb.materials())} materials is a screening tool, not an encyclopaedia. A stream
  it does not know cannot be matched - it lands in gap analysis, which is the honest outcome
  but not the complete one.
- **No quality specification is checked.** Two facilities may both handle 'fly ash' and still
  be incompatible on fineness, loss on ignition or chloride. The knowledge base note flags
  this per material; the engine cannot.
"""
    )

    st.markdown(f"## Knowledge base: {len(kb.SUBSTITUTIONS)} substitutions")
    st.markdown(
        '<p class="caveat">The whole basis for matching, browsable. Nothing is matched that '
        'is not in this table.</p>',
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

    st.markdown("## Registry in use")
    st.dataframe(facilities, hide_index=True, width="stretch", height=320)
