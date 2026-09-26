# Symbiosis Finder

Finds exchanges where one industrial plant's by-product can replace another's
virgin raw material, scores how practical each one actually is, and prices it
in tonnes diverted, CO₂ avoided and rupees per year.

Built for ENIGMA 5.0, Sustainability track, PS 5 — *Discovering Hidden
Industrial Symbiosis*.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Python 3.12 (works on 3.11), no database, no API keys, no credentials.

---

## The problem

Industries generate by-products they treat as waste while other industries
buy virgin raw materials those by-products could replace. Fly ash goes to an
ash pond while a cement plant 180 km away buys clinker. The matches are hard
to find because viability depends on material properties, quantity, location,
timing, transport, processing and regulation *simultaneously* — get any one
wrong and the exchange does not happen.

This tool searches that space exhaustively over a registry of facilities and
reports what it finds, including the exchanges that do not work and the
by-products that have nowhere to go.

## The approach

1. **A substitution knowledge base**, not keyword similarity. 48 documented
   substitutions across 32 by-product streams. Each records what displaces
   what, in what ratio, up to what fraction of the receiver's input, over what
   distance, with what processing, and what the practical catch is.
2. **Exhaustive pairwise search.** Every (supplier, by-product, receiver,
   application) combination in the registry is scored. Nothing is sampled and
   nothing is heuristically pruned.
3. **A five-factor score** that penalises the things that actually kill
   exchanges: tonnage mismatch, distance, seasonality, processing burden and
   regulatory friction.
4. **A valuation** in rupees per year, net of freight and processing, shown
   line by line.

### What makes it credible

- **Every number is computed in Python.** Deterministic — the same registry
  always produces the same matches in the same order, verified by a test that
  shuffles the input rows. No language model produces any figure. The
  explanation layer receives finished numbers and only arranges them into
  sentences.
- **Every score is auditable.** The interface shows each factor's raw value,
  its weight, the points it contributed and the expression that produced it,
  plus the money line by line and the tonnage chain from supplier output
  through the receiver's ceiling to what is actually allocated.
- **Bad matches are shown.** Exchanges costing more than they save are listed,
  labelled and explained, in the table, on the map in a different colour and
  in the KPI strip.
- **Unmatched streams get their own tab**, with the disposal cost being carried
  and why nothing fits — that is where a new facility would pay for itself.
- **The data's limits are stated in the interface**, not just here.

## Scoring

A match is one combination of supplier, by-product, receiver and application.
Score is 100 × the weighted sum of five factors, each normalised to 0–1.

| Factor | Weight | Formula |
|---|---|---|
| Quantity | 0.30 | `matched_t / ceiling`, where `ceiling = receiver_need × max_share` and `matched_t = min(supplier_output, ceiling)` |
| Proximity | 0.28 | `max(0, 1 - (road_km / max_km) ** 1.4)` |
| Processing | 0.16 | none 1.00, simple 0.85, moderate 0.55, complex 0.25 |
| Timing | 0.14 | months in which both sides are active, ÷ 12 |
| Compliance | 0.12 | unregulated 1.00; regulated and receiver authorised 0.75; regulated and not 0.25 |

**Gates.** Reject below score 35, beyond `max_km × 1.5`, or under 1 tonne a
year. A facility is never matched to itself. Between `max_km` and `max_km ×
1.5` a match is listed but scores zero on proximity and is labelled as past
its economic limit.

**Distance** is haversine great-circle, multiplied by 1.30 for road circuity.

### Valuation, per year

```
material_value  = matched_t × substitution_ratio × virgin_value
disposal_saved  = matched_t × disposal_rate        (default ₹1400/t, per-material override)
transport_cost  = matched_t × road_km × 6.5        (₹/tonne-km, bulk road freight)
processing_cost = matched_t × {none 0, simple 250, moderate 900, complex 2600}
net = material_value + disposal_saved - transport_cost - processing_cost
```

Every constant is a named module-level variable in `engine.py` with a comment
explaining it.

### What `max_share` and `max_km` are for

They are what stop this being naive. Fly ash can be about 35% of Portland
pozzolana cement, not 100% — IS 1489 Part 1 says so. Granulated slag can be up
to 70% under IS 455. Recycled aggregate is capped at 25% in plain concrete
under IS 383:2016. Textile ETP sludge co-processing needs CPCB authorisation
and contributes almost no heat.

Likewise distance. Bagasse stops travelling at about 120 km because it is
bulky and cheap; spent refinery catalyst carries enough recoverable
molybdenum and vanadium to ship 1200 km. A tool that ignores this will happily
propose shipping bagasse across the country.

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py          # opens on http://localhost:8501
python -m pytest test_engine.py -v
```

### The five tabs

1. **Find my matches** — describe your own plant from dropdowns (by-product or
   sector, nearest industrial centre, tonnage, operating season, hazardous-waste
   authorisation) and every facility in the registry is ranked as a partner. It
   runs the ordinary engine over the registry with your plant added, then filters
   to the exchanges you are part of — same five factors, same weights, same
   gates, so your ranking is directly comparable to everything else in the tool.
   Each result shows its score band, the money, the tonnage, and flags for the
   best option, a loss-maker and a haul past its economic limit.
2. **Exchange network** — every exchange drawn on a map of India with real state
   boundaries. States are shaded by a metric you choose (exchanges involved,
   tonnes supplied, tonnes received, facilities); flows are drawn between plants
   with thickness and opacity by score, dotted red where they lose money. Pan,
   zoom, hover any state for its totals, and filter by state, material or count.
3. **Ranked matches** — the full table with a score bar and CSV download, a
   detail panel with the plain-language case, and the full-width audit.
4. **Gap analysis** — by-products with no viable receiver, ranked by tonnage with
   the disposal cost carried, why nothing fits, and every recorded use.
5. **Method** — the weights, the gates, the valuation, every assumption, the
   known limits, and the whole knowledge base as a browsable table.

The sidebar switches between the sample registry and your own CSV, offers a
template, and sets the minimum score.

## Using your own registry

Upload a CSV with these columns:

| Column | Meaning |
|---|---|
| `name` | facility name (required) |
| `sector` | plant type; matched against the knowledge base's accepting sectors |
| `state` | used for filtering |
| `lat`, `lon` | decimal degrees (required) |
| `output_material` | the by-product offered; blank if the plant only receives |
| `output_tpa` | tonnes per year offered |
| `input_need_tpa` | tonnes per year of raw material input; 0 if it only supplies |
| `availability` | e.g. `continuous (year-round)`, `crushing season (Nov-Apr)` |
| `authorised_hazardous` | yes/no — whether the plant may handle regulated waste |

A plant with both an `output_material` and an `input_need_tpa` is both a
supplier and a receiver, which is how chains appear.

Common column spellings are accepted and renamed (`latitude`, `facility_name`,
`waste_tpa`, `demand_tpa` and others). Missing optional columns are filled with
defaults, text in numeric fields becomes zero, rows without usable coordinates
are dropped — and every repair is reported in the interface rather than
raising. Download the template from the sidebar for a working example.

## Sample registry

63 facilities at real Indian industrial locations with correct coordinates —
Bhilai, Jamshedpur, Rourkela, Durgapur, Visakhapatnam, Korba, Vindhyachal,
Singrauli, Ramagundam, Mundra, Satna, Jamnagar, Kochi, Jharsuguda, Lanjigarh,
Tirupur, Ludhiana, Kolhapur, Belagavi and others. 25 both supply and receive.

It is larger than the 45 originally sketched because covering 32 by-product
streams across a country-scale map needs enough candidate receivers that
materials fail on their own merits rather than on there being nobody in the
registry to ask.

At the default threshold it yields **75 viable exchanges** across 26 materials,
with scores from 39 to 100, **5 of which lose money**, and **10 by-product
streams with nowhere to go**.

## Files

```
app.py                      Streamlit interface
engine.py                   matching, scoring, valuation, validation
kb.py                       substitution knowledge base (48 entries)
explain.py                  computed numbers into plain language
sample_facilities.csv       sample registry (63 facilities)
data/india_states.geojson   simplified state boundaries for the map (139 KB)
test_engine.py              62 tests, one per acceptance criterion plus invariants
requirements.txt
.streamlit/config.toml      dark theme
```

## Limits

Read this before quoting any number from it.

- **Capacities in the sample registry are representative**, not audited. They
  are the right order of magnitude for a plant of that type at that location.
  They are not that plant's real figures and should not be cited as such.
- **Rupee values are gross, across both parties.** They are the size of the
  prize, not either side's margin. How it splits between supplier and receiver
  is a commercial negotiation that is not modelled. Virgin material prices are
  indicative Indian market levels and they move.
- **Distance is straight-line × 1.30**, not routed. No traffic, terrain, river
  crossings or road quality. A hill route will be worse than this says. Rail is
  cheaper than the assumed road rate and is not modelled at all.
- **Knowledge base coverage is the ceiling on what can be discovered.** 48
  substitutions is a screening tool, not an encyclopaedia. A stream it does not
  know cannot be matched — it lands in gap analysis, which is honest but not
  complete.
- **The quantity factor measures the receiver, not the supplier.** It is
  `matched_t / ceiling`, so any supplier whose output exceeds the receiver's
  ceiling scores 1.00 whether it places 90% of its output or 3%. Each match
  therefore also reports `supplier_share`, and the audit panel says so plainly.
- **Pairwise scores over-commit supply.** A supplier able to serve six
  receivers appears at full tonnage against each, so `matched_tpa` is not
  additive. The engine adds a greedy best-score-first allocation on top:
  `allocated_tpa` is a feasible plan that never promises the same tonne twice,
  and headline totals deduplicate by supplier and material. Neither is a plan
  anyone has agreed to.
- **No quality specification is checked.** Two plants may both handle "fly ash"
  and still be incompatible on fineness, loss on ignition or chloride content.
  The knowledge base note flags this per material; the engine cannot enforce it.
- **CO₂ figures count displaced production emissions only.** They are not
  verified carbon credits and would not survive a registry audit as stated.
  Process CO₂ reuse is *not* sequestration — the carbon is released later.
- **Energy streams are forced into a mass model.** Waste heat has no tonnage;
  its registry figure is tonnes of coal equivalent, and coke oven gas is priced
  on a natural-gas displacement basis. Both are flagged wherever they appear.
- **State boundaries are simplified.** They come from a public GeoJSON reduced
  from 526,000 coordinate points to 7,700 (about 2 km of detail) so the browser
  can draw the country instantly. They are for orientation, not for measuring
  anything, and are not a statement about any boundary.
- **The map is drawn as plain filled shapes, not on a Plotly geo projection.** A
  geo subplot fetches its own basemap from Plotly's CDN even with the basemap
  switched off, and this app is meant to run with no internet. Longitude is
  plotted as x, latitude as y, with the aspect ratio anchored at 1.08 (a degree
  of latitude is about 111 km; a degree of longitude about 103 km at 22°N). Over
  a country this size the distortion is cosmetic, and no distance shown anywhere
  is measured off the map — every one is haversine, computed in `engine.py`.
- **The app makes one external request: a Google Fonts stylesheet.** Nothing
  depends on it; without a connection the type falls back to the system stack and
  everything else, the map included, works exactly the same.

## Testing

```bash
python -m pytest test_engine.py -v
```

62 tests covering: the knowledge base is well formed and anchored to the
standards it cites; matched tonnage never exceeds supplier output or the
receiver's ceiling; no self-matches; no match beyond `max_km × 1.5`; scores are
spread rather than clustered and equal the sum of their weighted contributions;
seasonal suppliers score below 1.0 on timing; regulated materials score below
1.0 on compliance; the gap list is non-empty and covers both kinds of failure;
loss-making matches are listed and their explanations say so; the allocation
never over-commits a supplier or a receiver; results are identical when the
input rows are shuffled; a CSV with missing columns, text in numeric fields and
bad coordinates produces warnings rather than a traceback; every match and
every gap produces explanation text; a plant described through the interface is
scored by the same engine with no special-casing, and its compliance factor
responds to the hazardous-waste authorisation toggle; the state rollup
reconciles against the allocation; and the bundled boundary file covers every
state in the registry with closed rings inside India's bounding box.
