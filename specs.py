"""Specification library: what each application actually requires.

A specification is a list of limits. Each limit is

    (property_expression, operator, threshold, unit_note)

where `property_expression` is a property key from materials.py, or a sum of
them written with "+", as in "sio2+al2o3+fe2o3". Operators are ">=" and "<=".

Provenance, and why it is marked
--------------------------------
`confidence` is either:

  "standard"   - the threshold is taken from the named Indian Standard and can
                 be checked against it.
  "indicative" - there is no single published numeric limit, or the real
                 acceptance test is not a chemical one (a geotechnical index, a
                 trial burn, a plant's own kiln chemistry). The number is a
                 screening threshold drawn from common practice.

The interface shows this on every row. An indicative limit is never presented as
if it were an IS requirement - that distinction is the difference between a tool
an engineer can use and one that merely looks authoritative.
"""

from __future__ import annotations

SPECS = {
    # ==================================================================
    # High value - the specifications a stream has to earn
    # ==================================================================
    "Silica fume for high-performance concrete (IS 15388)": dict(
        standard="IS 15388: 2003",
        confidence="standard",
        value_inr_t=42000,
        sector="construction materials",
        limits=[
            ("sio2", ">=", 85.0, "% minimum silica"),
            ("loi", "<=", 4.0, "% loss on ignition"),
            ("moisture", "<=", 3.0, "% free moisture"),
            ("retained_45um", "<=", 10.0, "% retained on 45 um"),
            ("fineness_m2kg", ">=", 15000, "m2/kg BET surface area"),
        ],
        note="IS 15388 specifies BET surface area, not Blaine. Only a stream "
             "whose fineness is reported on the same basis can be read against "
             "this limit - see the note on the material.",
    ),
    "Pozzolanic SCM, natural pozzolana class (ASTM C618 Class N)": dict(
        standard="ASTM C618 Class N",
        confidence="standard",
        value_inr_t=8000,
        sector="cement",
        limits=[
            ("sio2+al2o3+fe2o3", ">=", 70.0, "% total reactive oxides"),
            ("so3", "<=", 4.0, "%"),
            ("moisture", "<=", 3.0, "%"),
            ("loi", "<=", 10.0, "% loss on ignition"),
            ("retained_45um", "<=", 34.0, "% retained on 45 um, wet sieving"),
        ],
        note="Used here because India has no published specification for rice "
             "husk ash or bagasse ash as a supplementary cementitious material. "
             "An American standard is the honest reference, not an Indian one. "
             "C618 also requires a strength activity index of at least 75% of "
             "the control at 28 days, which is a mortar test rather than an "
             "assay - a pass here is necessary, not sufficient.",
    ),
    "Fly ash for structural concrete (IS 3812 Part 1)": dict(
        standard="IS 3812 (Part 1): 2013",
        confidence="standard",
        value_inr_t=5000,
        sector="cement",
        limits=[
            ("sio2+al2o3+fe2o3", ">=", 70.0, "% total reactive oxides"),
            ("sio2", ">=", 35.0, "%"),
            ("loi", "<=", 5.0, "% loss on ignition, unburnt carbon"),
            ("moisture", "<=", 2.0, "%"),
            ("fineness_m2kg", ">=", 320, "m2/kg Blaine specific surface"),
            ("so3", "<=", 3.0, "%"),
            ("mgo", "<=", 5.0, "%"),
            ("alkali_na2oeq", "<=", 1.5, "% as Na2O equivalent"),
            ("retained_45um", "<=", 34.0, "% residue on 45 um, wet sieving"),
        ],
        note="Siliceous pulverised fuel ash for use as a pozzolana in concrete. "
             "IS 3812 Part 1 also requires a lime reactivity of at least "
             "4.5 N/mm2 and a soundness test, neither of which can be read off "
             "a chemical assay - a passing grade here is necessary, not "
             "sufficient.",
    ),
    "Sinter plant iron feed (mill scale)": dict(
        standard="plant acceptance practice",
        confidence="indicative",
        value_inr_t=5200,
        sector="steel",
        limits=[
            ("fe2o3", ">=", 90.0, "% total iron oxide"),
            ("sio2", "<=", 3.0, "% silica"),
            ("moisture", "<=", 5.0, "%"),
            ("cl", "<=", 0.05, "%"),
        ],
        note="No Indian Standard governs mill scale as sinter feed; each works "
             "sets its own acceptance chemistry. The binding practical limit is "
             "usually residual rolling oil, below about 1%, which a chemical "
             "assay of this kind does not capture.",
    ),
    "GGBS for Portland slag cement (IS 16714)": dict(
        standard="IS 16714: 2018",
        confidence="standard",
        value_inr_t=4200,
        sector="cement",
        limits=[
            ("cao+mgo+sio2", ">=", 66.67, "% sum of the three main oxides"),
            ("mgo", "<=", 17.0, "%"),
            ("sulphide_s", "<=", 2.0, "% sulphide sulphur"),
            ("loi", "<=", 3.0, "%"),
            ("cl", "<=", 0.1, "% chloride"),
            ("glass_content", ">=", 85.0, "% glass"),
            ("fineness_m2kg", ">=", 320, "m2/kg Blaine"),
            ("moisture", "<=", 1.0, "%"),
        ],
        note="IS 16714 also requires the ratio (CaO + MgO) / SiO2 to exceed "
             "1.0. That is a ratio rather than a sum, so it is checked "
             "separately in the conformance report rather than as a limit row. "
             "IS 455 then governs how much of this may go into the cement.",
    ),
    "Cement kiln alternative fuel, co-processing (CPCB)": dict(
        standard="CPCB co-processing guidelines, 2017",
        confidence="indicative",
        value_inr_t=3200,
        sector="cement",
        limits=[
            ("calorific_mjkg", ">=", 12.0, "MJ/kg net calorific value"),
            ("cl", "<=", 1.0, "% total chlorine"),
            ("moisture", "<=", 25.0, "%"),
            ("so3", "<=", 3.0, "%"),
        ],
        note="CPCB's guidelines set out a trial-burn and authorisation process "
             "rather than a single national table of numeric limits. These are "
             "the thresholds kilns commonly apply. Chlorine is the one that "
             "decides most cases, because it builds up in the preheater.",
    ),
    "Plasterboard grade gypsum": dict(
        standard="IS 2095 (Part 1) board practice",
        confidence="indicative",
        value_inr_t=2800,
        sector="construction materials",
        limits=[
            ("purity_caso4", ">=", 90.0, "% CaSO4.2H2O"),
            ("cl", "<=", 0.01, "% chloride"),
            ("moisture", "<=", 10.0, "% free moisture"),
            ("mgo", "<=", 1.0, "% soluble magnesia"),
        ],
        note="IS 2095 specifies the finished board, not the incoming gypsum. "
             "These are the purity and chloride thresholds board plants "
             "typically impose on synthetic gypsum.",
    ),
    "Fly ash as admixture, PPC and mortar (IS 3812 Part 2)": dict(
        standard="IS 3812 (Part 2): 2013",
        confidence="standard",
        value_inr_t=2600,
        sector="cement",
        limits=[
            ("sio2+al2o3+fe2o3", ">=", 70.0, "% total reactive oxides"),
            ("sio2", ">=", 35.0, "%"),
            ("loi", "<=", 12.0, "% loss on ignition"),
            ("moisture", "<=", 2.0, "%"),
            ("fineness_m2kg", ">=", 200, "m2/kg Blaine"),
            ("so3", "<=", 3.0, "%"),
            ("mgo", "<=", 5.0, "%"),
        ],
        note="Part 2 covers fly ash used as an admixture rather than as a "
             "pozzolana in structural concrete, and is materially more "
             "permissive on unburnt carbon and fineness. This is the rung a "
             "coarse, high-carbon ash can still reach.",
    ),
    "Cement set retarder, synthetic gypsum": dict(
        standard="IS 1290 grade practice",
        confidence="indicative",
        value_inr_t=2600,
        sector="cement",
        limits=[
            ("purity_caso4", ">=", 70.0, "% CaSO4.2H2O"),
            ("cl", "<=", 0.05, "% chloride"),
            ("moisture", "<=", 10.0, "%"),
        ],
        note="IS 1290 covers mineral gypsum and grades it by purity. Cement "
             "plants apply a comparable purity floor to synthetic gypsum; the "
             "chloride limit protects the mill and the reinforcement.",
    ),
    "Soil conditioner, sodic soil reclamation": dict(
        standard="agronomic practice",
        confidence="indicative",
        value_inr_t=1800,
        sector="agriculture",
        limits=[
            ("purity_caso4", ">=", 70.0, "% CaSO4.2H2O for calcium supply"),
            ("cl", "<=", 0.1, "% chloride"),
            ("alkali_na2oeq", "<=", 1.0, "% - a sodic amendment must not add sodium"),
        ],
        note="Reclamation practice on sodic soils in Uttar Pradesh and Haryana. "
             "There is no numeric IS specification; the binding constraints in "
             "the field are soluble sodium and heavy metals, and a heavy metal "
             "screen is not modelled here.",
    ),
    "AAC block feedstock (IS 2185 Part 3)": dict(
        standard="IS 2185 (Part 3): 1984",
        confidence="indicative",
        value_inr_t=1100,
        sector="construction materials",
        limits=[
            ("sio2", ">=", 40.0, "% silica for the autoclave reaction"),
            ("loi", "<=", 8.0, "% loss on ignition"),
            ("so3", "<=", 3.0, "%"),
            ("cl", "<=", 0.1, "%"),
        ],
        note="IS 2185 Part 3 specifies the finished autoclaved cellular concrete "
             "block, not the ash feed. These are the feed thresholds AAC plants "
             "commonly apply; unburnt carbon interferes with the aluminium "
             "powder reaction that raises the cake.",
    ),
    "Cement raw meal component": dict(
        standard="kiln chemistry practice",
        confidence="indicative",
        value_inr_t=1100,
        sector="cement",
        limits=[
            ("cl", "<=", 0.02, "% chloride in the raw meal"),
            ("alkali_na2oeq", "<=", 1.0, "%"),
            ("so3", "<=", 2.5, "%"),
            ("moisture", "<=", 12.0, "%"),
        ],
        note="No IS standard governs a raw meal component; every kiln sets its "
             "own chemistry. Chloride and alkali matter because they cycle in "
             "the preheater and build rings. The limits shown are typical of "
             "Indian dry-process kilns.",
    ),
    "Fly ash bricks (IS 12894)": dict(
        standard="IS 12894: 2002",
        confidence="indicative",
        value_inr_t=900,
        sector="construction materials",
        limits=[
            ("sio2+al2o3+fe2o3", ">=", 70.0, "% total oxides"),
            ("loi", "<=", 12.0, "%"),
            ("so3", "<=", 3.0, "%"),
            ("moisture", "<=", 15.0, "%"),
        ],
        note="IS 12894 specifies the finished fly ash-lime brick by compressive "
             "strength and water absorption, not the ash. These are the feed "
             "thresholds brick units commonly work to.",
    ),
    "Agricultural liming material": dict(
        standard="agronomic practice",
        confidence="indicative",
        value_inr_t=900,
        sector="agriculture",
        limits=[
            ("cao", ">=", 40.0, "% CaO, the neutralising value"),
            ("cl", "<=", 0.1, "%"),
            ("alkali_na2oeq", "<=", 1.0, "%"),
        ],
        note="Effective on the acid soils of eastern and north-eastern India. "
             "The real acceptance test is neutralising value and fineness, and "
             "as with the soil conditioner a heavy metal screen is not modelled.",
    ),
    "Road base aggregate (IS 383 / MoRTH)": dict(
        standard="IS 383: 2016 and MoRTH specifications",
        confidence="indicative",
        value_inr_t=750,
        sector="road project",
        limits=[
            ("free_lime", "<=", 5.0, "% free lime, expansion risk"),
            ("moisture", "<=", 8.0, "%"),
            ("so3", "<=", 1.0, "%"),
        ],
        note="Aggregate is accepted on physical tests - grading, impact value, "
             "water absorption and, for steel slag, an expansion test after "
             "ageing. None of those is a chemical assay. Free lime is included "
             "because it is the chemical proxy for the expansion that actually "
             "fails these pavements.",
    ),
    "Road embankment fill (IRC SP:58)": dict(
        standard="IRC SP:58-2001",
        confidence="indicative",
        value_inr_t=400,
        sector="road project",
        limits=[
            ("moisture", "<=", 25.0, "%"),
            ("so3", "<=", 2.0, "%"),
            ("cl", "<=", 0.2, "%"),
        ],
        note="IRC SP:58 governs ash embankments through geotechnical indices - "
             "compaction, shear strength, free swell - not composition. The "
             "chemical limits here only screen out streams that would corrode "
             "buried metal or attack concrete structures.",
    ),
    "Structural fill and site levelling": dict(
        standard="general earthworks practice",
        confidence="indicative",
        value_inr_t=300,
        sector="construction materials",
        limits=[
            ("moisture", "<=", 30.0, "%"),
            ("cl", "<=", 0.5, "%"),
        ],
        note="The lowest rung in the library, and the destination for anything "
             "that clears nothing else. Included so the value cascade has a "
             "floor rather than ending in nothing.",
    ),
}

# Checks that are not a simple threshold on a property or a sum of properties.
# Kept separate and reported separately so a limit table never implies that a
# ratio requirement was folded into it.
RATIO_RULES = {
    "GGBS for Portland slag cement (IS 16714)": [
        ("(cao+mgo)/sio2", ">", 1.0,
         "IS 16714 requires the basicity ratio (CaO + MgO) / SiO2 to exceed 1.0"),
    ],
}


def specs() -> list:
    """Every specification, most valuable first."""
    return sorted(SPECS, key=lambda name: -SPECS[name]["value_inr_t"])


def spec(name: str) -> dict | None:
    key = str(name).strip().lower()
    for candidate, entry in SPECS.items():
        if candidate.lower() == key:
            return entry
    return None


def highest_value() -> tuple:
    """The most valuable application in the library, as (name, value)."""
    best = max(SPECS, key=lambda name: SPECS[name]["value_inr_t"])
    return best, SPECS[best]["value_inr_t"]
