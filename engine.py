"""Matching, scoring and valuation for Symbiosis Finder.

Everything in this module is deterministic arithmetic on the registry and the
knowledge base. The same registry always produces the same matches in the same
order. No language model is involved in producing any number here.

Every constant that affects a score or a rupee figure is a named module-level
variable with a comment, so it can be defended or changed openly.
"""

from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

import kb

# ----------------------------------------------------------------------
# Scoring weights. These sum to 1.0 and the score is 100 x the weighted sum.
# Quantity and proximity dominate because in practice an exchange fails for
# one of two reasons: the tonnages do not fit, or the freight eats the value.
# ----------------------------------------------------------------------
W_QUANTITY = 0.30      # how much of the receiver's usable ceiling gets filled
W_PROXIMITY = 0.28     # road distance against the material's economic limit
W_PROCESSING = 0.16    # how much treatment the by-product needs first
W_TIMING = 0.14        # months in the year when both sides are active
W_COMPLIANCE = 0.12    # regulatory friction on the stream

WEIGHTS = {
    "quantity": W_QUANTITY,
    "proximity": W_PROXIMITY,
    "timing": W_TIMING,
    "processing": W_PROCESSING,
    "compliance": W_COMPLIANCE,
}

# ----------------------------------------------------------------------
# Acceptance gates
# ----------------------------------------------------------------------
MIN_SCORE_DEFAULT = 35.0        # below this an exchange is not worth listing
DISTANCE_HARD_LIMIT = 1.5       # reject beyond max_km x this, even if scoring well
MIN_MATCH_TONNES = 1.0          # under a tonne a year is not an exchange

# ----------------------------------------------------------------------
# Distance
# ----------------------------------------------------------------------
EARTH_RADIUS_KM = 6371.0        # mean radius, haversine
ROAD_CIRCUITY_FACTOR = 1.30     # straight line to road distance; Indian highway
                                # networks typically run 1.25-1.35x great circle
PROXIMITY_EXPONENT = 1.4        # >1 so the penalty accelerates near the limit

# ----------------------------------------------------------------------
# Processing: how treatable the stream is (score) and what it costs (rupees)
# ----------------------------------------------------------------------
PROCESSING_FACTOR = {
    "none": 1.00,       # usable as delivered
    "simple": 0.85,     # screening, drying, baling
    "moderate": 0.55,   # grinding, briquetting, de-oiling, dewatering
    "complex": 0.25,    # hydrometallurgy, ultrafiltration, hazardous pre-treatment
}
PROCESSING_COST = {    # INR per tonne of by-product handled
    "none": 0,
    "simple": 250,
    "moderate": 900,
    "complex": 2600,
}

# ----------------------------------------------------------------------
# Compliance
# ----------------------------------------------------------------------
COMPLIANCE_UNREGULATED = 1.00              # ordinary industrial by-product
COMPLIANCE_REGULATED_AUTHORISED = 0.75     # hazardous stream, receiver holds authorisation
COMPLIANCE_REGULATED_UNAUTHORISED = 0.25   # hazardous stream, receiver does not

# ----------------------------------------------------------------------
# Valuation constants, all per year
# ----------------------------------------------------------------------
DISPOSAL_COST_DEFAULT = 1400   # INR/tonne. Landfill or captive dump cost avoided for
                               # an ordinary non-hazardous stream. Knowledge base
                               # entries may override it: hazardous streams routed to a
                               # TSDF cost several times this, and captive ash ponds
                               # rather less.
FREIGHT_RATE = 6.5             # INR per tonne-km, bulk road freight, full truck loads
PIPELINE_RATE = 120.0          # INR per tonne-km for heat and gas moved by pipeline:
                               # amortised pipe, insulation and pumping. Far dearer per
                               # km than road, which is why these exchanges only ever
                               # work over a few kilometres.

REQUIRED_COLUMNS = [
    "name", "sector", "state", "lat", "lon", "output_material",
    "output_tpa", "input_need_tpa", "availability", "authorised_hazardous",
]

# Column aliases accepted on upload, so a reasonable CSV does not need to match
# our spelling exactly.
COLUMN_ALIASES = {
    "facility": "name", "facility_name": "name", "plant": "name", "plant_name": "name",
    "industry": "sector", "sector_type": "sector", "type": "sector",
    "latitude": "lat", "longitude": "lon", "long": "lon", "lng": "lon",
    "byproduct": "output_material", "by_product": "output_material",
    "waste": "output_material", "output": "output_material",
    "material": "output_material", "waste_material": "output_material",
    "output_tonnes": "output_tpa", "output_tonnes_per_year": "output_tpa",
    "byproduct_tpa": "output_tpa", "waste_tpa": "output_tpa",
    "input_tpa": "input_need_tpa", "demand_tpa": "input_need_tpa",
    "raw_material_tpa": "input_need_tpa", "input_need": "input_need_tpa",
    "season": "availability", "seasonality": "availability",
    "hazardous_authorised": "authorised_hazardous",
    "hazardous_authorized": "authorised_hazardous",
    "authorized_hazardous": "authorised_hazardous",
    "hazardous_permit": "authorised_hazardous",
}

# India's bounding box, used only to warn about coordinates, never to drop them.
INDIA_BOUNDS = {"lat_min": 6.0, "lat_max": 37.0, "lon_min": 67.0, "lon_max": 98.0}

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
ALL_MONTHS = frozenset(range(1, 13))
MONTHS_IN_YEAR = 12

_TRUE_TOKENS = {"yes", "y", "true", "t", "1", "1.0", "authorised", "authorized"}


# ======================================================================
# Formatting
# ======================================================================

def inr(x) -> str:
    """Format rupees as ₹ Cr / L, the way an Indian plant manager reads a number."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(v):
        return "n/a"
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e7:
        return f"{sign}₹{a / 1e7:,.2f} Cr"
    if a >= 1e5:
        return f"{sign}₹{a / 1e5:,.2f} L"
    if a >= 1e3:
        return f"{sign}₹{a / 1e3:,.1f} k"
    return f"{sign}₹{a:,.0f}"


def tonnes(x) -> str:
    """Format tonnes per year as Mt / kt."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "n/a"
    if not math.isfinite(v):
        return "n/a"
    sign = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e6:
        return f"{sign}{a / 1e6:,.2f} Mt"
    if a >= 1e3:
        return f"{sign}{a / 1e3:,.1f} kt"
    return f"{sign}{a:,.0f} t"


# ======================================================================
# Geography and seasons
# ======================================================================

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def road_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Straight-line distance inflated by the road circuity factor."""
    return haversine_km(lat1, lon1, lat2, lon2) * ROAD_CIRCUITY_FACTOR


def active_months(availability) -> frozenset:
    """Months a facility is active, read from an availability string.

    Understands "crushing season (Nov-Apr)", "Oct-Jan", "year-round" and plain
    month lists. Anything unrecognised is treated as active all year, which is
    the permissive reading - it never invents a penalty from a parse failure.
    """
    if availability is None:
        return ALL_MONTHS
    text = str(availability).strip().lower()
    if not text:
        return ALL_MONTHS

    ranges = re.findall(r"([a-z]{3})[a-z]*\s*(?:-|to|until|through)\s*([a-z]{3})[a-z]*", text)
    months = set()
    for start, end in ranges:
        a, b = _MONTHS.get(start), _MONTHS.get(end)
        if a is None or b is None:
            continue
        m = a
        while True:                     # walk forward, wrapping across December
            months.add(m)
            if m == b:
                break
            m = 1 if m == 12 else m + 1
    if months:
        return frozenset(months)

    named = {_MONTHS[t] for t in re.findall(r"[a-z]{3}", text) if t in _MONTHS}
    if named:
        return frozenset(named)
    return ALL_MONTHS


def timing_factor(supplier_availability, receiver_availability) -> float:
    """Fraction of the year in which supply and demand are both active.

    Denominator is twelve months, not the shorter of the two windows. A six-month
    crushing season feeding a year-round kiln scores 0.5 because for half the year
    the kiln must source elsewhere or the exchange must be storage-backed - which
    is a real cost, and exactly what this factor is meant to surface.
    """
    overlap = active_months(supplier_availability) & active_months(receiver_availability)
    return len(overlap) / MONTHS_IN_YEAR


# ======================================================================
# Validation
# ======================================================================

def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    return str(value).strip().lower() in _TRUE_TOKENS


def validate(df: pd.DataFrame) -> tuple:
    """Normalise a registry upload. Returns (clean_df, problems).

    Never raises on a messy file: unknown columns are ignored, missing optional
    columns are filled with safe defaults, unparseable numbers become zero and
    rows without usable coordinates are dropped. Every repair is reported.
    """
    problems: list = []

    if df is None or len(df) == 0:
        return pd.DataFrame(columns=REQUIRED_COLUMNS), ["The file contains no rows."]

    out = df.copy()
    out.columns = [
        re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_")
        for c in out.columns
    ]
    renamed = {c: COLUMN_ALIASES[c] for c in out.columns if c in COLUMN_ALIASES}
    # Only rename where it does not collide with a column already correctly named.
    renamed = {k: v for k, v in renamed.items() if v not in out.columns}
    if renamed:
        out = out.rename(columns=renamed)
        problems.append(
            "Renamed columns to the expected names: "
            + ", ".join(f"{k} -> {v}" for k, v in sorted(renamed.items()))
            + "."
        )
    out = out.loc[:, ~out.columns.duplicated()]

    defaults = {
        "name": "", "sector": "unknown", "state": "unknown",
        "output_material": "", "output_tpa": 0.0, "input_need_tpa": 0.0,
        "availability": "continuous (year-round)", "authorised_hazardous": False,
    }
    missing = [c for c in REQUIRED_COLUMNS if c not in out.columns]
    fatal = [c for c in ("name", "lat", "lon") if c not in out.columns]
    if fatal:
        problems.append(
            "Missing required column(s): " + ", ".join(fatal)
            + ". A registry needs at least a facility name and its coordinates."
        )
        return pd.DataFrame(columns=REQUIRED_COLUMNS), problems
    for col in missing:
        out[col] = defaults[col]
        problems.append(f"Column '{col}' was missing; filled with a default value.")

    for col in ("lat", "lon", "output_tpa", "input_need_tpa"):
        raw = out[col]
        num = pd.to_numeric(raw, errors="coerce")
        broken = int((num.isna() & raw.notna() & (raw.astype(str).str.strip() != "")).sum())
        if broken:
            problems.append(
                f"{broken} row(s) had a non-numeric value in '{col}'; "
                + ("those rows were dropped." if col in ("lat", "lon") else "treated as zero.")
            )
        out[col] = num

    for col in ("name", "sector", "state", "output_material", "availability"):
        out[col] = out[col].fillna("").astype(str).str.strip()
    out["sector"] = out["sector"].str.lower().replace("", "unknown")
    out["state"] = out["state"].replace("", "unknown")
    out["output_material"] = out["output_material"].str.lower()
    out["availability"] = out["availability"].replace("", "continuous (year-round)")
    out["authorised_hazardous"] = out["authorised_hazardous"].map(_coerce_bool)

    before = len(out)
    out = out[out["name"].astype(str).str.strip() != ""]
    if len(out) < before:
        problems.append(f"Dropped {before - len(out)} row(s) with no facility name.")

    before = len(out)
    out = out[out["lat"].notna() & out["lon"].notna()]
    out = out[out["lat"].between(-90, 90) & out["lon"].between(-180, 180)]
    if len(out) < before:
        problems.append(f"Dropped {before - len(out)} row(s) with unusable coordinates.")

    if len(out):
        outside = ~(
            out["lat"].between(INDIA_BOUNDS["lat_min"], INDIA_BOUNDS["lat_max"])
            & out["lon"].between(INDIA_BOUNDS["lon_min"], INDIA_BOUNDS["lon_max"])
        )
        if int(outside.sum()):
            problems.append(
                f"{int(outside.sum())} facility/facilities sit outside India's bounding box. "
                "They are kept and scored, but will not appear on the map."
            )

    for col in ("output_tpa", "input_need_tpa"):
        out[col] = out[col].fillna(0.0)
        negative = int((out[col] < 0).sum())
        if negative:
            problems.append(f"{negative} row(s) had a negative '{col}'; clamped to zero.")
            out[col] = out[col].clip(lower=0.0)

    dupes = int(out["name"].duplicated().sum())
    if dupes:
        problems.append(f"{dupes} duplicate facility name(s) found; kept as separate rows.")

    known = {m.lower() for m in kb.materials()}
    offered = {m for m in out["output_material"].unique() if m}
    unknown = sorted(offered - known)
    if unknown:
        problems.append(
            "Not in the knowledge base, so these cannot be matched and will appear in "
            "gap analysis: " + ", ".join(unknown) + "."
        )

    out = out.reset_index(drop=True)
    return out[REQUIRED_COLUMNS], problems


# ======================================================================
# Matching
# ======================================================================

def _disposal_rate(entry: dict) -> float:
    return float(entry.get("disposal_cost", DISPOSAL_COST_DEFAULT))


def _freight_rate(entry: dict) -> float:
    return PIPELINE_RATE if entry.get("transport_mode") == "pipeline" else FREIGHT_RATE


def _score_pair(supplier, receiver, entry: dict) -> dict | None:
    """Score one (supplier, by-product, receiver, application) candidate.

    Returns None if the candidate fails a hard gate. The returned dict carries
    every input to every number, so the whole match can be audited downstream.
    """
    need = float(receiver["input_need_tpa"])
    output = float(supplier["output_tpa"])
    if need <= 0 or output <= 0:
        return None

    ceiling = need * float(entry["max_share"])
    matched = min(output, ceiling)
    if matched < MIN_MATCH_TONNES:
        return None

    straight_km = haversine_km(
        float(supplier["lat"]), float(supplier["lon"]),
        float(receiver["lat"]), float(receiver["lon"]),
    )
    road_km = straight_km * ROAD_CIRCUITY_FACTOR
    max_km = float(entry["max_km"])
    if road_km > max_km * DISTANCE_HARD_LIMIT:
        return None

    # --- the five factors, each normalised to 0-1 ---
    f_quantity = min(1.0, matched / ceiling) if ceiling > 0 else 0.0
    f_proximity = max(0.0, 1.0 - (road_km / max_km) ** PROXIMITY_EXPONENT)
    f_timing = timing_factor(supplier["availability"], receiver["availability"])
    f_processing = PROCESSING_FACTOR[entry["processing"]]
    if entry["hazard"] == "regulated":
        f_compliance = (
            COMPLIANCE_REGULATED_AUTHORISED
            if bool(receiver["authorised_hazardous"])
            else COMPLIANCE_REGULATED_UNAUTHORISED
        )
    else:
        f_compliance = COMPLIANCE_UNREGULATED

    factors = {
        "quantity": f_quantity,
        "proximity": f_proximity,
        "timing": f_timing,
        "processing": f_processing,
        "compliance": f_compliance,
    }
    score = 100.0 * sum(WEIGHTS[k] * v for k, v in factors.items())

    # --- valuation, per year ---
    disposal_rate = _disposal_rate(entry)
    freight_rate = _freight_rate(entry)
    processing_rate = PROCESSING_COST[entry["processing"]]

    material_value = matched * float(entry["substitution_ratio"]) * float(entry["virgin_value"])
    disposal_saved = matched * disposal_rate
    transport_cost = matched * road_km * freight_rate
    processing_cost = matched * processing_rate
    net = material_value + disposal_saved - transport_cost - processing_cost

    return {
        "score": round(score, 2),
        "supplier": supplier["name"],
        "supplier_sector": supplier["sector"],
        "supplier_state": supplier["state"],
        "supplier_lat": float(supplier["lat"]),
        "supplier_lon": float(supplier["lon"]),
        "receiver": receiver["name"],
        "receiver_sector": receiver["sector"],
        "receiver_state": receiver["state"],
        "receiver_lat": float(receiver["lat"]),
        "receiver_lon": float(receiver["lon"]),
        "material": entry["material"],
        "application": entry["application"],
        "replaces": entry["replaces"],

        # tonnage and its origin
        "matched_tpa": matched,
        "ceiling_tpa": ceiling,
        "supplier_output_tpa": output,
        "receiver_need_tpa": need,
        "supplier_share": matched / output if output else 0.0,
        "max_share": float(entry["max_share"]),

        # distance
        "straight_km": straight_km,
        "road_km": road_km,
        "max_km": max_km,
        "beyond_max_km": road_km > max_km,
        "transport_mode": entry.get("transport_mode", "road"),

        # factors
        "f_quantity": f_quantity,
        "f_proximity": f_proximity,
        "f_timing": f_timing,
        "f_processing": f_processing,
        "f_compliance": f_compliance,
        "c_quantity": W_QUANTITY * f_quantity * 100.0,
        "c_proximity": W_PROXIMITY * f_proximity * 100.0,
        "c_timing": W_TIMING * f_timing * 100.0,
        "c_processing": W_PROCESSING * f_processing * 100.0,
        "c_compliance": W_COMPLIANCE * f_compliance * 100.0,

        # money, line by line
        "material_value": material_value,
        "disposal_saved": disposal_saved,
        "transport_cost": transport_cost,
        "processing_cost": processing_cost,
        "net_value": net,
        "substitution_ratio": float(entry["substitution_ratio"]),
        "virgin_value": float(entry["virgin_value"]),
        "disposal_rate": disposal_rate,
        "freight_rate": freight_rate,
        "processing_rate": float(processing_rate),

        # environment
        "co2_avoided_t": matched * float(entry["co2_saved_t"]),
        "co2_saved_t": float(entry["co2_saved_t"]),

        # context for the audit panel
        "processing": entry["processing"],
        "hazard": entry["hazard"],
        "receiver_authorised": bool(receiver["authorised_hazardous"]),
        "supplier_availability": supplier["availability"],
        "receiver_availability": receiver["availability"],
        "basis": entry.get("basis", "mass"),
        "note": entry["note"],
    }


def _allocate(df: pd.DataFrame) -> pd.DataFrame:
    """Greedy feasible allocation over the ranked matches.

    `matched_tpa` is what a pair could exchange in isolation, so the same tonne
    of fly ash appears in every match its supplier takes part in. This pass walks
    the matches best score first and reserves tonnage, so `allocated_tpa` is a
    plan that never promises the same material twice. Scores are untouched.
    """
    if df.empty:
        for col in ("allocated_tpa", "allocated_share", "allocated_net_value",
                    "allocated_co2_t", "fully_allocated"):
            df[col] = []
        return df

    supply_left: dict = {}
    need_left: dict = {}
    ceiling_left: dict = {}
    allocated = []

    for row in df.itertuples(index=False):
        s_key = (row.supplier, row.material)
        r_key = row.receiver
        rm_key = (row.receiver, row.material)
        supply_left.setdefault(s_key, row.supplier_output_tpa)
        need_left.setdefault(r_key, row.receiver_need_tpa)
        ceiling_left.setdefault(rm_key, row.ceiling_tpa)

        take = max(0.0, min(
            row.matched_tpa,
            supply_left[s_key],
            need_left[r_key],
            ceiling_left[rm_key],
        ))
        supply_left[s_key] -= take
        need_left[r_key] -= take
        ceiling_left[rm_key] -= take
        allocated.append(take)

    df = df.copy()
    df["allocated_tpa"] = allocated
    ratio = np.where(df["matched_tpa"] > 0, df["allocated_tpa"] / df["matched_tpa"], 0.0)
    df["allocated_share"] = ratio
    df["allocated_net_value"] = df["net_value"] * ratio
    df["allocated_co2_t"] = df["co2_avoided_t"] * ratio
    df["fully_allocated"] = df["allocated_tpa"] >= df["matched_tpa"] - 1e-6
    return df


def find_matches(facilities: pd.DataFrame, min_score: float = MIN_SCORE_DEFAULT) -> pd.DataFrame:
    """Every viable exchange in the registry, ranked by score.

    Deterministic: ties break on supplier, material, receiver and application
    names, so the ordering never depends on dictionary or row iteration order.
    """
    if facilities is None or len(facilities) == 0:
        return _empty_matches()

    suppliers = facilities[
        (facilities["output_material"].astype(str).str.strip() != "")
        & (facilities["output_tpa"] > 0)
    ]
    receivers = facilities[facilities["input_need_tpa"] > 0]
    if suppliers.empty or receivers.empty:
        return _empty_matches()

    receivers_by_sector: dict = {}
    for _, r in receivers.iterrows():
        receivers_by_sector.setdefault(str(r["sector"]).lower(), []).append(r)

    rows = []
    for _, supplier in suppliers.iterrows():
        for entry in kb.uses_for(supplier["output_material"]):
            for sector in entry["accepting_sectors"]:
                for receiver in receivers_by_sector.get(sector.lower(), []):
                    if receiver["name"] == supplier["name"]:
                        continue                      # no self-matches
                    match = _score_pair(supplier, receiver, entry)
                    if match is None or match["score"] < min_score:
                        continue
                    rows.append(match)

    if not rows:
        return _empty_matches()

    df = pd.DataFrame(rows)
    df = df.sort_values(
        by=["score", "supplier", "material", "receiver", "application"],
        ascending=[False, True, True, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    df = _allocate(df)
    df.insert(0, "rank", np.arange(1, len(df) + 1))
    return df


def _empty_matches() -> pd.DataFrame:
    """An empty frame with the full match schema, so callers never special-case."""
    columns = [
        "rank", "score", "supplier", "supplier_sector", "supplier_state",
        "supplier_lat", "supplier_lon", "receiver", "receiver_sector",
        "receiver_state", "receiver_lat", "receiver_lon", "material",
        "application", "replaces", "matched_tpa", "ceiling_tpa",
        "supplier_output_tpa", "receiver_need_tpa", "supplier_share", "max_share",
        "straight_km", "road_km", "max_km", "beyond_max_km", "transport_mode",
        "f_quantity", "f_proximity", "f_timing", "f_processing", "f_compliance",
        "c_quantity", "c_proximity", "c_timing", "c_processing", "c_compliance",
        "material_value", "disposal_saved", "transport_cost", "processing_cost",
        "net_value", "substitution_ratio", "virgin_value", "disposal_rate",
        "freight_rate", "processing_rate", "co2_avoided_t", "co2_saved_t",
        "processing", "hazard", "receiver_authorised", "supplier_availability",
        "receiver_availability", "basis", "note", "allocated_tpa",
        "allocated_share", "allocated_net_value", "allocated_co2_t",
        "fully_allocated",
    ]
    return pd.DataFrame({c: pd.Series(dtype="object") for c in columns})


# ======================================================================
# Gaps and totals
# ======================================================================

def unmatched_outputs(facilities: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """By-products with no viable receiver anywhere in the registry.

    Two distinct failures, both reported: the stream is not in the knowledge
    base at all, or it is but every candidate receiver failed a gate - usually
    distance. These are where a new facility would pay for itself, so they are
    never dropped silently.
    """
    if facilities is None or len(facilities) == 0:
        return pd.DataFrame(columns=[
            "supplier", "sector", "state", "lat", "lon", "material", "output_tpa",
            "disposal_cost", "reason", "recorded_uses", "candidate_sectors",
            "nearest_candidate", "nearest_km", "nearest_max_km",
        ])

    # Compare on lower-cased material names: the registry is normalised to lower
    # case by validate(), while the knowledge base keeps display case ("FGD
    # gypsum", "RDF", "C&D waste").
    placed = set()
    if matches is not None and len(matches):
        placed = {
            (s, str(m).lower())
            for s, m in zip(matches["supplier"], matches["material"])
        }

    rows = []
    for _, f in facilities.iterrows():
        material = str(f["output_material"]).strip().lower()
        if not material or float(f["output_tpa"]) <= 0:
            continue
        if (f["name"], material) in placed:
            continue

        uses = kb.uses_for(material)
        disposal = (
            max(_disposal_rate(u) for u in uses) if uses else DISPOSAL_COST_DEFAULT
        )
        candidate_sectors = sorted({s for u in uses for s in u["accepting_sectors"]})

        nearest_name, nearest_km, nearest_limit = "", float("nan"), float("nan")
        if uses:
            reason = (
                "Recorded uses exist, but no receiver in this registry clears the "
                "distance, tonnage, score or authorisation gates."
            )
            for u in uses:
                pool = facilities[
                    facilities["sector"].str.lower().isin(
                        [s.lower() for s in u["accepting_sectors"]]
                    )
                    & (facilities["input_need_tpa"] > 0)
                    & (facilities["name"] != f["name"])
                ]
                for _, r in pool.iterrows():
                    d = road_distance_km(
                        float(f["lat"]), float(f["lon"]),
                        float(r["lat"]), float(r["lon"]),
                    )
                    if math.isnan(nearest_km) or d < nearest_km:
                        nearest_name, nearest_km, nearest_limit = r["name"], d, u["max_km"]
            if not nearest_name:
                reason = (
                    "No facility in this registry belongs to a sector that can accept "
                    "this stream."
                )
        else:
            reason = "This stream is not in the substitution knowledge base."

        rows.append({
            "supplier": f["name"],
            "sector": f["sector"],
            "state": f["state"],
            "lat": float(f["lat"]),
            "lon": float(f["lon"]),
            # Show the knowledge base's spelling ("FGD gypsum") rather than the
            # lower-cased registry value, falling back to the registry for a
            # stream the knowledge base has never heard of.
            "material": uses[0]["material"] if uses else material,
            "output_tpa": float(f["output_tpa"]),
            "disposal_cost": float(f["output_tpa"]) * disposal,
            "reason": reason,
            "recorded_uses": len(uses),
            "candidate_sectors": ", ".join(candidate_sectors) if candidate_sectors else "none recorded",
            "nearest_candidate": nearest_name,
            "nearest_km": nearest_km,
            "nearest_max_km": nearest_limit,
        })

    if not rows:
        return pd.DataFrame(columns=[
            "supplier", "sector", "state", "lat", "lon", "material", "output_tpa",
            "disposal_cost", "reason", "recorded_uses", "candidate_sectors",
            "nearest_candidate", "nearest_km", "nearest_max_km",
        ])
    return (
        pd.DataFrame(rows)
        .sort_values(["output_tpa", "supplier"], ascending=[False, True], kind="mergesort")
        .reset_index(drop=True)
    )


def network_summary(matches: pd.DataFrame) -> dict:
    """Network totals.

    Headline tonnage, CO2 and value are taken from one match per
    supplier+material - the best-scoring one - so a supplier's output is never
    counted twice across the several receivers it could serve. The allocated_*
    figures come from the greedy allocation instead, which lets one supplier
    serve several receivers while still never promising a tonne twice.
    """
    if matches is None or len(matches) == 0:
        return {
            "exchanges": 0, "suppliers": 0, "receivers": 0,
            "tonnes_diverted": 0.0, "co2_avoided_t": 0.0, "value_unlocked": 0.0,
            "loss_making": 0, "loss_value": 0.0,
            "allocated_tonnes": 0.0, "allocated_co2_t": 0.0, "allocated_value": 0.0,
            "mean_score": 0.0, "best_score": 0.0,
        }

    best = (
        matches.sort_values(["score", "supplier", "material"],
                            ascending=[False, True, True], kind="mergesort")
        .drop_duplicates(subset=["supplier", "material"], keep="first")
    )
    return {
        "exchanges": int(len(matches)),
        "suppliers": int(matches["supplier"].nunique()),
        "receivers": int(matches["receiver"].nunique()),
        "tonnes_diverted": float(best["matched_tpa"].sum()),
        "co2_avoided_t": float(best["co2_avoided_t"].sum()),
        "value_unlocked": float(best["net_value"].sum()),
        "loss_making": int((matches["net_value"] < 0).sum()),
        "loss_value": float(matches.loc[matches["net_value"] < 0, "net_value"].sum()),
        "allocated_tonnes": float(matches["allocated_tpa"].sum()),
        "allocated_co2_t": float(matches["allocated_co2_t"].sum()),
        "allocated_value": float(matches["allocated_net_value"].sum()),
        "mean_score": float(matches["score"].mean()),
        "best_score": float(matches["score"].max()),
    }


def template_csv() -> str:
    """A minimal registry template for the sidebar download."""
    return (
        "name,sector,state,lat,lon,output_material,output_tpa,input_need_tpa,"
        "availability,authorised_hazardous\n"
        "Example Power Station,thermal power,Chhattisgarh,22.3595,82.6963,fly ash,"
        "1200000,0,continuous (year-round),no\n"
        "Example Cement Works,cement,Madhya Pradesh,24.5667,80.8322,,0,2500000,"
        "continuous (year-round),yes\n"
        "Example Sugar Mill,sugar,Uttar Pradesh,29.4720,77.7040,bagasse,180000,0,"
        "crushing season (Nov-Apr),no\n"
    )
