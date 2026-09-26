"""How much of Indian industry this tool can actually serve.

There are two different numbers here and conflating them would be dishonest:

  LOADED      the facilities in the registry currently open. Counted live.
  ADDRESSABLE the size of the universe the engine could score if the data were
              supplied. NOT loaded, NOT claimed as coverage - it is the size of
              the problem, not the size of the demo.

Why the distinction is stated so loudly: a headline that reads "1,000,000
companies" over a 255-row registry is the fastest way to lose an assessor. The
moment they ask where the data came from, every other number in the tool is in
doubt. Reporting both, labelled, is the version that survives the question.

Verify before quoting
---------------------
The figures below are the published sizes of public registers, recorded here
with their source and the period they refer to. They could not be fetched live
from this build - the statistics portals are not reachable from it - so each
carries `verified = False` and the interface shows the source next to the
number. Check them against the current release before presenting, and edit them
here: they exist in exactly one place for that reason.
"""

from __future__ import annotations

# ----------------------------------------------------------------------
# Public registers of Indian industry, largest set first.
# ----------------------------------------------------------------------
ADDRESSABLE = {
    "udyam_msme": dict(
        count=63_000_000,
        label="Udyam-registered enterprises",
        source="Udyam Registration portal, Ministry of MSME",
        period="cumulative registrations, 2020 to 2025",
        verified=False,
        caveat="The outer bound, and the least useful of the three. Most Udyam "
               "registrations are micro enterprises in trade and services with "
               "no process by-product at all. Quoted here because it is the "
               "number people mean by 'how many companies in India', not "
               "because this tool could serve all of them.",
    ),
    "registered_factories": dict(
        count=250_000,
        label="Registered factories",
        source="Annual Survey of Industries frame, MoSPI",
        period="most recent published ASI frame",
        verified=False,
        caveat="The set this tool is actually built for: premises registered "
               "under the Factories Act that run a manufacturing process, and "
               "therefore generate a process residue and consume a raw "
               "material. This is the honest denominator for coverage.",
    ),
    "consented_red_orange": dict(
        count=80_000,
        label="Red and Orange category industrial units",
        source="CPCB / State Pollution Control Board consent categories",
        period="CPCB categorisation directions, 2016 onward",
        verified=False,
        caveat="The units whose by-products are regulated and already "
               "inventoried by a pollution control board - where a registry "
               "could realistically be assembled from existing filings rather "
               "than collected from scratch.",
    ),
}

# The set the interface leads with. The factory frame, not the MSME count:
# it is the one this tool can defend.
PRIMARY_KEY = "registered_factories"


def addressable(key: str = PRIMARY_KEY) -> dict:
    return ADDRESSABLE[key]


def format_count(value: int, lang: str = "en") -> str:
    """Indian numbering: crore and lakh, which is how these registers report."""
    value = float(value)
    if value >= 1e7:
        return f"{value / 1e7:,.2f} crore"
    if value >= 1e5:
        return f"{value / 1e5:,.2f} lakh"
    return f"{value:,.0f}"


# ----------------------------------------------------------------------
# What the engine can chew through, measured rather than asserted.
# ----------------------------------------------------------------------

def benchmark(base_registry, size: int = 2000, seed: int = 11) -> dict:
    """Score a synthetic national registry of `size` facilities and time it.

    The synthetic registry exists only to measure throughput - it is never
    shown as data and never mixed with the real one. Facilities are cloned from
    the loaded registry and scattered across India's landmass, which is the
    hard case for the spatial index: a clustered registry prunes better.
    """
    import random
    import time

    import pandas as pd

    import engine

    if base_registry is None or len(base_registry) == 0:
        return {"ran": False}

    random.seed(seed)
    rows = []
    for i in range(int(size)):
        src = dict(base_registry.iloc[i % len(base_registry)])
        src["name"] = f'{src["name"]} [synthetic {i}]'
        src["lat"] = random.uniform(8.5, 34.0)
        src["lon"] = random.uniform(69.5, 95.0)
        rows.append(src)
    registry = pd.DataFrame(rows)[engine.REQUIRED_COLUMNS]

    start = time.perf_counter()
    matches = engine.find_matches(registry)
    elapsed = time.perf_counter() - start

    return {
        "ran": True,
        "facilities": int(size),
        "seconds": elapsed,
        "matches": int(len(matches)),
        "facilities_per_second": (size / elapsed) if elapsed > 0 else 0.0,
        "seed": seed,
    }


def summary(facilities, kb_module, specs_module, materials_module) -> dict:
    """Everything the coverage panel needs, counted from what is loaded."""
    loaded = int(len(facilities)) if facilities is not None else 0
    sectors = int(facilities["sector"].nunique()) if loaded else 0
    states = int(facilities["state"].nunique()) if loaded else 0
    offered = 0
    if loaded:
        offered = int(((facilities["output_material"].astype(str).str.strip() != "")
                       & (facilities["output_tpa"] > 0)).sum())

    primary = addressable()
    return {
        "loaded": loaded,
        "sectors": sectors,
        "states": states,
        "supplying": offered,
        "substitutions": len(kb_module.SUBSTITUTIONS),
        "kb_materials": len(kb_module.materials()),
        "specifications": len(specs_module.SPECS),
        "profiled_materials": len(materials_module.MATERIAL_PROPERTIES),
        "addressable_count": primary["count"],
        "addressable_label": primary["label"],
        "addressable_source": primary["source"],
        "addressable_pretty": format_count(primary["count"]),
    }
