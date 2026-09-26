"""Plain-language case for a scored exchange.

This module performs no arithmetic on the exchange. It receives a finished
match from `engine.find_matches` and arranges the numbers already in it into
sentences. There is no model here, no network call and no randomness: the same
match always produces the same words.

The only transformations applied are presentational - rupees into crore,
tonnes into kilotonnes, a 0-1 factor into a percentage - all of which are
formatting, not valuation.
"""

from __future__ import annotations

from engine import inr, tonnes

# Score bands. The wording changes with the band so a 90 does not read like a 40.
BANDS = [
    (85.0, "strong"),
    (70.0, "solid"),
    (55.0, "workable"),
    (45.0, "marginal"),
    (0.0, "weak"),
]

SECTION_ORDER = [
    "What could be exchanged",
    "Is it practical",
    "What it is worth",
    "What to watch",
]

_PROCESSING_PHRASE = {
    "none": "needs no treatment - it can be used as delivered",
    "simple": "needs simple preparation such as screening, drying or baling",
    "moderate": "needs real processing - grinding, briquetting, dewatering or de-oiling",
    "complex": "needs heavy processing, which is the main cost and the main risk",
}


def band_for(score: float) -> str:
    """The qualitative band a score falls in."""
    for floor, name in BANDS:
        if float(score) >= floor:
            return name
    return "weak"


def _get(match, key, default=None):
    """Read a field from a dict or a pandas Series without caring which."""
    try:
        value = match[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _pct(x) -> str:
    return f"{float(x) * 100:.0f}%"


def _km(x) -> str:
    return f"{float(x):,.0f} km"


def _headline(match) -> str:
    score = float(_get(match, "score", 0.0))
    band = band_for(score)
    material = _get(match, "material", "the by-product")
    supplier = _get(match, "supplier", "the supplier")
    receiver = _get(match, "receiver", "the receiver")
    openers = {
        "strong": f"A strong match: {supplier} has {material} that {receiver} can use with little standing in the way.",
        "solid": f"A solid match: {material} from {supplier} fits {receiver}'s needs, with a manageable catch or two.",
        "workable": f"Workable: {receiver} can use {supplier}'s {material}, but it needs work to stand up.",
        "marginal": f"Marginal: the substitution is real, but this particular pairing of {supplier} and {receiver} is near the edge of sense.",
        "weak": f"Weak: {material} from {supplier} is technically usable by {receiver}, and little else recommends it.",
    }
    return f"{openers[band]} Score {score:.1f} of 100."


def _what_could_be_exchanged(match) -> str:
    material = _get(match, "material", "the by-product")
    supplier = _get(match, "supplier", "the supplier")
    receiver = _get(match, "receiver", "the receiver")
    application = _get(match, "application", "an industrial use")
    replaces = _get(match, "replaces", "virgin material")
    matched = _get(match, "matched_tpa", 0.0)
    output = _get(match, "supplier_output_tpa", 0.0)
    ceiling = _get(match, "ceiling_tpa", 0.0)
    need = _get(match, "receiver_need_tpa", 0.0)
    max_share = _get(match, "max_share", 0.0)
    ratio = float(_get(match, "substitution_ratio", 1.0))
    share = _get(match, "supplier_share", 0.0)
    basis = _get(match, "basis", "mass")

    lines = [
        f"{supplier} produces {tonnes(output)} of {material} a year. "
        f"{receiver} draws {tonnes(need)} of input, and {material} can cover at most "
        f"{_pct(max_share)} of it in {application} - a ceiling of {tonnes(ceiling)}. "
        f"The exchange is therefore {tonnes(matched)} a year."
    ]

    if ratio == 1.0:
        lines.append(f"Each tonne used displaces a tonne of {replaces}.")
    elif ratio < 1.0:
        lines.append(
            f"Each tonne used displaces {ratio:.2f} t of {replaces} - less than one for one, "
            "because the by-product is the weaker material of the two."
        )
    else:
        lines.append(
            f"Each tonne used displaces {ratio:.2f} t of {replaces}, more than its own weight, "
            "because it also removes material the receiver would otherwise have to add."
        )

    if float(share) < 0.25:
        lines.append(
            f"This places only {_pct(share)} of what {supplier} produces. The rest still needs "
            "somewhere to go - one receiver does not solve this supplier's problem."
        )
    elif float(share) >= 0.99:
        lines.append(f"This places the supplier's entire output of {material}.")
    else:
        lines.append(f"This places {_pct(share)} of what {supplier} produces.")

    if basis == "energy":
        lines.append(
            "Tonnage here is a coal- or gas-equivalent stand-in, not a physical mass: this is "
            "an energy stream and has no tonnage of its own."
        )
    return " ".join(lines)


def _is_it_practical(match) -> str:
    road_km = _get(match, "road_km", 0.0)
    max_km = _get(match, "max_km", 0.0)
    beyond = bool(_get(match, "beyond_max_km", False))
    mode = _get(match, "transport_mode", "road")
    processing = _get(match, "processing", "none")
    f_timing = float(_get(match, "f_timing", 1.0))
    sup_season = _get(match, "supplier_availability", "")
    rec_season = _get(match, "receiver_availability", "")
    hazard = _get(match, "hazard", "none")
    authorised = bool(_get(match, "receiver_authorised", False))
    f_proximity = float(_get(match, "f_proximity", 0.0))

    lines = []
    if mode == "pipeline":
        lines.append(
            f"The two sites are {_km(road_km)} apart. This stream moves by pipeline, not by "
            f"truck, so the {_km(max_km)} limit is a physical one rather than an economic one."
        )
    elif beyond:
        lines.append(
            f"At {_km(road_km)} the haul is past the {_km(max_km)} at which this material stops "
            "making commercial sense, so proximity scores zero. It is listed because the other "
            "factors carry it, not because the distance works."
        )
    elif f_proximity >= 0.75:
        lines.append(
            f"At {_km(road_km)} against a {_km(max_km)} limit, the two plants are close enough "
            "that freight is a detail rather than a decision."
        )
    else:
        lines.append(
            f"The haul is {_km(road_km)} against a {_km(max_km)} limit for this material - "
            "inside the range, but far enough that freight is a real line in the arithmetic."
        )

    lines.append(f"The material {_PROCESSING_PHRASE.get(processing, 'needs preparation')}.")

    if f_timing >= 0.999:
        lines.append("Both sides run year-round, so supply and demand line up every month.")
    else:
        lines.append(
            f"Timing is the weak point: the supplier runs {sup_season} and the receiver "
            f"{rec_season}, which overlap for {_pct(f_timing)} of the year. Outside that window "
            "the receiver must source elsewhere, or someone must pay to store the material."
        )

    if hazard == "regulated":
        if authorised:
            lines.append(
                "The stream is regulated, and the receiver holds the authorisation to handle it - "
                "which still means manifested transport and a paper trail, but the permission exists."
            )
        else:
            lines.append(
                "The stream is regulated and the receiver is not authorised to handle it. Nothing "
                "can move until that authorisation is obtained; treat this as a prerequisite, not "
                "a detail."
            )
    return " ".join(lines)


def _what_it_is_worth(match) -> str:
    material_value = float(_get(match, "material_value", 0.0))
    disposal_saved = float(_get(match, "disposal_saved", 0.0))
    transport_cost = float(_get(match, "transport_cost", 0.0))
    processing_cost = float(_get(match, "processing_cost", 0.0))
    net = float(_get(match, "net_value", 0.0))
    co2 = _get(match, "co2_avoided_t", 0.0)
    matched = _get(match, "matched_tpa", 0.0)
    replaces = _get(match, "replaces", "virgin material")

    ledger = (
        f"Virgin {replaces} displaced is worth {inr(material_value)} a year and avoided disposal "
        f"another {inr(disposal_saved)}. Against that, freight costs {inr(transport_cost)} and "
        f"processing {inr(processing_cost)}."
    )

    if net < 0:
        verdict = (
            f"It does not pay for itself: the exchange is {inr(net)} a year, a loss. Freight and "
            "processing cost more than the material saves, so nobody will do this on economics "
            f"alone. The environmental case may still stand - it keeps {tonnes(matched)} out of "
            f"disposal and avoids {tonnes(co2)} of CO2 a year - but it would need a gate fee, a "
            "subsidy, a shorter haul or a cheaper processing route before anyone signs."
        )
    elif net < 1e7:
        verdict = (
            f"The exchange is worth {inr(net)} a year net, and avoids {tonnes(co2)} of CO2. "
            "That is positive but thin: a freight rate increase or a processing surprise would "
            "close the gap."
        )
    else:
        verdict = (
            f"The exchange is worth {inr(net)} a year net and avoids {tonnes(co2)} of CO2. "
            "The margin is wide enough to survive a worse freight rate than assumed here."
        )

    caveat = (
        "This is the size of the prize across both parties, not either one's margin - how it "
        "splits is a commercial negotiation."
    )
    return " ".join([ledger, verdict, caveat])


def _what_to_watch(match) -> str:
    note = _get(match, "note", "")
    f_quantity = float(_get(match, "f_quantity", 1.0))
    f_processing = float(_get(match, "f_processing", 1.0))
    f_compliance = float(_get(match, "f_compliance", 1.0))
    f_proximity = float(_get(match, "f_proximity", 1.0))
    f_timing = float(_get(match, "f_timing", 1.0))
    score = float(_get(match, "score", 0.0))
    band = band_for(score)

    weakest = min(
        [("tonnage fit", f_quantity), ("distance", f_proximity), ("seasonal overlap", f_timing),
         ("processing burden", f_processing), ("regulatory status", f_compliance)],
        key=lambda pair: pair[1],
    )

    lines = []
    if note:
        lines.append(str(note))

    if weakest[1] >= 0.85:
        lines.append(
            "No single factor drags this down; the weakest is "
            f"{weakest[0]} at {_pct(weakest[1])}, which is still strong."
        )
    else:
        lines.append(
            f"The binding constraint is {weakest[0]}, scoring {_pct(weakest[1])}. "
            "That is where to look first if this exchange is to be improved."
        )

    closers = {
        "strong": "On these numbers this is worth a conversation between the two plants now.",
        "solid": "Worth a site visit and a trial consignment before anything is committed.",
        "workable": "Worth a feasibility check: the idea holds, the specifics need testing.",
        "marginal": "Treat as a fallback. It clears the bar, but only just, and a better receiver "
                    "may exist outside this registry.",
        "weak": "Listed for completeness rather than as a recommendation.",
    }
    lines.append(closers[band])
    lines.append(
        "Figures rest on representative capacities and indicative prices, not audited plant data."
    )
    return " ".join(lines)


def explain(match) -> dict:
    """Four short sections for one scored exchange.

    Returns {"headline": str, "band": str, "sections": {title: text}} with the
    sections in SECTION_ORDER. Raises nothing for a well-formed match; missing
    optional fields fall back to neutral wording.
    """
    return {
        "headline": _headline(match),
        "band": band_for(float(_get(match, "score", 0.0))),
        "sections": {
            "What could be exchanged": _what_could_be_exchanged(match),
            "Is it practical": _is_it_practical(match),
            "What it is worth": _what_it_is_worth(match),
            "What to watch": _what_to_watch(match),
        },
    }


def explain_gap(gap) -> str:
    """Why a by-product has nowhere to go, from a row of unmatched_outputs."""
    material = _get(gap, "material", "this stream")
    supplier = _get(gap, "supplier", "the supplier")
    output = _get(gap, "output_tpa", 0.0)
    disposal = _get(gap, "disposal_cost", 0.0)
    uses = int(_get(gap, "recorded_uses", 0) or 0)
    sectors = _get(gap, "candidate_sectors", "none recorded")
    nearest = _get(gap, "nearest_candidate", "")
    nearest_km = _get(gap, "nearest_km", None)
    nearest_max = _get(gap, "nearest_max_km", None)

    lines = [
        f"{supplier} puts out {tonnes(output)} of {material} a year with no viable receiver in "
        f"this registry, and carries roughly {inr(disposal)} a year in disposal cost for it."
    ]
    if uses == 0:
        lines.append(
            "The substitution knowledge base records no use for this stream at all. That is a "
            "statement about the knowledge base as much as about the material - it may have a "
            "use this tool does not know, and it is the first thing worth researching."
        )
    else:
        lines.append(
            f"There are {uses} recorded use(s) for it, in these sectors: {sectors}. "
            "The substitution is real; the receiver is missing."
        )
        try:
            if nearest and nearest_km is not None and nearest_max is not None:
                if float(nearest_km) == float(nearest_km):  # not NaN
                    lines.append(
                        f"The nearest candidate is {nearest} at {_km(nearest_km)}, against an "
                        f"economic limit of {_km(nearest_max)} for this material. That gap is the "
                        "whole problem."
                    )
        except (TypeError, ValueError):
            pass
    lines.append(
        "A stream this size with no outlet is where a processing or aggregation facility would "
        "pay for itself - the disposal cost alone is the revenue it would not have to earn."
    )
    return " ".join(lines)
